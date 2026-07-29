import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from customers.models import Customer
from inventory.models import StockBatch
from products.models import Product


ZERO_MONEY = Decimal("0.00")
ZERO_COST = Decimal("0.0000")
ZERO_QUANTITY = Decimal("0.000")


def generate_sale_number():
    date_part = timezone.localdate().strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:6].upper()

    return f"SALE-{date_part}-{random_part}"

def generate_cutting_service_number():
    date_part = timezone.localdate().strftime(
        "%Y%m%d"
    )

    random_part = uuid.uuid4().hex[:6].upper()

    return f"CUT-{date_part}-{random_part}"


class Sale(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile money"
        BANK = "bank", "Bank transfer"
        CREDIT = "credit", "Credit"

    sale_number = models.CharField(
        max_length=40,
        unique=True,
        default=generate_sale_number,
        editable=False,
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="sales",
        null=True,
        blank=True,
    )

    sale_date = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )

    discount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        validators=[
            MinValueValidator(ZERO_MONEY),
        ],
    )

    subtotal = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
    )

    total_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
    )

    amount_tendered = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        validators=[
            MinValueValidator(ZERO_MONEY),
        ],
        help_text="Amount received from the customer.",
    )

    amount_paid = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
    )

    change_due = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
    )

    notes = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_sales",
    )

    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="completed_sales",
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-sale_date",
            "-id",
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(discount__gte=0),
                name="sale_discount_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gte=0),
                name="sale_subtotal_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(total_amount__gte=0),
                name="sale_total_amount_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(amount_tendered__gte=0),
                name="sale_amount_tendered_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(amount_paid__gte=0),
                name="sale_amount_paid_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(change_due__gte=0),
                name="sale_change_due_gte_zero",
            ),
        ]

    def __str__(self):
        return self.sale_number

    @property
    def calculated_subtotal(self):
        return sum(
            (
                item.calculated_line_total
                for item in self.items.all()
            ),
            ZERO_MONEY,
        )

    @property
    def calculated_total(self):
        total = (
            self.calculated_subtotal
            - self.discount
        )

        return max(
            total,
            ZERO_MONEY,
        )

    @property
    def current_subtotal(self):
        if self.status == self.Status.COMPLETED:
            return self.subtotal

        return self.calculated_subtotal

    @property
    def current_total(self):
        if self.status == self.Status.COMPLETED:
            return self.total_amount

        return self.calculated_total

    @property
    def balance_due(self):
        balance = (
            self.current_total
            - self.amount_paid
        )

        return max(
            balance,
            ZERO_MONEY,
        )

    @property
    def payment_status(self):
        if self.current_total <= ZERO_MONEY:
            return "Unpaid"

        if self.amount_paid <= ZERO_MONEY:
            return "Unpaid"

        if self.amount_paid >= self.current_total:
            return "Paid"

        return "Partial"

    @property
    def gross_profit(self):
        return sum(
            (
                item.profit_amount
                for item in self.items.all()
            ),
            ZERO_MONEY,
        )



    @property
    def total_cost(self):
      return sum(
        (
            item.cost_total
            for item in self.items.all()
        ),
        ZERO_MONEY,
    )


    @property
    def net_profit(self):
       return (
        self.gross_profit
        - self.discount
    )


class SaleItem(models.Model):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="sale_items",
    )

    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[
            MinValueValidator(
                Decimal("0.001")
            ),
        ],
    )

    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[
            MinValueValidator(ZERO_MONEY),
        ],
    )

    line_discount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO_MONEY,
        validators=[
            MinValueValidator(ZERO_MONEY),
        ],
    )

    line_total = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
    )

    cost_total = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
    )

    profit_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
    )

    notes = models.CharField(
        max_length=200,
        blank=True,
    )

    class Meta:
        ordering = ["id"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "sale",
                    "product",
                ],
                name="unique_product_per_sale",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="sale_item_quantity_gt_zero",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="sale_item_unit_price_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(line_discount__gte=0),
                name="sale_item_discount_gte_zero",
            ),
        ]

    def __str__(self):
        return (
            f"{self.sale.sale_number} - "
            f"{self.product.name}"
        )

    @property
    def gross_line_total(self):
        return (
            self.quantity
            * self.unit_price
        )

    @property
    def calculated_line_total(self):
        total = (
            self.gross_line_total
            - self.line_discount
        )

        return max(
            total,
            ZERO_MONEY,
        )


class SaleItemBatchUsage(models.Model):
    sale_item = models.ForeignKey(
        SaleItem,
        on_delete=models.CASCADE,
        related_name="batch_usages",
    )

    batch = models.ForeignKey(
        StockBatch,
        on_delete=models.PROTECT,
        related_name="sale_usages",
    )

    quantity_used = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[
            MinValueValidator(
                Decimal("0.001")
            ),
        ],
    )

    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        validators=[
            MinValueValidator(ZERO_COST),
        ],
    )

    total_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        validators=[
            MinValueValidator(ZERO_MONEY),
        ],
    )

    class Meta:
        ordering = [
            "batch__received_at",
            "batch_id",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "sale_item",
                    "batch",
                ],
                name="unique_batch_per_sale_item",
            ),
            models.CheckConstraint(
                condition=Q(
                    quantity_used__gt=0
                ),
                name=(
                    "sale_usage_quantity_gt_zero"
                ),
            ),
        ]

    def __str__(self):
        return (
            f"{self.sale_item.sale.sale_number} - "
            f"Batch {self.batch_id}"
        )


class CustomerCuttingService(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    cutting_number = models.CharField(
        max_length=40,
        unique=True,
        default=generate_cutting_service_number,
        editable=False,
        db_index=True,
    )

    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="cutting_services",
    )

    sale_item = models.ForeignKey(
        SaleItem,
        on_delete=models.PROTECT,
        related_name="cutting_services",
    )

    service_date = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    quantity_cut = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[
            MinValueValidator(
                Decimal("0.001")
            ),
        ],
        help_text=(
            "Number of sold Timber pieces receiving "
            "the cutting service."
        ),
    )

    number_of_cuts = models.PositiveIntegerField(
        validators=[
            MinValueValidator(1),
        ],
        help_text=(
            "Actual machine cuts performed. "
            "One board divided into four sections "
            "usually requires three cuts."
        ),
    )

    fee_per_cut = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO_MONEY,
        validators=[
            MinValueValidator(ZERO_MONEY),
        ],
    )

    total_fee = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
    )

    payment_method = models.CharField(
        max_length=30,
        choices=Sale.PaymentMethod.choices,
        default=Sale.PaymentMethod.CASH,
    )

    amount_tendered = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        validators=[
            MinValueValidator(ZERO_MONEY),
        ],
        help_text=(
            "Amount received specifically for "
            "the cutting service."
        ),
    )

    amount_paid = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
    )

    change_due = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
    )

    notes = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name=(
            "created_cutting_services"
        ),
    )

    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name=(
            "completed_cutting_services"
        ),
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-service_date",
            "-id",
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    quantity_cut__gt=0
                ),
                name=(
                    "cutting_quantity_cut_gt_zero"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    number_of_cuts__gt=0
                ),
                name=(
                    "cutting_number_of_cuts_gt_zero"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    fee_per_cut__gte=0
                ),
                name=(
                    "cutting_fee_per_cut_gte_zero"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    total_fee__gte=0
                ),
                name=(
                    "cutting_total_fee_gte_zero"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    amount_tendered__gte=0
                ),
                name=(
                    "cutting_tendered_gte_zero"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    amount_paid__gte=0
                ),
                name=(
                    "cutting_paid_gte_zero"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    change_due__gte=0
                ),
                name=(
                    "cutting_change_gte_zero"
                ),
            ),
        ]

    def __str__(self):
        return self.cutting_number

    @property
    def customer(self):
        return self.sale.customer

    @property
    def product(self):
        return self.sale_item.product

    @property
    def calculated_total_fee(self):
        number_of_cuts = Decimal(
            str(self.number_of_cuts or 0)
        )

        return (
            number_of_cuts
            * self.fee_per_cut
        )

    @property
    def current_total_fee(self):
        if self.status == self.Status.COMPLETED:
            return self.total_fee

        return self.calculated_total_fee

    @property
    def balance_due(self):
        balance = (
            self.current_total_fee
            - self.amount_paid
        )

        return max(
            balance,
            ZERO_MONEY,
        )

    @property
    def payment_status(self):
        if self.current_total_fee <= ZERO_MONEY:
            return "Free"

        if self.amount_paid <= ZERO_MONEY:
            return "Unpaid"

        if self.amount_paid >= self.current_total_fee:
            return "Paid"

        return "Partial"