import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from products.models import Product
from suppliers.models import Supplier


ZERO_MONEY = Decimal("0.00")
ZERO_COST = Decimal("0.0000")
ZERO_QUANTITY = Decimal("0.000")


def generate_conversion_number():
    date_part = timezone.localdate().strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:6].upper()

    return f"CUT-{date_part}-{random_part}"

def generate_adjustment_number():
    date_part = timezone.localdate().strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:6].upper()

    return f"ADJ-{date_part}-{random_part}"


class StockBatch(models.Model):
    class SourceType(models.TextChoices):
        OPENING = "opening", "Opening stock"
        PURCHASE = "purchase", "Purchase"
        CONVERSION = "conversion", "Wood conversion"
        ADJUSTMENT = "adjustment", "Stock adjustment"
        RETURN = "return", "Customer return"

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="stock_batches",
    )

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="stock_batches",
        null=True,
        blank=True,
    )

    source_type = models.CharField(
        max_length=30,
        choices=SourceType.choices,
    )

    source_reference = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
    )

    received_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )

    remaining_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(ZERO_QUANTITY)],
    )

    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        validators=[MinValueValidator(ZERO_COST)],
    )

    received_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    expiry_note = models.CharField(
        max_length=100,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_stock_batches",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "received_at",
            "id",
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(received_quantity__gt=0),
                name="stock_batch_received_quantity_gt_zero",
            ),
            models.CheckConstraint(
                condition=Q(remaining_quantity__gte=0),
                name="stock_batch_remaining_quantity_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(unit_cost__gte=0),
                name="stock_batch_unit_cost_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(
                    remaining_quantity__lte=F("received_quantity")
                ),
                name="stock_batch_remaining_not_above_received",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "product",
                    "is_active",
                    "received_at",
                ],
                name="stock_fifo_batch_index",
            ),
        ]

    def __str__(self):
        return (
            f"{self.product.name} - "
            f"{self.remaining_quantity}/{self.received_quantity}"
        )

    @property
    def received_value(self):
        return self.received_quantity * self.unit_cost

    @property
    def remaining_value(self):
        return self.remaining_quantity * self.unit_cost
    @property
    def used_quantity(self):
        return (
         self.received_quantity
          - self.remaining_quantity
    )


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        OPENING = "opening", "Opening stock"
        PURCHASE = "purchase", "Purchase"
        SALE = "sale", "Sale"
        SALE_RETURN = "sale_return", "Sale return"
        PURCHASE_RETURN = "purchase_return", "Purchase return"

        CONVERSION_INPUT = (
            "conversion_input",
            "Conversion input",
        )

        CONVERSION_OUTPUT = (
            "conversion_output",
            "Conversion output",
        )

        ADJUSTMENT_IN = (
            "adjustment_in",
            "Adjustment increase",
        )

        ADJUSTMENT_OUT = (
            "adjustment_out",
            "Adjustment decrease",
        )

        DAMAGE = "damage", "Damage"
        WASTE = "waste", "Waste"

        REVERSAL_IN = (
            "reversal_in",
            "Reversal increase",
        )

        REVERSAL_OUT = (
            "reversal_out",
            "Reversal decrease",
        )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )

    batch = models.ForeignKey(
        StockBatch,
        on_delete=models.PROTECT,
        related_name="movements",
        null=True,
        blank=True,
    )

    movement_type = models.CharField(
        max_length=40,
        choices=MovementType.choices,
    )

    quantity_delta = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        help_text="Positive adds stock and negative removes stock.",
    )

    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=ZERO_COST,
        validators=[MinValueValidator(ZERO_COST)],
    )

    total_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
    )

    notes = models.TextField(
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_stock_movements",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = [
            "-created_at",
            "-id",
        ]

        constraints = [
            models.CheckConstraint(
                condition=~Q(quantity_delta=0),
                name="stock_movement_quantity_not_zero",
            ),
            models.CheckConstraint(
                condition=Q(unit_cost__gte=0),
                name="stock_movement_unit_cost_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(total_cost__gte=0),
                name="stock_movement_total_cost_gte_zero",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "product",
                    "created_at",
                ],
                name="stock_movement_product_date",
            ),
            models.Index(
                fields=[
                    "movement_type",
                    "created_at",
                ],
                name="stock_movement_type_date",
            ),
        ]

    def __str__(self):
        return (
            f"{self.product.name}: "
            f"{self.quantity_delta} "
            f"({self.get_movement_type_display()})"
        )

class StockAdjustment(models.Model):
    class AdjustmentType(models.TextChoices):
        OPENING = "opening", "Opening stock"
        INCREASE = "increase", "Stock increase"
        DECREASE = "decrease", "Stock decrease"
        DAMAGE = "damage", "Damaged stock"
        WASTE = "waste", "Wasted stock"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        CANCELLED = "cancelled", "Cancelled"

    adjustment_number = models.CharField(
        max_length=40,
        unique=True,
        default=generate_adjustment_number,
        editable=False,
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="stock_adjustments",
    )

    adjustment_type = models.CharField(
        max_length=30,
        choices=AdjustmentType.choices,
        db_index=True,
    )

    adjustment_date = models.DateField(
        default=timezone.localdate,
        db_index=True,
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
        default=ZERO_COST,
        validators=[
            MinValueValidator(ZERO_COST),
        ],
        help_text=(
            "Required for opening stock and stock increases."
        ),
    )

    total_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
    )

    reason = models.CharField(
        max_length=200,
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

    created_batch = models.OneToOneField(
        StockBatch,
        on_delete=models.PROTECT,
        related_name="stock_adjustment",
        null=True,
        blank=True,
        editable=False,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_stock_adjustments",
    )

    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="posted_stock_adjustments",
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
            "-adjustment_date",
            "-id",
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="stock_adjustment_quantity_gt_zero",
            ),
            models.CheckConstraint(
                condition=Q(unit_cost__gte=0),
                name="stock_adjustment_unit_cost_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(total_cost__gte=0),
                name="stock_adjustment_total_cost_gte_zero",
            ),
        ]

    def __str__(self):
        return self.adjustment_number

    @property
    def adds_stock(self):
        return self.adjustment_type in {
            self.AdjustmentType.OPENING,
            self.AdjustmentType.INCREASE,
        }

    @property
    def removes_stock(self):
        return self.adjustment_type in {
            self.AdjustmentType.DECREASE,
            self.AdjustmentType.DAMAGE,
            self.AdjustmentType.WASTE,
        }

    @property
    def signed_quantity(self):
        if self.removes_stock:
            return -self.quantity

        return self.quantity


class StockAdjustmentBatchUsage(models.Model):
    adjustment = models.ForeignKey(
        StockAdjustment,
        on_delete=models.PROTECT,
        related_name="batch_usages",
    )

    batch = models.ForeignKey(
        StockBatch,
        on_delete=models.PROTECT,
        related_name="adjustment_usages",
    )

    quantity_used = models.DecimalField(
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
                    "adjustment",
                    "batch",
                ],
                name="unique_batch_per_stock_adjustment",
            ),
            models.CheckConstraint(
                condition=Q(quantity_used__gt=0),
                name="adjustment_batch_quantity_gt_zero",
            ),
        ]

    def __str__(self):
        return (
            f"{self.adjustment.adjustment_number} - "
            f"Batch {self.batch_id}"
        )


class WoodConversion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        CANCELLED = "cancelled", "Cancelled"

    conversion_number = models.CharField(
        max_length=40,
        unique=True,
        default=generate_conversion_number,
        editable=False,
    )

    source_product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="source_conversions",
    )

    source_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )

    additional_cutting_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
    )

    source_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
    )

    total_conversion_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    conversion_date = models.DateField(
        default=timezone.localdate,
        db_index=True,
    )

    notes = models.TextField(
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_wood_conversions",
    )

    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="posted_wood_conversions",
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
            "-conversion_date",
            "-id",
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(source_quantity__gt=0),
                name="wood_conversion_source_quantity_gt_zero",
            ),
            models.CheckConstraint(
                condition=Q(additional_cutting_cost__gte=0),
                name="wood_conversion_cutting_cost_gte_zero",
            ),
        ]

    def __str__(self):
        return self.conversion_number


class ConversionOutput(models.Model):
    conversion = models.ForeignKey(
        WoodConversion,
        on_delete=models.CASCADE,
        related_name="outputs",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="conversion_outputs",
    )

    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )

    allocated_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=ZERO_MONEY,
        editable=False,
    )

    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=ZERO_COST,
        editable=False,
    )

    output_batch = models.OneToOneField(
        StockBatch,
        on_delete=models.PROTECT,
        related_name="conversion_output",
        null=True,
        blank=True,
        editable=False,
    )

    class Meta:
        ordering = ["id"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "conversion",
                    "product",
                ],
                name="unique_product_per_conversion_output",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="conversion_output_quantity_gt_zero",
            ),
        ]

    def __str__(self):
        return (
            f"{self.conversion.conversion_number} - "
            f"{self.product.name}"
        )


class ConversionBatchUsage(models.Model):
    conversion = models.ForeignKey(
        WoodConversion,
        on_delete=models.PROTECT,
        related_name="batch_usages",
    )

    batch = models.ForeignKey(
        StockBatch,
        on_delete=models.PROTECT,
        related_name="conversion_usages",
    )

    quantity_used = models.DecimalField(
        max_digits=14,
        decimal_places=3,
    )

    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=4,
    )

    total_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
    )

    class Meta:
        ordering = [
            "batch__received_at",
            "batch_id",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "conversion",
                    "batch",
                ],
                name="unique_batch_per_conversion_usage",
            ),
            models.CheckConstraint(
                condition=Q(quantity_used__gt=0),
                name="conversion_batch_usage_quantity_gt_zero",
            ),
        ]

    def __str__(self):
        return (
            f"{self.conversion.conversion_number} - "
            f"Batch {self.batch_id}"
        )