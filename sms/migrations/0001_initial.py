# Generated for the CHIDO Wood ERP SMS Center.

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("customers", "0001_initial"),
        ("sales", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SMSContactGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sms_contact_groups_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="SMSImportBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_name", models.CharField(blank=True, max_length=255)),
                ("total_rows", models.PositiveIntegerField(default=0)),
                ("created_count", models.PositiveIntegerField(default=0)),
                ("updated_count", models.PositiveIntegerField(default=0)),
                ("skipped_count", models.PositiveIntegerField(default=0)),
                ("error_rows", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sms_import_batches_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="SenderID",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "name",
                    models.CharField(
                        help_text="3 to 11 letters or numbers without spaces. Example: CHIDOWOOD",
                        max_length=11,
                        unique=True,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Sender name must contain 3 to 11 letters or numbers without spaces.",
                                regex="^[A-Za-z0-9]{3,11}$",
                            )
                        ],
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending Approval"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("suspended", "Suspended"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=False)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("rejection_reason", models.TextField(blank=True)),
                ("provider_reference", models.CharField(blank=True, max_length=200)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sms_sender_ids_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-is_default", "name"]},
        ),
        migrations.CreateModel(
            name="SMSTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=150)),
                ("message", models.TextField()),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("thank_you", "Thank You"),
                            ("debt_reminder", "Debt Reminder"),
                            ("payment_confirmation", "Payment Confirmation"),
                            ("promotion", "Promotion"),
                            ("new_stock", "New Stock"),
                            ("order_ready", "Order Ready"),
                            ("custom", "Custom"),
                        ],
                        db_index=True,
                        default="custom",
                        max_length=40,
                    ),
                ),
                (
                    "language",
                    models.CharField(
                        choices=[("en", "English"), ("sw", "Swahili")],
                        db_index=True,
                        default="sw",
                        max_length=10,
                    ),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sms_templates_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["title"]},
        ),
        migrations.CreateModel(
            name="SMSSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("beem", "Beem Africa")], default="beem", max_length=30)),
                ("business_name", models.CharField(default="CHIDO Wood Company LTD", max_length=120)),
                ("default_language", models.CharField(choices=[("en", "English"), ("sw", "Swahili")], default="sw", max_length=10)),
                ("transaction_sms_enabled", models.BooleanField(default=True)),
                ("promotional_sms_enabled", models.BooleanField(default=False)),
                ("automatic_sale_sms_enabled", models.BooleanField(default=False)),
                (
                    "send_limit",
                    models.PositiveIntegerField(
                        default=50,
                        help_text="Maximum recipients sent synchronously in one action.",
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "low_balance_threshold",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("cached_balance", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("balance_checked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "automatic_sale_template",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="automatic_sale_settings",
                        to="sms.smstemplate",
                    ),
                ),
                (
                    "default_sender",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="default_for_settings",
                        to="sms.senderid",
                    ),
                ),
            ],
            options={"verbose_name": "SMS Setting", "verbose_name_plural": "SMS Settings"},
        ),
        migrations.CreateModel(
            name="SMSContact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, max_length=255)),
                (
                    "phone",
                    models.CharField(
                        db_index=True,
                        max_length=12,
                        unique=True,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Use Tanzania international format, for example 255712345678.",
                                regex="^255[67]\\d{8}$",
                            )
                        ],
                    ),
                ),
                ("email", models.EmailField(blank=True, max_length=254)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("sale", "Sale"),
                            ("import", "Import"),
                            ("customer", "Customer Record"),
                            ("other", "Other"),
                        ],
                        db_index=True,
                        default="manual",
                        max_length=30,
                    ),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("allow_transaction_sms", models.BooleanField(default=True)),
                ("allow_promotional_sms", models.BooleanField(default=False)),
                ("opted_out", models.BooleanField(db_index=True, default=False)),
                ("opted_out_at", models.DateTimeField(blank=True, null=True)),
                ("last_purchase_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sms_contacts_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sms_contacts",
                        to="customers.customer",
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(blank=True, related_name="contacts", to="sms.smscontactgroup"),
                ),
            ],
            options={"ordering": ["name", "phone"]},
        ),
        migrations.CreateModel(
            name="SMSCampaign",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=150)),
                ("message", models.TextField(blank=True)),
                (
                    "message_type",
                    models.CharField(
                        choices=[("transaction", "Transaction"), ("promotional", "Promotional")],
                        db_index=True,
                        default="transaction",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("queued", "Queued"),
                            ("sending", "Sending"),
                            ("sent", "Sent"),
                            ("partial", "Partially Sent"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("total_recipients", models.PositiveIntegerField(default=0)),
                ("sent_count", models.PositiveIntegerField(default=0)),
                ("delivered_count", models.PositiveIntegerField(default=0)),
                ("failed_count", models.PositiveIntegerField(default=0)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "contacts",
                    models.ManyToManyField(blank=True, related_name="campaigns", to="sms.smscontact"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sms_campaigns_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(blank=True, related_name="campaigns", to="sms.smscontactgroup"),
                ),
                (
                    "sender_id",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="campaigns",
                        to="sms.senderid",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="campaigns",
                        to="sms.smstemplate",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="SMSMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "dest_addr",
                    models.CharField(
                        db_index=True,
                        max_length=12,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Use Tanzania international format, for example 255712345678.",
                                regex="^255[67]\\d{8}$",
                            )
                        ],
                    ),
                ),
                ("message", models.TextField()),
                (
                    "message_type",
                    models.CharField(
                        choices=[("transaction", "Transaction"), ("promotional", "Promotional")],
                        db_index=True,
                        default="transaction",
                        max_length=20,
                    ),
                ),
                ("recipient_id", models.CharField(blank=True, max_length=200)),
                ("request_id", models.CharField(blank=True, db_index=True, max_length=200)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("queued", "Queued"),
                            ("sent", "Sent"),
                            ("delivered", "Delivered"),
                            ("undelivered", "Undelivered"),
                            ("failed", "Failed"),
                            ("rejected", "Rejected"),
                            ("expired", "Expired"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("sms_parts", models.PositiveSmallIntegerField(default=1)),
                ("provider_response", models.JSONField(blank=True, default=dict)),
                ("error_text", models.TextField(blank=True)),
                ("is_automatic", models.BooleanField(db_index=True, default=False)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "campaign",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="messages",
                        to="sms.smscampaign",
                    ),
                ),
                (
                    "contact",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="messages",
                        to="sms.smscontact",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sms_messages_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sms_messages",
                        to="customers.customer",
                    ),
                ),
                (
                    "sale",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sms_messages",
                        to="sales.sale",
                    ),
                ),
                (
                    "sender_id",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="messages",
                        to="sms.senderid",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="smstemplate",
            constraint=models.UniqueConstraint(
                fields=("title", "language"),
                name="unique_sms_template_title_language",
            ),
        ),
        migrations.AddConstraint(
            model_name="smsmessage",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_automatic", True)),
                fields=("sale",),
                name="unique_automatic_sms_per_sale",
            ),
        ),
        migrations.AddIndex(
            model_name="senderid",
            index=models.Index(fields=["status", "is_active"], name="sms_senderi_status_7f5d7a_idx"),
        ),
        migrations.AddIndex(
            model_name="senderid",
            index=models.Index(fields=["is_default"], name="sms_senderi_is_defa_1c91a3_idx"),
        ),
        migrations.AddIndex(
            model_name="smscontact",
            index=models.Index(fields=["source", "is_active"], name="sms_smscont_source_2e3131_idx"),
        ),
        migrations.AddIndex(
            model_name="smscontact",
            index=models.Index(fields=["last_purchase_at"], name="sms_smscont_last_pu_c5d36c_idx"),
        ),
        migrations.AddIndex(
            model_name="smscampaign",
            index=models.Index(fields=["status", "created_at"], name="sms_smscamp_status_a17efd_idx"),
        ),
        migrations.AddIndex(
            model_name="smsmessage",
            index=models.Index(fields=["status", "created_at"], name="sms_smsmess_status_d8bc89_idx"),
        ),
        migrations.AddIndex(
            model_name="smsmessage",
            index=models.Index(fields=["message_type", "created_at"], name="sms_smsmess_message_e85a97_idx"),
        ),
    ]
