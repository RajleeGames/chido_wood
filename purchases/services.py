from datetime import datetime, time
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from inventory.models import StockBatch
from inventory.services import (
    create_stock_batch,
    round_money,
    round_unit_cost,
)
from .models import Purchase, PurchaseItem


@transaction.atomic
def post_purchase(*, purchase_id, user):
    purchase = (
        Purchase.objects
        .select_for_update()
        .select_related("supplier")
        .get(pk=purchase_id)
    )

    if purchase.status != Purchase.Status.DRAFT:
        raise ValidationError(
            "Only draft purchases can be posted."
        )

    items = list(
        PurchaseItem.objects
        .select_for_update()
        .select_related("product")
        .filter(purchase=purchase)
        .order_by("id")
    )

    if not items:
        raise ValidationError(
            "Add at least one product before posting."
        )

    for item in items:
        if item.quantity <= 0:
            raise ValidationError(
                f"Quantity for {item.product.name} must be greater than zero."
            )

        if item.unit_cost < 0:
            raise ValidationError(
                f"Cost for {item.product.name} cannot be negative."
            )

        if item.stock_batch_id:
            raise ValidationError(
                f"{item.product.name} already has a stock batch."
            )

    subtotal = round_money(
        sum(
            (
                item.quantity * item.unit_cost
                for item in items
            ),
            Decimal("0.00"),
        )
    )

    additional_costs = round_money(
        purchase.transport_cost
        + purchase.loading_cost
        + purchase.other_cost
    )

    total_amount = round_money(
        subtotal
        + additional_costs
        - purchase.discount
    )

    if total_amount < Decimal("0.00"):
        raise ValidationError(
            "Purchase discount cannot exceed the purchase total."
        )

    if purchase.amount_paid > total_amount:
        raise ValidationError(
            "Amount paid cannot exceed the purchase total."
        )

    if total_amount <= Decimal("0.00"):
        raise ValidationError(
            "Purchase total must be greater than zero."
        )

    line_bases = [
        round_money(
            item.quantity * item.unit_cost
        )
        for item in items
    ]

    total_basis = sum(
        line_bases,
        Decimal("0.00"),
    )

    if total_basis <= Decimal("0.00"):
        line_bases = [
            item.quantity
            for item in items
        ]

        total_basis = sum(
            line_bases,
            Decimal("0.000"),
        )

    remaining_cost = total_amount

    purchase_datetime = timezone.make_aware(
        datetime.combine(
            purchase.purchase_date,
            time(hour=12),
        )
    )

    for index, item in enumerate(items):
        is_last_item = index == len(items) - 1

        if is_last_item:
            allocated_cost = remaining_cost
        else:
            allocated_cost = round_money(
                total_amount
                * line_bases[index]
                / total_basis
            )

            remaining_cost = round_money(
                remaining_cost - allocated_cost
            )

        effective_unit_cost = round_unit_cost(
            allocated_cost / item.quantity
        )

        stock_batch = create_stock_batch(
            product=item.product,
            supplier=purchase.supplier,
            quantity=item.quantity,
            unit_cost=effective_unit_cost,
            source_type=StockBatch.SourceType.PURCHASE,
            source_reference=purchase.purchase_number,
            user=user,
            received_at=purchase_datetime,
            notes=(
                f"Purchase from {purchase.supplier.name}"
            ),
        )

        item.allocated_cost = allocated_cost
        item.effective_unit_cost = effective_unit_cost
        item.stock_batch = stock_batch

        item.save(
            update_fields=[
                "allocated_cost",
                "effective_unit_cost",
                "stock_batch",
            ]
        )

    purchase.subtotal = subtotal
    purchase.total_amount = total_amount
    purchase.status = Purchase.Status.POSTED
    purchase.posted_by = user
    purchase.posted_at = timezone.now()

    purchase.save(
        update_fields=[
            "subtotal",
            "total_amount",
            "status",
            "posted_by",
            "posted_at",
            "updated_at",
        ]
    )

    return purchase