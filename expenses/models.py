import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


ZERO_MONEY = Decimal("0.00")


def generate_expense_number():
    date_part = timezone.localdate().strftime(
        "%Y%m%d"
    )

    random_part = uuid.uuid4().hex[:6].upper()

    return f"EXP-{date_part}-{random_part}"


class ExpenseCategory(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
    )

    code = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
    )

    description = models.TextField(
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
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

        verbose_name_plural = (
            "Expense categories"
        )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = str(
            self.name or ""
        ).strip()

        self.code = (
            str(self.code or "")
            .strip()
            .upper()
            .replace(" ", "_")
        )

        super().save(
            *args,
            **kwargs,
        )


class Expense(models.Model):
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
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        CANCELLED = "cancelled", "Cancelled"

    expense_number = models.CharField(
        max_length=40,
        unique=True,
        default=generate_expense_number,
        editable=False,
        db_index=True,
    )

    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name="expenses",
    )

    expense_date = models.DateField(
        default=timezone.localdate,
        db_index=True,
    )

    description = models.CharField(
        max_length=200,
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

    payee = models.CharField(
        max_length=150,
        blank=True,
        help_text=(
            "Person or company that received "
            "the payment."
        ),
    )

    reference = models.CharField(
        max_length=120,
        blank=True,
        help_text=(
            "Receipt, transaction or bank "
            "reference."
        ),
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
        related_name="created_expenses",
    )

    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="posted_expenses",
        null=True,
        blank=True,
    )

    posted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cancelled_expenses",
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
            "-expense_date",
            "-id",
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="expense_amount_gt_zero",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "status",
                    "expense_date",
                ],
                name="expense_status_date_idx",
            ),
        ]

    def __str__(self):
        return self.expense_number