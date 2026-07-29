import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


ZERO_MONEY = Decimal("0.00")


def generate_customer_code():
    random_part = uuid.uuid4().hex[:8].upper()

    return f"CUS-{random_part}"


def generate_customer_payment_number():
    date_part = timezone.localdate().strftime(
        "%Y%m%d"
    )

    random_part = uuid.uuid4().hex[:6].upper()

    return f"PAY-{date_part}-{random_part}"


class Customer(models.Model):
    customer_code = models.CharField(
        max_length=30,
        unique=True,
        default=generate_customer_code,
        editable=False,
        db_index=True,
    )

    name = models.CharField(
        max_length=150,
        db_index=True,
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
        db_index=True,
    )

    email = models.EmailField(
        blank=True,
    )

    address = models.TextField(
        blank=True,
    )

    opening_balance = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        blank=True,
        validators=[
            MinValueValidator(ZERO_MONEY),
        ],
        help_text=(
            "Amount the customer already owed before "
            "starting to use this system."
        ),
    )

    opening_balance_paid = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
        validators=[
            MinValueValidator(ZERO_MONEY),
        ],
    )

    credit_limit = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        blank=True,
        validators=[
            MinValueValidator(ZERO_MONEY),
        ],
        help_text=(
            "Maximum credit allowed for this customer. "
            "Enter zero for no configured limit."
        ),
    )

    notes = models.TextField(
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_customers",
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
            "name",
            "id",
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    opening_balance__gte=0
                ),
                name=(
                    "customer_opening_balance_gte_zero"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    opening_balance_paid__gte=0
                ),
                name=(
                    "customer_opening_paid_gte_zero"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    credit_limit__gte=0
                ),
                name=(
                    "customer_credit_limit_gte_zero"
                ),
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "name",
                    "phone",
                ],
                name="customer_name_phone_index",
            ),
        ]

    def __str__(self):
        if self.phone:
            return f"{self.name} - {self.phone}"

        return self.name

    @property
    def remaining_opening_balance(self):
        remaining = (
            self.opening_balance
            - self.opening_balance_paid
        )

        return max(
            remaining,
            ZERO_MONEY,
        )

    @property
    def current_debt(self):
        from .services import customer_current_debt

        return customer_current_debt(self)


class CustomerPayment(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = (
            "mobile_money",
            "Mobile money",
        )
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
        default=generate_customer_payment_number,
        editable=False,
        db_index=True,
    )

    customer = models.ForeignKey(
        Customer,
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
            MinValueValidator(
                Decimal("0.01")
            ),
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
        related_name="created_customer_payments",
    )

    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cancelled_customer_payments",
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
                name=(
                    "customer_payment_amount_gt_zero"
                ),
            ),
        ]

    def __str__(self):
        return self.payment_number


class CustomerPaymentAllocation(models.Model):
    class AllocationType(models.TextChoices):
        OPENING_BALANCE = (
            "opening_balance",
            "Opening balance",
        )
        SALE = "sale", "Credit sale"
        CUTTING_SERVICE = (
            "cutting_service",
            "Cutting service",
        )

    payment = models.ForeignKey(
        CustomerPayment,
        on_delete=models.CASCADE,
        related_name="allocations",
    )

    allocation_type = models.CharField(
        max_length=30,
        choices=AllocationType.choices,
    )

    sale = models.ForeignKey(
        "sales.Sale",
        on_delete=models.PROTECT,
        related_name="customer_payment_allocations",
        null=True,
        blank=True,
    )

    cutting_service = models.ForeignKey(
        "sales.CustomerCuttingService",
        on_delete=models.PROTECT,
        related_name="customer_payment_allocations",
        null=True,
        blank=True,
    )

    amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0.01")
            ),
        ],
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "id",
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name=(
                    "customer_payment_allocation_gt_zero"
                ),
            ),
        ]

    def __str__(self):
        return (
            f"{self.payment.payment_number} - "
            f"{self.get_allocation_type_display()}"
        )

    def clean(self):
        super().clean()

        if (
            self.allocation_type
            == self.AllocationType.OPENING_BALANCE
        ):
            if (
                self.sale_id
                or self.cutting_service_id
            ):
                raise ValidationError(
                    (
                        "Opening balance allocations "
                        "must not select a sale or "
                        "cutting service."
                    )
                )

        elif (
            self.allocation_type
            == self.AllocationType.SALE
        ):
            if not self.sale_id:
                raise ValidationError(
                    "Select the allocated sale."
                )

            if self.cutting_service_id:
                raise ValidationError(
                    (
                        "A sale allocation cannot also "
                        "select a cutting service."
                    )
                )

        elif (
            self.allocation_type
            == self.AllocationType.CUTTING_SERVICE
        ):
            if not self.cutting_service_id:
                raise ValidationError(
                    (
                        "Select the allocated cutting "
                        "service."
                    )
                )

            if self.sale_id:
                raise ValidationError(
                    (
                        "A cutting allocation cannot also "
                        "select a sale."
                    )
                )