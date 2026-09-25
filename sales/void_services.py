from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from customers.models import (
    CustomerPayment,
    CustomerPaymentAllocation,
)
from inventory.models import (
    StockBatch,
    StockMovement,
)
from inventory.services import round_quantity

from .models import (
    CustomerCuttingService,
    Sale,
    SaleItem,
    SaleItemBatchUsage,
)


ZERO_QUANTITY = Decimal("0.000")


def _user_can_void_sale(user):
    return bool(
        user
        and user.is_authenticated
        and getattr(
            user,
            "is_admin_user",
            False,
        )
    )


@transaction.atomic
def void_completed_sale(
    *,
    sale_id,
    user,
    reason,
):
    """
    Void one completed sale safely.

    The original sale and FIFO usage records are kept
    for audit purposes. Stock is restored into the exact
    batches originally consumed by the sale and matching
    REVERSAL_IN movements are created.

    Important safety rules:
    - Only an Administrator or Django superuser can void.
    - Only COMPLETED sales can be voided.
    - A reason is mandatory.
    - Linked draft/completed cutting services are also
      cancelled so their income/debt is removed with the sale.
    - A sale or linked cutting service with a POSTED customer
      account payment allocated to it cannot be voided until
      that payment is cancelled, otherwise the customer ledger
      would become inconsistent.
    """

    if not _user_can_void_sale(user):
        raise ValidationError(
            (
                "Only an Administrator or superuser "
                "can void a completed sale."
            )
        )

    reason = str(
        reason or ""
    ).strip()

    if len(reason) < 3:
        raise ValidationError(
            (
                "Enter a clear reason for voiding "
                "this sale."
            )
        )

    sale = (
        Sale.objects
        .select_for_update()
        .select_related(
            "customer",
            "created_by",
            "completed_by",
        )
        .get(pk=sale_id)
    )

    if sale.status != Sale.Status.COMPLETED:
        raise ValidationError(
            "Only a completed sale can be voided."
        )

    linked_cutting_services = list(
        CustomerCuttingService.objects
        .select_for_update()
        .filter(sale=sale)
        .order_by("id")
    )

    cutting_service_ids = [
        service.id
        for service in linked_cutting_services
    ]

    sale_payment_numbers = list(
        sale.customer_payment_allocations
        .filter(
            payment__status=(
                CustomerPayment.Status.POSTED
            )
        )
        .values_list(
            "payment__payment_number",
            flat=True,
        )
        .distinct()
    )

    cutting_payment_numbers = []

    if cutting_service_ids:
        cutting_payment_numbers = list(
            CustomerPaymentAllocation.objects
            .filter(
                cutting_service_id__in=(
                    cutting_service_ids
                ),
                payment__status=(
                    CustomerPayment.Status.POSTED
                ),
            )
            .values_list(
                "payment__payment_number",
                flat=True,
            )
            .distinct()
        )

    posted_payment_numbers = sorted(
        set(
            sale_payment_numbers
            + cutting_payment_numbers
        )
    )

    if posted_payment_numbers:
        shown_numbers = (
            posted_payment_numbers[:5]
        )

        payment_text = ", ".join(
            shown_numbers
        )

        if len(posted_payment_numbers) > 5:
            payment_text = (
                f"{payment_text}, ..."
            )

        raise ValidationError(
            (
                "This sale or one of its cutting "
                "services has a posted customer "
                "payment allocated to it. Cancel the "
                "customer payment first, then void "
                f"the sale. Payment: {payment_text}"
            )
        )

    items = list(
        SaleItem.objects
        .select_for_update()
        .select_related("product")
        .filter(sale=sale)
        .order_by("id")
    )

    if not items:
        raise ValidationError(
            (
                "This completed sale has no sale items. "
                "Void was stopped to protect stock data."
            )
        )

    usages = list(
        SaleItemBatchUsage.objects
        .select_for_update()
        .select_related(
            "sale_item",
            "sale_item__product",
            "batch",
        )
        .filter(
            sale_item__sale=sale
        )
        .order_by(
            "sale_item_id",
            "id",
        )
    )

    usages_by_item = {}

    for usage in usages:
        usages_by_item.setdefault(
            usage.sale_item_id,
            [],
        ).append(usage)

    for item in items:
        item_usages = usages_by_item.get(
            item.id,
            [],
        )

        used_quantity = sum(
            (
                usage.quantity_used
                for usage in item_usages
            ),
            ZERO_QUANTITY,
        )

        if (
            round_quantity(used_quantity)
            != round_quantity(item.quantity)
        ):
            raise ValidationError(
                (
                    "FIFO audit data does not match the "
                    f"sold quantity for "
                    f"{item.product.name}. "
                    "Void was stopped so stock is not "
                    "restored incorrectly."
                )
            )

    batch_ids = {
        usage.batch_id
        for usage in usages
    }

    locked_batches = {
        batch.id: batch
        for batch in (
            StockBatch.objects
            .select_for_update()
            .filter(pk__in=batch_ids)
        )
    }

    if len(locked_batches) != len(batch_ids):
        raise ValidationError(
            (
                "One or more FIFO stock batches used "
                "by this sale are missing."
            )
        )

    voided_at = timezone.now()

    for usage in usages:
        batch = locked_batches[
            usage.batch_id
        ]

        restored_quantity = round_quantity(
            batch.remaining_quantity
            + usage.quantity_used
        )

        if (
            restored_quantity
            > batch.received_quantity
        ):
            raise ValidationError(
                (
                    f"Restoring batch #{batch.id} would "
                    "increase its stock above the "
                    "original received quantity. "
                    "Void was stopped because the stock "
                    "audit trail is inconsistent."
                )
            )

        batch.remaining_quantity = (
            restored_quantity
        )

        batch.save(
            update_fields=[
                "remaining_quantity",
            ]
        )

        StockMovement.objects.create(
            product=usage.sale_item.product,
            batch=batch,
            movement_type=(
                StockMovement
                .MovementType
                .REVERSAL_IN
            ),
            quantity_delta=(
                usage.quantity_used
            ),
            unit_cost=usage.unit_cost,
            total_cost=usage.total_cost,
            reference=(
                f"VOID:{sale.sale_number}"
            ),
            notes=(
                f"Stock restored because sale "
                f"{sale.sale_number} was voided. "
                f"Reason: {reason}"
            ),
            created_by=user,
        )

    for cutting_service in linked_cutting_services:
        if (
            cutting_service.status
            == CustomerCuttingService
            .Status
            .CANCELLED
        ):
            continue

        audit_note = (
            f"Automatically cancelled because sale "
            f"{sale.sale_number} was voided. "
            f"Reason: {reason}"
        )

        existing_notes = str(
            cutting_service.notes or ""
        ).strip()

        if existing_notes:
            cutting_service.notes = (
                f"{existing_notes}\n\n"
                f"{audit_note}"
            )
        else:
            cutting_service.notes = audit_note

        cutting_service.status = (
            CustomerCuttingService
            .Status
            .CANCELLED
        )

        cutting_service.save(
            update_fields=[
                "status",
                "notes",
                "updated_at",
            ]
        )

    sale.status = Sale.Status.VOIDED
    sale.voided_by = user
    sale.voided_at = voided_at
    sale.void_reason = reason

    sale.save(
        update_fields=[
            "status",
            "voided_by",
            "voided_at",
            "void_reason",
            "updated_at",
        ]
    )

    return sale
