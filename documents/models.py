import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class BusinessProfile(models.Model):
    company_name = models.CharField(
        max_length=180,
        default="CHIDO WOOD PRODUCT",
    )

    logo = models.ImageField(
        upload_to="documents/company/",
        blank=True,
        null=True,
        help_text=(
            "Logo used on invoices, proforma invoices "
            "and delivery notes."
        ),
    )

    email = models.EmailField(
        blank=True,
    )

    phone_1 = models.CharField(
        max_length=40,
        blank=True,
    )

    phone_2 = models.CharField(
        max_length=40,
        blank=True,
    )

    address = models.CharField(
        max_length=255,
        blank=True,
    )

    tin = models.CharField(
        "TIN",
        max_length=80,
        blank=True,
    )

    vrn = models.CharField(
        "VRN",
        max_length=80,
        blank=True,
    )

    # =========================================================
    # AUTOMATIC DOCUMENT NUMBER COUNTERS
    # =========================================================

    next_invoice_number = models.PositiveBigIntegerField(
        default=1,
        editable=False,
    )

    next_proforma_invoice_number = models.PositiveBigIntegerField(
        default=1,
        editable=False,
    )

    next_delivery_note_number = models.PositiveBigIntegerField(
        default=1,
        editable=False,
    )

    footer_note = models.TextField(
        blank=True,
        default="Thank you for doing business with us.",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Business profile"
        verbose_name_plural = "Business profile"

    def __str__(self):
        return self.company_name

    @classmethod
    def get_solo(cls):
        obj = (
            cls.objects
            .order_by("pk")
            .first()
        )

        return (
            obj
            or cls.objects.create()
        )


class BankAccount(models.Model):
    business = models.ForeignKey(
        BusinessProfile,
        on_delete=models.CASCADE,
        related_name="bank_accounts",
    )

    bank_name = models.CharField(
        max_length=100,
    )

    account_name = models.CharField(
        max_length=180,
    )

    account_number = models.CharField(
        max_length=100,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = [
            "sort_order",
            "pk",
        ]

    def __str__(self):
        return (
            f"{self.bank_name} - "
            f"{self.account_number}"
        )


class Document(models.Model):

    # =========================================================
    # DOCUMENT TYPES
    # =========================================================

    class DocumentType(models.TextChoices):
        INVOICE = (
            "invoice",
            "Invoice",
        )

        PROFORMA_INVOICE = (
            "proforma_invoice",
            "Proforma Invoice",
        )

        DELIVERY_NOTE = (
            "delivery_note",
            "Delivery Note",
        )

    class Status(models.TextChoices):
        DRAFT = (
            "draft",
            "Draft",
        )

        ISSUED = (
            "issued",
            "Issued",
        )

    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.INVOICE,
    )

    # Assigned automatically.
    #
    # Each document type has its own independent sequence:
    #
    # Invoice:
    # 00001, 00002...
    #
    # Proforma:
    # 00001, 00002...
    #
    # Delivery Note:
    # 00001, 00002...
    document_number = models.CharField(
        max_length=60,
        editable=False,
    )

    date = models.DateField()

    customer_name = models.CharField(
        max_length=180,
    )

    customer_phone = models.CharField(
        max_length=50,
        blank=True,
    )

    customer_address = models.CharField(
        max_length=255,
        blank=True,
    )

    customer_reference = models.CharField(
        max_length=120,
        blank=True,
    )

    subject = models.CharField(
        max_length=180,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
    )

    vat_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(
                Decimal("0.00")
            )
        ],
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    share_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="manual_documents",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-date",
            "-pk",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "document_type",
                    "document_number",
                ],
                name=(
                    "uniq_manual_document_number_by_type"
                ),
            )
        ]

    def __str__(self):
        return (
            f"{self.get_document_type_display()} "
            f"{self.document_number}"
        )

    # =========================================================
    # DISPLAY NUMBER
    # =========================================================

    @property
    def display_document_number(self):
        """
        Display numeric document numbers using five digits.

        Examples:

        1     -> 00001
        25    -> 00025
        00042 -> 00042

        Legacy non-numeric numbers remain untouched.
        """

        value = str(
            self.document_number
            or ""
        ).strip()

        if value.isdigit():
            return value.zfill(5)

        return value

    # =========================================================
    # DOCUMENT TYPE HELPERS
    # =========================================================

    @property
    def is_invoice(self):
        return (
            self.document_type
            == self.DocumentType.INVOICE
        )

    @property
    def is_proforma_invoice(self):
        return (
            self.document_type
            == self.DocumentType.PROFORMA_INVOICE
        )

    @property
    def is_delivery_note(self):
        return (
            self.document_type
            == self.DocumentType.DELIVERY_NOTE
        )

    @property
    def has_prices(self):
        """
        Invoice and Proforma Invoice both show:
        - unit price
        - line total
        - VAT
        - grand total

        Delivery Note does not.
        """

        return self.document_type in {
            self.DocumentType.INVOICE,
            self.DocumentType.PROFORMA_INVOICE,
        }

    # =========================================================
    # TOTALS
    # =========================================================

    @property
    def subtotal(self):
        return sum(
            (
                item.line_total
                for item
                in self.items.all()
            ),
            Decimal("0.00"),
        )

    @property
    def vat_amount(self):
        if not self.has_prices:
            return Decimal("0.00")

        return (
            self.subtotal
            * self.vat_percent
            / Decimal("100")
        ).quantize(
            Decimal("0.01")
        )

    @property
    def grand_total(self):
        if not self.has_prices:
            return Decimal("0.00")

        return (
            self.subtotal
            + self.vat_amount
        )

    # =========================================================
    # NUMBER ALLOCATION
    # =========================================================

    @classmethod
    def allocate_document_number(
        cls,
        document_type,
    ):
        """
        Allocate a five-digit number safely.

        Each type has its own sequence:

        Invoice:
            next_invoice_number

        Proforma Invoice:
            next_proforma_invoice_number

        Delivery Note:
            next_delivery_note_number

        Existing numeric numbers are also checked to prevent
        accidental reuse.
        """

        profile = (
            BusinessProfile.objects
            .select_for_update()
            .order_by("pk")
            .first()
        )

        if profile is None:
            profile = (
                BusinessProfile.objects
                .create()
            )

            profile = (
                BusinessProfile.objects
                .select_for_update()
                .get(
                    pk=profile.pk
                )
            )

        # -----------------------------------------------------
        # Select the correct counter.
        # -----------------------------------------------------

        if (
            document_type
            == cls.DocumentType.DELIVERY_NOTE
        ):
            counter_field = (
                "next_delivery_note_number"
            )

        elif (
            document_type
            == cls.DocumentType.PROFORMA_INVOICE
        ):
            counter_field = (
                "next_proforma_invoice_number"
            )

        else:
            counter_field = (
                "next_invoice_number"
            )

        counter_value = max(
            int(
                getattr(
                    profile,
                    counter_field,
                    1,
                )
                or 1
            ),
            1,
        )

        # -----------------------------------------------------
        # Find highest existing numeric number for this type.
        # -----------------------------------------------------

        highest_existing = 0

        existing_numbers = (
            cls.objects
            .filter(
                document_type=document_type,
            )
            .values_list(
                "document_number",
                flat=True,
            )
        )

        for current in existing_numbers:
            cleaned = str(
                current or ""
            ).strip()

            if cleaned.isdigit():
                highest_existing = max(
                    highest_existing,
                    int(cleaned),
                )

        allocated = max(
            counter_value,
            highest_existing + 1,
        )

        # -----------------------------------------------------
        # Move counter forward.
        # -----------------------------------------------------

        setattr(
            profile,
            counter_field,
            allocated + 1,
        )

        profile.save(
            update_fields=[
                counter_field,
                "updated_at",
            ]
        )

        return f"{allocated:05d}"


class DocumentItem(models.Model):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="items",
    )

    description = models.CharField(
        max_length=255,
    )

    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[
            MinValueValidator(
                Decimal("0.00")
            )
        ],
    )

    unit = models.CharField(
        max_length=30,
        blank=True,
    )

    unit_price = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(
                Decimal("0.00")
            )
        ],
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        ordering = [
            "sort_order",
            "pk",
        ]

    def __str__(self):
        return self.description

    @property
    def line_total(self):
        return (
            self.quantity
            or Decimal("0.00")
        ) * (
            self.unit_price
            or Decimal("0.00")
        )