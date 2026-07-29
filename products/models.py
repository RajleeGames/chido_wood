from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


ZERO_MONEY = Decimal("0.00")
ZERO_QUANTITY = Decimal("0.000")


class Category(models.Model):
    name = models.CharField(
        max_length=120,
        unique=True,
    )

    code = models.CharField(
        max_length=30,
        unique=True,
    )

    description = models.TextField(
        blank=True,
    )

    allow_cutting = models.BooleanField(
        default=False,
    )

    default_cutting_fee = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
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
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    class MeasurementUnit(models.TextChoices):
        PIECE = "piece", "Piece"
        SHEET = "sheet", "Sheet"
        METRE = "metre", "Metre"
        RUNNING_FOOT = "Run_foot", "Run foot"
        SQUARE_METRE = "square_metre", "Square metre"
        CUBIC_METRE = "cubic_metre", "Cubic metre"
        PACK = "pack", "Pack"
        OTHER = "other", "Other"

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )

    code = models.CharField(
        max_length=50,
        unique=True,
    )

    name = models.CharField(
        max_length=180,
    )

    wood_type = models.CharField(
        max_length=120,
        blank=True,
        help_text="Example: Pine, Mninga or Eucalyptus.",
    )

    thickness = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(ZERO_MONEY)],
        help_text="Thickness in inches or millimetres.",
    )

    width = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(ZERO_MONEY)],
    )

    length = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(ZERO_MONEY)],
    )

    dimension_note = models.CharField(
        max_length=100,
        blank=True,
        help_text="Example: 6×2 inches × 12 feet.",
    )

    measurement_unit = models.CharField(
        max_length=30,
        choices=MeasurementUnit.choices,
        default=MeasurementUnit.PIECE,
    )

    selling_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
    )

    wholesale_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(ZERO_MONEY)],
    )

    minimum_selling_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(ZERO_MONEY)],
    )

    allow_customer_cutting = models.BooleanField(
        default=False,
    )

    default_cutting_fee = models.DecimalField(
    max_digits=14,
    decimal_places=2,
    default=ZERO_MONEY,
    blank=True,
    validators=[MinValueValidator(ZERO_MONEY)],
    help_text="Leave empty to use the category cutting fee.",
)

    track_stock = models.BooleanField(
        default=True,
    )

    low_stock_level = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=ZERO_QUANTITY,
        validators=[MinValueValidator(ZERO_QUANTITY)],
    )

    barcode = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
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
            models.UniqueConstraint(
                fields=["category", "name"],
                name="unique_product_name_per_category",
            ),
        ]

        indexes = [
            models.Index(
                fields=["name"],
                name="product_name_index",
            ),
            models.Index(
                fields=["code"],
                name="product_code_index",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def effective_cutting_fee(self):
        if self.default_cutting_fee > ZERO_MONEY:
            return self.default_cutting_fee

        if self.category.allow_cutting:
            return self.category.default_cutting_fee

        return ZERO_MONEY