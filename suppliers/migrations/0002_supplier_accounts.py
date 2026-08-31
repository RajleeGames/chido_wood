from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

import suppliers.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("purchases", "0001_initial"),
        ("suppliers", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="supplier",
            name="opening_balance_paid",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                editable=False,
                max_digits=14,
                validators=[MinValueValidator(Decimal("0.00"))],
            ),
        ),
        migrations.AddConstraint(
            model_name="supplier",
            constraint=models.CheckConstraint(
                condition=models.Q(("opening_balance__gte", 0)),
                name="supplier_opening_balance_gte_zero",
            ),
        ),
        migrations.AddConstraint(
            model_name="supplier",
            constraint=models.CheckConstraint(
                condition=models.Q(("opening_balance_paid__gte", 0)),
                name="supplier_opening_paid_gte_zero",
            ),
        ),
        migrations.CreateModel(
            name="SupplierPayment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "payment_number",
                    models.CharField(
                        db_index=True,
                        default=suppliers.models.generate_supplier_payment_number,
                        editable=False,
                        max_length=40,
                        unique=True,
                    ),
                ),
                (
                    "payment_date",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=16,
                        validators=[MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                (
                    "payment_method",
                    models.CharField(
                        choices=[
                            ("cash", "Cash"),
                            ("mobile_money", "Mobile money"),
                            ("bank", "Bank transfer"),
                            ("card", "Card"),
                            ("cheque", "Cheque"),
                            ("other", "Other"),
                        ],
                        default="cash",
                        max_length=30,
                    ),
                ),
                (
                    "reference",
                    models.CharField(
                        blank=True,
                        max_length=120,
                    ),
                ),
                (
                    "notes",
                    models.TextField(blank=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("posted", "Posted"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="posted",
                        max_length=20,
                    ),
                ),
                (
                    "cancelled_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "cancellation_reason",
                    models.TextField(blank=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "cancelled_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cancelled_supplier_payments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_supplier_payments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="account_payments",
                        to="suppliers.supplier",
                    ),
                ),
            ],
            options={
                "ordering": ["-payment_date", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="supplierpayment",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__gt", 0)),
                name="supplier_payment_amount_gt_zero",
            ),
        ),
        migrations.CreateModel(
            name="SupplierPaymentAllocation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "allocation_type",
                    models.CharField(
                        choices=[
                            ("opening_balance", "Opening balance"),
                            ("purchase", "Purchase"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=16,
                        validators=[MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "payment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="allocations",
                        to="suppliers.supplierpayment",
                    ),
                ),
                (
                    "purchase",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="supplier_payment_allocations",
                        to="purchases.purchase",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.AddConstraint(
            model_name="supplierpaymentallocation",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__gt", 0)),
                name="supplier_payment_allocation_gt_zero",
            ),
        ),
    ]
