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
    Customer,
    CustomerPayment,
    CustomerPaymentAllocation,
)


ZERO_MONEY = Decimal("0.00")
MONEY_PLACES = Decimal("0.01")


def round_money(value):
    return Decimal(
        str(value or 0)
    ).quantize(
        MONEY_PLACES,
        rounding=ROUND_HALF_UP,
    )


def customer_current_debt(customer):
    from sales.models import (
        CustomerCuttingService,
        Sale,
    )

    remaining_opening_balance = max(
        customer.opening_balance
        - customer.opening_balance_paid,
        ZERO_MONEY,
    )

    sale_balance_expression = ExpressionWrapper(
        F("total_amount") - F("amount_paid"),
        output_field=DecimalField(
            max_digits=18,
            decimal_places=2,
        ),
    )

    sale_debt = (
        Sale.objects
        .filter(
            customer=customer,
            status=Sale.Status.COMPLETED,
        )
        .aggregate(
            total=Coalesce(
                Sum(sale_balance_expression),
                Value(ZERO_MONEY),
                output_field=DecimalField(
                    max_digits=18,
                    decimal_places=2,
                ),
            )
        )["total"]
    )

    cutting_balance_expression = (
        ExpressionWrapper(
            F("total_fee") - F("amount_paid"),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=2,
            ),
        )
    )

    cutting_debt = (
        CustomerCuttingService.objects
        .filter(
            sale__customer=customer,
            status=(
                CustomerCuttingService
                .Status
                .COMPLETED
            ),
        )
        .aggregate(
            total=Coalesce(
                Sum(cutting_balance_expression),
                Value(ZERO_MONEY),
                output_field=DecimalField(
                    max_digits=18,
                    decimal_places=2,
                ),
            )
        )["total"]
    )

    return round_money(
        remaining_opening_balance
        + sale_debt
        + cutting_debt
    )


@transaction.atomic
def post_customer_payment(
    *,
    customer_id,
    amount,
    payment_method,
    payment_date,
    reference,
    notes,
    user,
):
    from sales.models import (
        CustomerCuttingService,
        Sale,
    )

    customer = (
        Customer.objects
        .select_for_update()
        .get(pk=customer_id)
    )

    amount = round_money(amount)

    if amount <= ZERO_MONEY:
        raise ValidationError(
            "Payment amount must be greater than zero."
        )

    remaining_opening_balance = round_money(
        max(
            customer.opening_balance
            - customer.opening_balance_paid,
            ZERO_MONEY,
        )
    )

    outstanding_sales = list(
        Sale.objects
        .select_for_update()
        .filter(
            customer=customer,
            status=Sale.Status.COMPLETED,
            total_amount__gt=F("amount_paid"),
        )
        .order_by(
            "sale_date",
            "id",
        )
    )

    outstanding_cutting_services = list(
        CustomerCuttingService.objects
        .select_for_update()
        .filter(
            sale__customer=customer,
            status=(
                CustomerCuttingService
                .Status
                .COMPLETED
            ),
            total_fee__gt=F("amount_paid"),
        )
        .order_by(
            "service_date",
            "id",
        )
    )

    total_outstanding = (
        remaining_opening_balance
    )

    for sale in outstanding_sales:
        total_outstanding += max(
            sale.total_amount - sale.amount_paid,
            ZERO_MONEY,
        )

    for service in outstanding_cutting_services:
        total_outstanding += max(
            service.total_fee - service.amount_paid,
            ZERO_MONEY,
        )

    total_outstanding = round_money(
        total_outstanding
    )

    if total_outstanding <= ZERO_MONEY:
        raise ValidationError(
            "This customer has no outstanding balance."
        )

    if amount > total_outstanding:
        raise ValidationError(
            (
                f"Payment cannot exceed the outstanding "
                f"balance of TZS "
                f"{total_outstanding:,.2f}."
            )
        )

    payment = CustomerPayment.objects.create(
        customer=customer,
        payment_date=payment_date,
        amount=amount,
        payment_method=payment_method,
        reference=reference,
        notes=notes,
        status=CustomerPayment.Status.POSTED,
        created_by=user,
    )

    allocations = []
    remaining_payment = amount

    if (
        remaining_payment > ZERO_MONEY
        and remaining_opening_balance > ZERO_MONEY
    ):
        allocated_amount = min(
            remaining_payment,
            remaining_opening_balance,
        )

        allocated_amount = round_money(
            allocated_amount
        )

        customer.opening_balance_paid = round_money(
            customer.opening_balance_paid
            + allocated_amount
        )

        customer.save(
            update_fields=[
                "opening_balance_paid",
                "updated_at",
            ]
        )

        allocations.append(
            CustomerPaymentAllocation(
                payment=payment,
                allocation_type=(
                    CustomerPaymentAllocation
                    .AllocationType
                    .OPENING_BALANCE
                ),
                amount=allocated_amount,
            )
        )

        remaining_payment = round_money(
            remaining_payment
            - allocated_amount
        )

    obligations = []

    for sale in outstanding_sales:
        obligations.append(
            {
                "type": "sale",
                "date": sale.sale_date,
                "id": sale.id,
                "object": sale,
            }
        )

    for service in outstanding_cutting_services:
        obligations.append(
            {
                "type": "cutting_service",
                "date": service.service_date,
                "id": service.id,
                "object": service,
            }
        )

    obligations.sort(
        key=lambda entry: (
            entry["date"],
            entry["id"],
            entry["type"],
        )
    )

    for obligation in obligations:
        if remaining_payment <= ZERO_MONEY:
            break

        target = obligation["object"]

        if obligation["type"] == "sale":
            outstanding_amount = round_money(
                target.total_amount
                - target.amount_paid
            )
        else:
            outstanding_amount = round_money(
                target.total_fee
                - target.amount_paid
            )

        if outstanding_amount <= ZERO_MONEY:
            continue

        allocated_amount = min(
            remaining_payment,
            outstanding_amount,
        )

        allocated_amount = round_money(
            allocated_amount
        )

        if obligation["type"] == "sale":
            target.amount_paid = round_money(
                target.amount_paid
                + allocated_amount
            )

            target.save(
                update_fields=[
                    "amount_paid",
                    "updated_at",
                ]
            )

            allocations.append(
                CustomerPaymentAllocation(
                    payment=payment,
                    allocation_type=(
                        CustomerPaymentAllocation
                        .AllocationType
                        .SALE
                    ),
                    sale=target,
                    amount=allocated_amount,
                )
            )

        else:
            target.amount_paid = round_money(
                target.amount_paid
                + allocated_amount
            )

            target.save(
                update_fields=[
                    "amount_paid",
                    "updated_at",
                ]
            )

            allocations.append(
                CustomerPaymentAllocation(
                    payment=payment,
                    allocation_type=(
                        CustomerPaymentAllocation
                        .AllocationType
                        .CUTTING_SERVICE
                    ),
                    cutting_service=target,
                    amount=allocated_amount,
                )
            )

        remaining_payment = round_money(
            remaining_payment
            - allocated_amount
        )

    if remaining_payment > ZERO_MONEY:
        raise ValidationError(
            (
                "The payment could not be fully "
                "allocated to customer debt."
            )
        )

    CustomerPaymentAllocation.objects.bulk_create(
        allocations
    )

    return payment


@transaction.atomic
def cancel_customer_payment(
    *,
    payment_id,
    user,
    reason,
):
    payment = (
        CustomerPayment.objects
        .select_for_update()
        .select_related("customer")
        .get(pk=payment_id)
    )

    if payment.status != CustomerPayment.Status.POSTED:
        raise ValidationError(
            "Only posted payments can be cancelled."
        )

    reason = str(reason or "").strip()

    if not reason:
        raise ValidationError(
            "Enter a reason for cancelling this payment."
        )

    customer = (
        Customer.objects
        .select_for_update()
        .get(pk=payment.customer_id)
    )

    allocations = list(
        CustomerPaymentAllocation.objects
        .select_for_update()
        .select_related(
            "sale",
            "cutting_service",
        )
        .filter(payment=payment)
        .order_by("-id")
    )

    for allocation in allocations:
        if (
            allocation.allocation_type
            == CustomerPaymentAllocation
            .AllocationType
            .OPENING_BALANCE
        ):
            customer.opening_balance_paid = max(
                round_money(
                    customer.opening_balance_paid
                    - allocation.amount
                ),
                ZERO_MONEY,
            )

            customer.save(
                update_fields=[
                    "opening_balance_paid",
                    "updated_at",
                ]
            )

        elif (
            allocation.allocation_type
            == CustomerPaymentAllocation
            .AllocationType
            .SALE
        ):
            sale = allocation.sale

            sale.amount_paid = max(
                round_money(
                    sale.amount_paid
                    - allocation.amount
                ),
                ZERO_MONEY,
            )

            sale.save(
                update_fields=[
                    "amount_paid",
                    "updated_at",
                ]
            )

        elif (
            allocation.allocation_type
            == CustomerPaymentAllocation
            .AllocationType
            .CUTTING_SERVICE
        ):
            service = allocation.cutting_service

            service.amount_paid = max(
                round_money(
                    service.amount_paid
                    - allocation.amount
                ),
                ZERO_MONEY,
            )

            service.save(
                update_fields=[
                    "amount_paid",
                    "updated_at",
                ]
            )

    payment.status = CustomerPayment.Status.CANCELLED
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