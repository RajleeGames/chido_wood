from decimal import Decimal
from customers.services import customer_current_debt
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

from inventory.models import StockMovement
from inventory.services import (
    consume_stock_fifo,
    round_money,
)

from .models import (
    CustomerCuttingService,
    Sale,
    SaleItem,
    SaleItemBatchUsage,
)


ZERO_MONEY = Decimal("0.00")



@transaction.atomic
def complete_sale(
    *,
    sale_id,
    user,
):
    sale = (
        Sale.objects
        .select_for_update()
        .select_related("customer")
        .get(pk=sale_id)
    )

    if sale.status != Sale.Status.DRAFT:
        raise ValidationError(
            "Only draft sales can be completed."
        )

    items = list(
        SaleItem.objects
        .select_for_update()
        .select_related(
            "product",
            "product__category",
        )
        .filter(sale=sale)
        .order_by("id")
    )

    if not items:
        raise ValidationError(
            "Add at least one product before completing the sale."
        )

    if sale.discount < ZERO_MONEY:
        raise ValidationError(
            "Sale discount cannot be negative."
        )

    if sale.amount_tendered < ZERO_MONEY:
        raise ValidationError(
            "Amount received cannot be negative."
        )

    subtotal = ZERO_MONEY

    for item in items:
        product = item.product

        if not product.is_active:
            raise ValidationError(
                f"{product.name} is inactive."
            )

        if not product.track_stock:
            raise ValidationError(
                (
                    f"{product.name} is not configured "
                    f"for stock tracking."
                )
            )

        if item.quantity <= 0:
            raise ValidationError(
                (
                    f"Quantity for {product.name} "
                    f"must be greater than zero."
                )
            )

        if item.unit_price < ZERO_MONEY:
            raise ValidationError(
                (
                    f"Selling price for {product.name} "
                    f"cannot be negative."
                )
            )

        gross_line_total = round_money(
            item.quantity
            * item.unit_price
        )

        if item.line_discount < ZERO_MONEY:
            raise ValidationError(
                (
                    f"Discount for {product.name} "
                    f"cannot be negative."
                )
            )

        if item.line_discount > gross_line_total:
            raise ValidationError(
                (
                    f"Discount for {product.name} "
                    f"cannot exceed its line total."
                )
            )

        minimum_price = (
            product.minimum_selling_price
        )

        if (
            minimum_price is not None
            and minimum_price > ZERO_MONEY
            and item.unit_price < minimum_price
        ):
            raise ValidationError(
                (
                    f"{product.name} cannot be sold below "
                    f"TZS {minimum_price:,.2f}."
                )
            )

        line_total = round_money(
            gross_line_total
            - item.line_discount
        )

        subtotal += line_total

    subtotal = round_money(
        subtotal
    )

    if sale.discount > subtotal:
        raise ValidationError(
            "Sale discount cannot exceed the subtotal."
        )

    total_amount = round_money(
        subtotal - sale.discount
    )

    if total_amount <= ZERO_MONEY:
        raise ValidationError(
            "Sale total must be greater than zero."
        )

    if (
        sale.payment_method
        == Sale.PaymentMethod.CASH
    ):
        amount_paid = min(
            sale.amount_tendered,
            total_amount,
        )

        change_due = max(
            sale.amount_tendered
            - total_amount,
            ZERO_MONEY,
        )

    else:
        if sale.amount_tendered > total_amount:
            raise ValidationError(
                (
                    "Amount received cannot exceed the "
                    "sale total for this payment method."
                )
            )

        amount_paid = sale.amount_tendered
        change_due = ZERO_MONEY

    amount_paid = round_money(
        amount_paid
    )

    change_due = round_money(
        change_due
    )

    balance_due = round_money(
        total_amount - amount_paid
    )

    if (
        sale.payment_method
        == Sale.PaymentMethod.CREDIT
        and sale.customer is None
    ):
        raise ValidationError(
            "Select a customer for a credit sale."
        )

    if (
        balance_due > ZERO_MONEY
        and sale.customer is None
    ):
        raise ValidationError(
            (
                "Select a customer when the full sale "
                "amount has not been paid."
            )
        )

    if (
        sale.customer
        and balance_due > ZERO_MONEY
        and sale.customer.credit_limit > ZERO_MONEY
    ):
        existing_debt = customer_current_debt(
            sale.customer
        )

        projected_debt = round_money(
            existing_debt + balance_due
        )

        if (
            projected_debt
            > sale.customer.credit_limit
        ):
            raise ValidationError(
                (
                    f"{sale.customer.name}'s credit limit "
                    f"would be exceeded. Current debt: "
                    f"TZS {existing_debt:,.2f}. "
                    f"New balance: TZS {balance_due:,.2f}. "
                    f"Credit limit: "
                    f"TZS {sale.customer.credit_limit:,.2f}."
                )
            )

    for item in items:
        total_cost, allocations = consume_stock_fifo(
            product=item.product,
            quantity=item.quantity,
            movement_type=(
                StockMovement.MovementType.SALE
            ),
            reference=sale.sale_number,
            notes=(
                f"Product sold through "
                f"{sale.sale_number}"
            ),
            user=user,
        )

        SaleItemBatchUsage.objects.bulk_create(
            [
                SaleItemBatchUsage(
                    sale_item=item,
                    batch=allocation["batch"],
                    quantity_used=allocation[
                        "quantity"
                    ],
                    unit_cost=allocation[
                        "unit_cost"
                    ],
                    total_cost=allocation[
                        "total_cost"
                    ],
                )
                for allocation in allocations
            ]
        )

        line_total = round_money(
            item.quantity
            * item.unit_price
            - item.line_discount
        )

        item.line_total = line_total
        item.cost_total = total_cost
        item.profit_amount = round_money(
            line_total - total_cost
        )

        item.save(
            update_fields=[
                "line_total",
                "cost_total",
                "profit_amount",
            ]
        )

    sale.subtotal = subtotal
    sale.total_amount = total_amount
    sale.amount_paid = amount_paid
    sale.change_due = change_due
    sale.status = Sale.Status.COMPLETED
    sale.completed_by = user
    sale.completed_at = timezone.now()

    sale.save(
        update_fields=[
            "subtotal",
            "total_amount",
            "amount_paid",
            "change_due",
            "status",
            "completed_by",
            "completed_at",
            "updated_at",
        ]
    )

    return sale


@transaction.atomic
def complete_customer_cutting_service(
    *,
    cutting_service_id,
    user,
):
    cutting_service = (
        CustomerCuttingService.objects
        .select_for_update()
        .select_related(
            "sale",
            "sale__customer",
            "sale_item",
            "sale_item__product",
            "sale_item__product__category",
        )
        .get(pk=cutting_service_id)
    )

    if (
        cutting_service.status
        != CustomerCuttingService.Status.DRAFT
    ):
        raise ValidationError(
            (
                "Only draft cutting services "
                "can be completed."
            )
        )

    sale = cutting_service.sale
    sale_item = cutting_service.sale_item
    product = sale_item.product

    if sale.status != Sale.Status.COMPLETED:
        raise ValidationError(
            (
                "Customer cutting can only be "
                "recorded for a completed sale."
            )
        )

    if sale_item.sale_id != sale.id:
        raise ValidationError(
            (
                "The selected product does "
                "not belong to this sale."
            )
        )

    # Customer cutting is controlled by the
    # product's "Allow Customer Cutting" setting.
    allows_cutting = getattr(
        product,
        "allow_customer_cutting",
        False,
    )

    if not allows_cutting:
        raise ValidationError(
            (
                f"{product.name} does not allow "
                f"customer cutting."
            )
        )

    if cutting_service.quantity_cut <= 0:
        raise ValidationError(
            (
                "Quantity receiving cutting must "
                "be greater than zero."
            )
        )

    if (
        cutting_service.quantity_cut
        > sale_item.quantity
    ):
        raise ValidationError(
            (
                f"Only {sale_item.quantity} pieces "
                f"were sold."
            )
        )

    if cutting_service.number_of_cuts <= 0:
        raise ValidationError(
            (
                "Number of cuts must be "
                "greater than zero."
            )
        )

    if cutting_service.fee_per_cut < ZERO_MONEY:
        raise ValidationError(
            "Cutting fee cannot be negative."
        )

    completed_quantity = (
        CustomerCuttingService.objects
        .select_for_update()
        .filter(
            sale_item=sale_item,
            status=(
                CustomerCuttingService
                .Status
                .COMPLETED
            ),
        )
        .exclude(
            pk=cutting_service.pk
        )
        .aggregate(
            total=Coalesce(
                Sum("quantity_cut"),
                Value(
                    Decimal("0.000")
                ),
                output_field=DecimalField(
                    max_digits=16,
                    decimal_places=3,
                ),
            )
        )["total"]
    )

    projected_quantity = (
        completed_quantity
        + cutting_service.quantity_cut
    )

    if projected_quantity > sale_item.quantity:
        remaining_quantity = (
            sale_item.quantity
            - completed_quantity
        )

        raise ValidationError(
            (
                f"Only {remaining_quantity} "
                f"uncut sold pieces remain."
            )
        )

    total_fee = round_money(
        Decimal(
            cutting_service.number_of_cuts
        )
        * cutting_service.fee_per_cut
    )

    amount_tendered = round_money(
        cutting_service.amount_tendered
    )

    if (
        cutting_service.payment_method
        == Sale.PaymentMethod.CASH
    ):
        amount_paid = min(
            amount_tendered,
            total_fee,
        )

        change_due = max(
            amount_tendered
            - total_fee,
            ZERO_MONEY,
        )

    else:
        if amount_tendered > total_fee:
            raise ValidationError(
                (
                    "Amount received cannot exceed "
                    "the cutting fee for this "
                    "payment method."
                )
            )

        amount_paid = amount_tendered
        change_due = ZERO_MONEY

    amount_paid = round_money(
        amount_paid
    )

    change_due = round_money(
        change_due
    )

    balance_due = round_money(
        total_fee - amount_paid
    )

    if (
        cutting_service.payment_method
        == Sale.PaymentMethod.CREDIT
        and sale.customer is None
    ):
        raise ValidationError(
            (
                "The original sale must have a "
                "registered customer for credit "
                "cutting."
            )
        )

    if (
        balance_due > ZERO_MONEY
        and sale.customer is None
    ):
        raise ValidationError(
            (
                "Select a registered customer on "
                "the original sale because the "
                "cutting fee is not fully paid."
            )
        )

    if (
        sale.customer
        and balance_due > ZERO_MONEY
        and sale.customer.credit_limit > ZERO_MONEY
    ):
        existing_debt = customer_current_debt(
            sale.customer
        )

        projected_debt = round_money(
            existing_debt
            + balance_due
        )

        if (
            projected_debt
            > sale.customer.credit_limit
        ):
            raise ValidationError(
                (
                    f"{sale.customer.name}'s credit "
                    f"limit would be exceeded. "
                    f"Current debt: "
                    f"TZS {existing_debt:,.2f}. "
                    f"Cutting balance: "
                    f"TZS {balance_due:,.2f}. "
                    f"Credit limit: "
                    f"TZS "
                    f"{sale.customer.credit_limit:,.2f}."
                )
            )

    cutting_service.total_fee = total_fee
    cutting_service.amount_paid = amount_paid
    cutting_service.change_due = change_due
    cutting_service.status = (
        CustomerCuttingService.Status.COMPLETED
    )
    cutting_service.completed_by = user
    cutting_service.completed_at = (
        timezone.now()
    )

    cutting_service.save(
        update_fields=[
            "total_fee",
            "amount_paid",
            "change_due",
            "status",
            "completed_by",
            "completed_at",
            "updated_at",
        ]
    )

    # No stock is consumed here.
    # The original completed sale already removed stock.

    return cutting_service