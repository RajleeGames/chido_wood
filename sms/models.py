from __future__ import annotations

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

from .services.phones import normalize_phone


sender_name_validator = RegexValidator(
    regex=r"^[A-Za-z0-9]{3,11}$",
    message="Sender name must contain 3 to 11 letters or numbers without spaces.",
)

phone_validator = RegexValidator(
    regex=r"^255[67]\d{8}$",
    message="Use Tanzania international format, for example 255712345678.",
)


class SenderID(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"

    name = models.CharField(
        max_length=11,
        unique=True,
        validators=[sender_name_validator],
        help_text="3 to 11 letters or numbers without spaces. Example: CHIDOWOOD",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    provider_reference = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_sender_ids_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "name"]
        indexes = [
            models.Index(fields=["status", "is_active"]),
            models.Index(fields=["is_default"]),
        ]

    def save(self, *args, **kwargs):
        self.name = str(self.name or "").strip().upper()

        if self.status == self.Status.APPROVED:
            if not self.approved_at:
                self.approved_at = timezone.now()
        else:
            self.approved_at = None
            self.is_default = False
            self.is_active = False

        super().save(*args, **kwargs)

        if self.is_default:
            type(self).objects.filter(is_default=True).exclude(pk=self.pk).update(
                is_default=False
            )

    @property
    def can_send(self):
        return self.status == self.Status.APPROVED and self.is_active

    def __str__(self):
        return self.name


class SMSTemplate(models.Model):
    class Category(models.TextChoices):
        THANK_YOU = "thank_you", "Thank You"
        DEBT_REMINDER = "debt_reminder", "Debt Reminder"
        PAYMENT_CONFIRMATION = "payment_confirmation", "Payment Confirmation"
        PROMOTION = "promotion", "Promotion"
        NEW_STOCK = "new_stock", "New Stock"
        ORDER_READY = "order_ready", "Order Ready"
        CUSTOM = "custom", "Custom"

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        SWAHILI = "sw", "Swahili"

    title = models.CharField(max_length=150)
    message = models.TextField()
    category = models.CharField(
        max_length=40,
        choices=Category.choices,
        default=Category.CUSTOM,
        db_index=True,
    )
    language = models.CharField(
        max_length=10,
        choices=Language.choices,
        default=Language.SWAHILI,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_templates_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(
                fields=["title", "language"],
                name="unique_sms_template_title_language",
            ),
        ]

    def __str__(self):
        return self.title


class SMSSetting(models.Model):
    class Provider(models.TextChoices):
        BEEM = "beem", "Beem Africa"

    provider = models.CharField(
        max_length=30,
        choices=Provider.choices,
        default=Provider.BEEM,
    )
    business_name = models.CharField(max_length=120, default="CHIDO Wood Company LTD")
    default_language = models.CharField(
        max_length=10,
        choices=SMSTemplate.Language.choices,
        default=SMSTemplate.Language.SWAHILI,
    )
    default_sender = models.ForeignKey(
        SenderID,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_settings",
    )
    automatic_sale_template = models.ForeignKey(
        SMSTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="automatic_sale_settings",
    )
    transaction_sms_enabled = models.BooleanField(default=True)
    promotional_sms_enabled = models.BooleanField(default=False)
    automatic_sale_sms_enabled = models.BooleanField(default=False)
    send_limit = models.PositiveIntegerField(
        default=50,
        validators=[MinValueValidator(1)],
        help_text="Maximum recipients sent synchronously in one action.",
    )
    low_balance_threshold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    cached_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    balance_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "SMS Setting"
        verbose_name_plural = "SMS Settings"

    @classmethod
    def load(cls):
        setting, _ = cls.objects.get_or_create(pk=1)
        return setting

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return None

    def __str__(self):
        return "SMS Center Settings"


class SMSContactGroup(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_contact_groups_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SMSContact(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        SALE = "sale", "Sale"
        IMPORT = "import", "Import"
        CUSTOMER = "customer", "Customer Record"
        OTHER = "other", "Other"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_contacts",
    )
    name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(
        max_length=12,
        unique=True,
        validators=[phone_validator],
        db_index=True,
    )
    email = models.EmailField(blank=True)
    groups = models.ManyToManyField(
        SMSContactGroup,
        blank=True,
        related_name="contacts",
    )
    source = models.CharField(
        max_length=30,
        choices=Source.choices,
        default=Source.MANUAL,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    allow_transaction_sms = models.BooleanField(default=True)
    allow_promotional_sms = models.BooleanField(default=False)
    opted_out = models.BooleanField(default=False, db_index=True)
    opted_out_at = models.DateTimeField(null=True, blank=True)
    last_purchase_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_contacts_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "phone"]
        indexes = [
            models.Index(fields=["source", "is_active"]),
            models.Index(fields=["last_purchase_at"]),
        ]

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        self.name = str(self.name or "").strip()

        if self.opted_out and not self.opted_out_at:
            self.opted_out_at = timezone.now()
        elif not self.opted_out:
            self.opted_out_at = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name or self.phone} ({self.phone})"


class SMSCampaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUEUED = "queued", "Queued"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        PARTIAL = "partial", "Partially Sent"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class MessageType(models.TextChoices):
        TRANSACTION = "transaction", "Transaction"
        PROMOTIONAL = "promotional", "Promotional"

    title = models.CharField(max_length=150)
    template = models.ForeignKey(
        SMSTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns",
    )
    message = models.TextField(blank=True)
    sender_id = models.ForeignKey(
        SenderID,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns",
    )
    groups = models.ManyToManyField(
        SMSContactGroup,
        blank=True,
        related_name="campaigns",
    )
    contacts = models.ManyToManyField(
        SMSContact,
        blank=True,
        related_name="campaigns",
    )
    message_type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.TRANSACTION,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    total_recipients = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    delivered_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_campaigns_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def get_message_text(self):
        if self.template_id:
            return self.template.message or ""
        return self.message or ""

    def __str__(self):
        return self.title


class SMSMessage(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        UNDELIVERED = "undelivered", "Undelivered"
        FAILED = "failed", "Failed"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"

    campaign = models.ForeignKey(
        SMSCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )
    contact = models.ForeignKey(
        SMSContact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_messages",
    )
    sale = models.ForeignKey(
        "sales.Sale",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_messages",
    )
    sender_id = models.ForeignKey(
        SenderID,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )
    dest_addr = models.CharField(max_length=12, validators=[phone_validator], db_index=True)
    message = models.TextField()
    message_type = models.CharField(
        max_length=20,
        choices=SMSCampaign.MessageType.choices,
        default=SMSCampaign.MessageType.TRANSACTION,
        db_index=True,
    )
    recipient_id = models.CharField(max_length=200, blank=True)
    request_id = models.CharField(max_length=200, blank=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    sms_parts = models.PositiveSmallIntegerField(default=1)
    provider_response = models.JSONField(default=dict, blank=True)
    error_text = models.TextField(blank=True)
    is_automatic = models.BooleanField(default=False, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_messages_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["message_type", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["sale"],
                condition=models.Q(is_automatic=True),
                name="unique_automatic_sms_per_sale",
            )
        ]

    def save(self, *args, **kwargs):
        self.dest_addr = normalize_phone(self.dest_addr)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.dest_addr} - {self.status}"


class SMSImportBatch(models.Model):
    source_name = models.CharField(max_length=255, blank=True)
    total_rows = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    error_rows = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_import_batches_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.source_name or f"Import {self.pk}"
