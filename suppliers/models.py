import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


ZERO_MONEY = Decimal("0.00")


def generate_supplier_payment_number():
    date_part = timezone.localdate().strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:6].upper()
    return f"SPAY-{date_part}-{random_part}"


class Supplier(models.Model):
    name = models.CharField(
        max_length=180,
        unique=True,
    )

    contact_person = models.CharField(
        max_length=150,
        blank=True,
    )

    phone = models.CharField(
        max_length=40,
        blank=True,
    )

    email = models.EmailField(
        blank=True,
    )

    address = models.TextField(
        blank=True,
    )

    tin = models.CharField(
        max_length=50,
        blank=True,
    )

    opening_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO_MONEY,
        validators=[
            MinValueValidator(ZERO_MONEY),
        ],
    )

    opening_balance_paid = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
        validators=[
            MinValueValidator(ZERO_MONEY),
        ],
    )

    notes = models.TextField(
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(opening_balance__gte=0),
                name="supplier_opening_balance_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(opening_balance_paid__gte=0),
                name="supplier_opening_paid_gte_zero",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def remaining_opening_balance(self):
        return max(
            self.opening_balance - self.opening_balance_paid,
            ZERO_MONEY,
        )

    @property
    def current_debt(self):
        from .services import supplier_current_debt

        return supplier_current_debt(self)


class SupplierPayment(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile money"
        BANK = "bank", "Bank transfer"
        CARD = "card", "Card"
        CHEQUE = "cheque", "Cheque"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        POSTED = "posted", "Posted"
        CANCELLED = "cancelled", "Cancelled"

    payment_number = models.CharField(
        max_length=40,
        unique=True,
        default=generate_supplier_payment_number,
        editable=False,
        db_index=True,
    )

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="account_payments",
    )

    payment_date = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01")),
        ],
    )

    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )

    reference = models.CharField(
        max_length=120,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.POSTED,
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_supplier_payments",
    )

    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cancelled_supplier_payments",
        null=True,
        blank=True,
    )

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    cancellation_reason = models.TextField(
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
            "-payment_date",
            "-id",
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="supplier_payment_amount_gt_zero",
            ),
        ]

    def __str__(self):
        return self.payment_number


class SupplierPaymentAllocation(models.Model):
    class AllocationType(models.TextChoices):
        OPENING_BALANCE = "opening_balance", "Opening balance"
        PURCHASE = "purchase", "Purchase"

    payment = models.ForeignKey(
        SupplierPayment,
        on_delete=models.CASCADE,
        related_name="allocations",
    )

    allocation_type = models.CharField(
        max_length=30,
        choices=AllocationType.choices,
    )

    purchase = models.ForeignKey(
        "purchases.Purchase",
        on_delete=models.PROTECT,
        related_name="supplier_payment_allocations",
        null=True,
        blank=True,
    )

    amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01")),
        ],
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="supplier_payment_allocation_gt_zero",
            ),
        ]

    def __str__(self):
        return (
            f"{self.payment.payment_number} - "
            f"{self.get_allocation_type_display()}"
        )

    def clean(self):
        super().clean()

        if self.allocation_type == self.AllocationType.OPENING_BALANCE:
            if self.purchase_id:
                raise ValidationError(
                    "Opening balance allocations must not select a purchase."
                )

        elif self.allocation_type == self.AllocationType.PURCHASE:
            if not self.purchase_id:
                raise ValidationError(
                    "Select the purchase receiving this allocation."
                )
