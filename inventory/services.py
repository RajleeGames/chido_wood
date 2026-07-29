from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from datetime import datetime, time

from .models import (
    ConversionBatchUsage,
    ConversionOutput,
    StockAdjustment,
    StockAdjustmentBatchUsage,
    StockBatch,
    StockMovement,
    WoodConversion,
)


QUANTITY_PLACES = Decimal("0.001")
MONEY_PLACES = Decimal("0.01")
UNIT_COST_PLACES = Decimal("0.0001")


def as_decimal(value):
    if isinstance(value, Decimal):
        return value

    return Decimal(str(value))


def round_quantity(value):
    return as_decimal(value).quantize(
        QUANTITY_PLACES,
        rounding=ROUND_HALF_UP,
    )


def round_money(value):
    return as_decimal(value).quantize(
        MONEY_PLACES,
        rounding=ROUND_HALF_UP,
    )


def round_unit_cost(value):
    return as_decimal(value).quantize(
        UNIT_COST_PLACES,
        rounding=ROUND_HALF_UP,
    )


@transaction.atomic
def create_stock_batch(
    *,
    product,
    quantity,
    unit_cost,
    source_type,
    source_reference="",
    supplier=None,
    user=None,
    received_at=None,
    notes="",
):
    quantity = round_quantity(quantity)
    unit_cost = round_unit_cost(unit_cost)

    if quantity <= 0:
        raise ValidationError(
            "Stock quantity must be greater than zero."
        )

    if unit_cost < 0:
        raise ValidationError(
            "Unit cost cannot be negative."
        )

    batch = StockBatch.objects.create(
        product=product,
        supplier=supplier,
        source_type=source_type,
        source_reference=source_reference,
        received_quantity=quantity,
        remaining_quantity=quantity,
        unit_cost=unit_cost,
        received_at=received_at or timezone.now(),
        notes=notes,
        created_by=user,
    )

    movement_type_map = {
        StockBatch.SourceType.OPENING:
            StockMovement.MovementType.OPENING,

        StockBatch.SourceType.PURCHASE:
            StockMovement.MovementType.PURCHASE,

        StockBatch.SourceType.CONVERSION:
            StockMovement.MovementType.CONVERSION_OUTPUT,

        StockBatch.SourceType.ADJUSTMENT:
            StockMovement.MovementType.ADJUSTMENT_IN,

        StockBatch.SourceType.RETURN:
            StockMovement.MovementType.SALE_RETURN,
    }

    movement_type = movement_type_map[source_type]

    StockMovement.objects.create(
        product=product,
        batch=batch,
        movement_type=movement_type,
        quantity_delta=quantity,
        unit_cost=unit_cost,
        total_cost=round_money(quantity * unit_cost),
        reference=source_reference,
        notes=notes,
        created_by=user,
    )

    return batch


@transaction.atomic
def consume_stock_fifo(
    *,
    product,
    quantity,
    movement_type,
    reference="",
    notes="",
    user=None,
):
    quantity = round_quantity(quantity)

    if quantity <= 0:
        raise ValidationError(
            "Quantity must be greater than zero."
        )

    batches = list(
        StockBatch.objects
        .select_for_update()
        .filter(
            product=product,
            is_active=True,
            remaining_quantity__gt=0,
        )
        .order_by(
            "received_at",
            "id",
        )
    )

    available_quantity = sum(
        (
            batch.remaining_quantity
            for batch in batches
        ),
        Decimal("0.000"),
    )

    if available_quantity < quantity:
        raise ValidationError(
            (
                f"Insufficient stock for {product.name}. "
                f"Available: {available_quantity}. "
                f"Required: {quantity}."
            )
        )

    remaining_to_consume = quantity
    total_cost = Decimal("0.00")
    allocations = []

    for batch in batches:
        if remaining_to_consume <= 0:
            break

        quantity_from_batch = min(
            batch.remaining_quantity,
            remaining_to_consume,
        )

        quantity_from_batch = round_quantity(
            quantity_from_batch
        )

        line_cost = round_money(
            quantity_from_batch * batch.unit_cost
        )

        batch.remaining_quantity = round_quantity(
            batch.remaining_quantity - quantity_from_batch
        )

        batch.save(
            update_fields=[
                "remaining_quantity",
            ]
        )

        StockMovement.objects.create(
            product=product,
            batch=batch,
            movement_type=movement_type,
            quantity_delta=-quantity_from_batch,
            unit_cost=batch.unit_cost,
            total_cost=line_cost,
            reference=reference,
            notes=notes,
            created_by=user,
        )

        allocations.append(
            {
                "batch": batch,
                "quantity": quantity_from_batch,
                "unit_cost": batch.unit_cost,
                "total_cost": line_cost,
            }
        )

        total_cost += line_cost
        remaining_to_consume -= quantity_from_batch

    return round_money(total_cost), allocations

@transaction.atomic
def post_stock_adjustment(
    *,
    adjustment_id,
    user,
):
    adjustment = (
        StockAdjustment.objects
        .select_for_update()
        .select_related("product")
        .get(pk=adjustment_id)
    )

    if adjustment.status != StockAdjustment.Status.DRAFT:
        raise ValidationError(
            "Only draft stock adjustments can be posted."
        )

    if adjustment.quantity <= 0:
        raise ValidationError(
            "Adjustment quantity must be greater than zero."
        )

    if adjustment.created_batch_id:
        raise ValidationError(
            "This adjustment already has a stock batch."
        )

    if adjustment.batch_usages.exists():
        raise ValidationError(
            "This adjustment has already consumed stock."
        )

    reference = adjustment.adjustment_number

    movement_notes = adjustment.reason

    if adjustment.notes:
        movement_notes = (
            f"{adjustment.reason}. {adjustment.notes}"
        )

    if adjustment.adds_stock:
        if adjustment.unit_cost <= 0:
            raise ValidationError(
                (
                    "Unit cost must be greater than zero "
                    "for opening stock and stock increases."
                )
            )

        if (
            adjustment.adjustment_type
            == StockAdjustment.AdjustmentType.OPENING
        ):
            source_type = StockBatch.SourceType.OPENING
        else:
            source_type = StockBatch.SourceType.ADJUSTMENT

        adjustment_datetime = timezone.make_aware(
            datetime.combine(
                adjustment.adjustment_date,
                time(hour=12),
            )
        )

        created_batch = create_stock_batch(
            product=adjustment.product,
            quantity=adjustment.quantity,
            unit_cost=adjustment.unit_cost,
            source_type=source_type,
            source_reference=reference,
            user=user,
            received_at=adjustment_datetime,
            notes=movement_notes,
        )

        adjustment.created_batch = created_batch

        adjustment.total_cost = round_money(
            adjustment.quantity
            * adjustment.unit_cost
        )

    else:
        movement_type_map = {
            StockAdjustment.AdjustmentType.DECREASE:
                StockMovement.MovementType.ADJUSTMENT_OUT,

            StockAdjustment.AdjustmentType.DAMAGE:
                StockMovement.MovementType.DAMAGE,

            StockAdjustment.AdjustmentType.WASTE:
                StockMovement.MovementType.WASTE,
        }

        movement_type = movement_type_map.get(
            adjustment.adjustment_type
        )

        if movement_type is None:
            raise ValidationError(
                "Invalid stock adjustment type."
            )

        total_cost, allocations = consume_stock_fifo(
            product=adjustment.product,
            quantity=adjustment.quantity,
            movement_type=movement_type,
            reference=reference,
            notes=movement_notes,
            user=user,
        )

        StockAdjustmentBatchUsage.objects.bulk_create(
            [
                StockAdjustmentBatchUsage(
                    adjustment=adjustment,
                    batch=allocation["batch"],
                    quantity_used=allocation["quantity"],
                    unit_cost=allocation["unit_cost"],
                    total_cost=allocation["total_cost"],
                )
                for allocation in allocations
            ]
        )

        adjustment.unit_cost = Decimal("0.0000")
        adjustment.total_cost = total_cost

    adjustment.status = StockAdjustment.Status.POSTED
    adjustment.posted_by = user
    adjustment.posted_at = timezone.now()

    adjustment.save(
        update_fields=[
            "unit_cost",
            "total_cost",
            "created_batch",
            "status",
            "posted_by",
            "posted_at",
            "updated_at",
        ]
    )

    return adjustment

@transaction.atomic
def post_wood_conversion(
    *,
    conversion_id,
    user,
):
    conversion = (
        WoodConversion.objects
        .select_for_update()
        .select_related(
            "source_product",
            "source_product__category",
        )
        .get(pk=conversion_id)
    )

    # Only draft conversions may affect inventory.
    if conversion.status != WoodConversion.Status.DRAFT:
        raise ValidationError(
            "Only draft conversions can be posted."
        )

    # Validate the source quantity.
    if conversion.source_quantity <= 0:
        raise ValidationError(
            "Source quantity must be greater than zero."
        )

    # Internal processing cost cannot be negative.
    if conversion.additional_cutting_cost < 0:
        raise ValidationError(
            "Additional processing cost cannot be negative."
        )

    # Only Timber products can be used as conversion sources.
    if (
        not conversion.source_product.category
        or conversion.source_product.category.code != "TIMBER"
    ):
        raise ValidationError(
            "Only Timber products can be converted."
        )

    outputs = list(
        ConversionOutput.objects
        .select_for_update()
        .select_related(
            "product",
            "product__category",
        )
        .filter(conversion=conversion)
        .order_by("id")
    )

    # A conversion record requires output stock because its
    # purpose is changing source stock into other products.
    # Normal complete Timber is sold directly through Sales/POS.
    if not outputs:
        raise ValidationError(
            "Add at least one output product before posting."
        )

    # Prevent accidental reposting of an incomplete old record.
    if conversion.batch_usages.exists():
        raise ValidationError(
            "This conversion has already consumed source stock."
        )

    selected_output_product_ids = set()

    for output in outputs:
        if output.product is None:
            raise ValidationError(
                "Every conversion output must have a product."
            )

        if (
            not output.product.category
            or output.product.category.code != "TIMBER"
        ):
            raise ValidationError(
                (
                    f"{output.product.name} is not a "
                    f"Timber product."
                )
            )

        if (
            output.product_id
            == conversion.source_product_id
        ):
            raise ValidationError(
                (
                    "The output product cannot be the same "
                    "as the source product."
                )
            )

        if (
            output.product_id
            in selected_output_product_ids
        ):
            raise ValidationError(
                (
                    f"{output.product.name} has been added "
                    f"more than once."
                )
            )

        selected_output_product_ids.add(
            output.product_id
        )

        if output.quantity <= 0:
            raise ValidationError(
                (
                    f"Output quantity for "
                    f"{output.product.name} must be "
                    f"greater than zero."
                )
            )

        if output.output_batch_id:
            raise ValidationError(
                (
                    f"{output.product.name} already has "
                    f"a conversion stock batch."
                )
            )

    # Remove the source Timber from available stock using FIFO.
    source_cost, batch_allocations = consume_stock_fifo(
        product=conversion.source_product,
        quantity=conversion.source_quantity,
        movement_type=(
            StockMovement.MovementType.CONVERSION_INPUT
        ),
        reference=conversion.conversion_number,
        notes=(
            f"Source stock used for "
            f"{conversion.conversion_number}"
        ),
        user=user,
    )

    # Save exactly which FIFO source batches were consumed.
    ConversionBatchUsage.objects.bulk_create(
        [
            ConversionBatchUsage(
                conversion=conversion,
                batch=allocation["batch"],
                quantity_used=allocation["quantity"],
                unit_cost=allocation["unit_cost"],
                total_cost=allocation["total_cost"],
            )
            for allocation in batch_allocations
        ]
    )

    # The output stock carries the source FIFO cost plus any
    # internal processing or machine cost.
    total_conversion_cost = round_money(
        source_cost
        + conversion.additional_cutting_cost
    )

    # Allocate conversion cost using expected selling value.
    # Higher-value outputs receive a larger part of the cost.
    selling_value_basis = []

    for output in outputs:
        selling_value = round_money(
            output.quantity
            * output.product.selling_price
        )

        selling_value_basis.append(
            selling_value
        )

    total_basis = sum(
        selling_value_basis,
        Decimal("0.00"),
    )

    # When selling prices are zero, allocate by output quantity.
    if total_basis <= 0:
        selling_value_basis = [
            output.quantity
            for output in outputs
        ]

        total_basis = sum(
            selling_value_basis,
            Decimal("0.000"),
        )

    if total_basis <= 0:
        raise ValidationError(
            "The total output quantity must be greater than zero."
        )

    remaining_cost_to_allocate = total_conversion_cost

    for index, output in enumerate(outputs):
        is_last_output = (
            index == len(outputs) - 1
        )

        # Give the last output the remaining amount to avoid
        # losing cents through decimal rounding.
        if is_last_output:
            allocated_cost = round_money(
                remaining_cost_to_allocate
            )
        else:
            allocated_cost = round_money(
                total_conversion_cost
                * selling_value_basis[index]
                / total_basis
            )

            remaining_cost_to_allocate = round_money(
                remaining_cost_to_allocate
                - allocated_cost
            )

        unit_cost = round_unit_cost(
            allocated_cost
            / output.quantity
        )

        output_batch = create_stock_batch(
            product=output.product,
            quantity=output.quantity,
            unit_cost=unit_cost,
            source_type=(
                StockBatch.SourceType.CONVERSION
            ),
            source_reference=(
                conversion.conversion_number
            ),
            user=user,
            notes=(
                f"Produced from "
                f"{conversion.source_product.name} "
                f"through "
                f"{conversion.conversion_number}"
            ),
        )

        output.allocated_cost = allocated_cost
        output.unit_cost = unit_cost
        output.output_batch = output_batch

        output.save(
            update_fields=[
                "allocated_cost",
                "unit_cost",
                "output_batch",
            ]
        )

    conversion.source_cost = source_cost
    conversion.total_conversion_cost = (
        total_conversion_cost
    )
    conversion.status = (
        WoodConversion.Status.POSTED
    )
    conversion.posted_by = user
    conversion.posted_at = timezone.now()

    conversion.save(
        update_fields=[
            "source_cost",
            "total_conversion_cost",
            "status",
            "posted_by",
            "posted_at",
            "updated_at",
        ]
    )

    return conversion