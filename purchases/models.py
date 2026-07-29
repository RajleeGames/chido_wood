import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from inventory.models import StockBatch
from products.models import Product
from suppliers.models import Supplier


ZERO_MONEY = Decimal("0.00")
ZERO_QUANTITY = Decimal("0.000")
ZERO_COST = Decimal("0.0000")


def generate_purchase_number():
    date_part = timezone.localdate().strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:6].upper()

    return f"PUR-{date_part}-{random_part}"


class Purchase(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile money"
        BANK = "bank", "Bank"
        CREDIT = "credit", "Credit"
        MIXED = "mixed", "Mixed"

    purchase_number = models.CharField(
        max_length=40,
        unique=True,
        default=generate_purchase_number,
        editable=False,
    )

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="purchases",
    )

    supplier_invoice_number = models.CharField(
        max_length=100,
        blank=True,
    )

    purchase_date = models.DateField(
        default=timezone.localdate,
        db_index=True,
    )

    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )

    amount_paid = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
    )

    transport_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
    )

    loading_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
    )

    other_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
    )

    discount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
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
        related_name="created_purchases",
    )

    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="posted_purchases",
        null=True,
        blank=True,
    )

    posted_at = models.DateTimeField(
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
            "-purchase_date",
            "-id",
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(amount_paid__gte=0),
                name="purchase_amount_paid_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(transport_cost__gte=0),
                name="purchase_transport_cost_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(loading_cost__gte=0),
                name="purchase_loading_cost_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(other_cost__gte=0),
                name="purchase_other_cost_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(discount__gte=0),
                name="purchase_discount_gte_zero",
            ),
        ]

    def __str__(self):
        return self.purchase_number

    @property
    def additional_costs(self):
        return (
            self.transport_cost
            + self.loading_cost
            + self.other_cost
        )

    @property
    def calculated_subtotal(self):
        return sum(
            (
                item.line_total
                for item in self.items.all()
            ),
            Decimal("0.00"),
        )

    @property
    def calculated_total(self):
        total = (
            self.calculated_subtotal
            + self.additional_costs
            - self.discount
        )

        return max(total, Decimal("0.00"))

    @property
    def current_subtotal(self):
        if self.status == self.Status.POSTED:
            return self.subtotal

        return self.calculated_subtotal

    @property
    def current_total(self):
        if self.status == self.Status.POSTED:
            return self.total_amount

        return self.calculated_total

    @property
    def balance_due(self):
        balance = self.current_total - self.amount_paid

        return max(balance, Decimal("0.00"))

    @property
    def payment_status(self):
        if self.current_total <= Decimal("0.00"):
            return "Unpaid"

        if self.amount_paid <= Decimal("0.00"):
            return "Unpaid"

        if self.amount_paid >= self.current_total:
            return "Paid"

        return "Partial"


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="purchase_items",
    )

    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[
            MinValueValidator(Decimal("0.001")),
        ],
    )

    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        validators=[
            MinValueValidator(ZERO_COST),
        ],
        help_text="Supplier price before additional costs.",
    )

    allocated_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
    )

    effective_unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=ZERO_COST,
        editable=False,
    )

    stock_batch = models.OneToOneField(
        StockBatch,
        on_delete=models.PROTECT,
        related_name="purchase_item",
        null=True,
        blank=True,
        editable=False,
    )

    notes = models.CharField(
        max_length=200,
        blank=True,
    )

    class Meta:
        ordering = ["id"]

        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="purchase_item_quantity_gt_zero",
            ),
            models.CheckConstraint(
                condition=Q(unit_cost__gte=0),
                name="purchase_item_unit_cost_gte_zero",
            ),
        ]

    def __str__(self):
        return (
            f"{self.purchase.purchase_number} - "
            f"{self.product.name}"
        )

    @property
    def line_total(self):
        return self.quantity * self.unit_cost