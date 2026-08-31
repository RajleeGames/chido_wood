from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import (
    Supplier,
    SupplierPayment,
    SupplierPaymentAllocation,
)


ZERO_MONEY = Decimal("0.00")
MONEY_PLACES = Decimal("0.01")


def round_money(value):
    return Decimal(str(value or 0)).quantize(
        MONEY_PLACES,
        rounding=ROUND_HALF_UP,
    )


def supplier_current_debt(supplier):
    from purchases.models import Purchase

    remaining_opening_balance = max(
        supplier.opening_balance - supplier.opening_balance_paid,
        ZERO_MONEY,
    )

    purchase_balance_expression = ExpressionWrapper(
        F("total_amount") - F("amount_paid"),
        output_field=DecimalField(
            max_digits=18,
            decimal_places=2,
        ),
    )

    purchase_debt = (
        Purchase.objects
        .filter(
            supplier=supplier,
            status=Purchase.Status.POSTED,
        )
        .aggregate(
            total=Coalesce(
                Sum(purchase_balance_expression),
                Value(ZERO_MONEY),
                output_field=DecimalField(
                    max_digits=18,
                    decimal_places=2,
                ),
            )
        )["total"]
    )

    return round_money(
        remaining_opening_balance + purchase_debt
    )


@transaction.atomic
def post_supplier_payment(
    *,
    supplier_id,
    amount,
    payment_method,
    payment_date,
    reference,
    notes,
    user,
):
    from purchases.models import Purchase

    supplier = (
        Supplier.objects
        .select_for_update()
        .get(pk=supplier_id)
    )

    amount = round_money(amount)

    if amount <= ZERO_MONEY:
        raise ValidationError(
            "Payment amount must be greater than zero."
        )

    remaining_opening_balance = round_money(
        max(
            supplier.opening_balance - supplier.opening_balance_paid,
            ZERO_MONEY,
        )
    )

    outstanding_purchases = list(
        Purchase.objects
        .select_for_update()
        .filter(
            supplier=supplier,
            status=Purchase.Status.POSTED,
            total_amount__gt=F("amount_paid"),
        )
        .order_by(
            "purchase_date",
            "id",
        )
    )

    total_outstanding = remaining_opening_balance

    for purchase in outstanding_purchases:
        total_outstanding += max(
            purchase.total_amount - purchase.amount_paid,
            ZERO_MONEY,
        )

    total_outstanding = round_money(total_outstanding)

    if total_outstanding <= ZERO_MONEY:
        raise ValidationError(
            "This supplier has no outstanding balance."
        )

    if amount > total_outstanding:
        raise ValidationError(
            (
                "Payment cannot exceed the outstanding balance of "
                f"TZS {total_outstanding:,.2f}."
            )
        )

    payment = SupplierPayment.objects.create(
        supplier=supplier,
        payment_date=payment_date,
        amount=amount,
        payment_method=payment_method,
        reference=reference,
        notes=notes,
        status=SupplierPayment.Status.POSTED,
        created_by=user,
    )

    allocations = []
    remaining_payment = amount

    if (
        remaining_payment > ZERO_MONEY
        and remaining_opening_balance > ZERO_MONEY
    ):
        allocated_amount = round_money(
            min(
                remaining_payment,
                remaining_opening_balance,
            )
        )

        supplier.opening_balance_paid = round_money(
            supplier.opening_balance_paid + allocated_amount
        )
        supplier.save(
            update_fields=[
                "opening_balance_paid",
                "updated_at",
            ]
        )

        allocations.append(
            SupplierPaymentAllocation(
                payment=payment,
                allocation_type=(
                    SupplierPaymentAllocation
                    .AllocationType
                    .OPENING_BALANCE
                ),
                amount=allocated_amount,
            )
        )

        remaining_payment = round_money(
            remaining_payment - allocated_amount
        )

    for purchase in outstanding_purchases:
        if remaining_payment <= ZERO_MONEY:
            break

        outstanding_amount = round_money(
            purchase.total_amount - purchase.amount_paid
        )

        if outstanding_amount <= ZERO_MONEY:
            continue

        allocated_amount = round_money(
            min(
                remaining_payment,
                outstanding_amount,
            )
        )

        purchase.amount_paid = round_money(
            purchase.amount_paid + allocated_amount
        )
        purchase.save(
            update_fields=[
                "amount_paid",
                "updated_at",
            ]
        )

        allocations.append(
            SupplierPaymentAllocation(
                payment=payment,
                allocation_type=(
                    SupplierPaymentAllocation
                    .AllocationType
                    .PURCHASE
                ),
                purchase=purchase,
                amount=allocated_amount,
            )
        )

        remaining_payment = round_money(
            remaining_payment - allocated_amount
        )

    if remaining_payment > ZERO_MONEY:
        raise ValidationError(
            "The payment could not be fully allocated to supplier debt."
        )

    SupplierPaymentAllocation.objects.bulk_create(allocations)

    return payment


@transaction.atomic
def cancel_supplier_payment(
    *,
    payment_id,
    user,
    reason,
):
    payment = (
        SupplierPayment.objects
        .select_for_update()
        .select_related("supplier")
        .get(pk=payment_id)
    )

    if payment.status != SupplierPayment.Status.POSTED:
        raise ValidationError(
            "Only posted supplier payments can be cancelled."
        )

    reason = str(reason or "").strip()

    if not reason:
        raise ValidationError(
            "Enter a reason for cancelling this payment."
        )

    supplier = (
        Supplier.objects
        .select_for_update()
        .get(pk=payment.supplier_id)
    )

    allocations = list(
        SupplierPaymentAllocation.objects
        .select_for_update()
        .select_related("purchase")
        .filter(payment=payment)
        .order_by("-id")
    )

    for allocation in allocations:
        if (
            allocation.allocation_type
            == SupplierPaymentAllocation.AllocationType.OPENING_BALANCE
        ):
            supplier.opening_balance_paid = max(
                round_money(
                    supplier.opening_balance_paid - allocation.amount
                ),
                ZERO_MONEY,
            )
            supplier.save(
                update_fields=[
                    "opening_balance_paid",
                    "updated_at",
                ]
            )

        elif (
            allocation.allocation_type
            == SupplierPaymentAllocation.AllocationType.PURCHASE
        ):
            purchase = allocation.purchase

            purchase.amount_paid = max(
                round_money(
                    purchase.amount_paid - allocation.amount
                ),
                ZERO_MONEY,
            )
            purchase.save(
                update_fields=[
                    "amount_paid",
                    "updated_at",
                ]
            )

    payment.status = SupplierPayment.Status.CANCELLED
    payment.cancelled_by = user
    payment.cancelled_at = timezone.now()
    payment.cancellation_reason = reason
    payment.save(
        update_fields=[
            "status",
            "cancelled_by",
            "cancelled_at",
            "cancellation_reason",
            "updated_at",
        ]
    )

    return payment
