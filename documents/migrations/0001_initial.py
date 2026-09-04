import decimal
import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BusinessProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("company_name", models.CharField(default="CHIDO WOOD PRODUCT", max_length=180)),
                ("logo", models.ImageField(blank=True, help_text="Logo used on invoices and delivery notes.", null=True, upload_to="documents/company/")),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone_1", models.CharField(blank=True, max_length=40)),
                ("phone_2", models.CharField(blank=True, max_length=40)),
                ("address", models.CharField(blank=True, max_length=255)),
                ("tin", models.CharField(blank=True, max_length=80, verbose_name="TIN")),
                ("vrn", models.CharField(blank=True, max_length=80, verbose_name="VRN")),
                ("footer_note", models.TextField(blank=True, default="Thank you for doing business with us.")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Business profile", "verbose_name_plural": "Business profile"},
        ),
        migrations.CreateModel(
            name="Document",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("document_type", models.CharField(choices=[("invoice", "Invoice"), ("delivery_note", "Delivery Note")], default="invoice", max_length=20)),
                ("document_number", models.CharField(help_text="Manual number, e.g. INV-00560 or DN-0012.", max_length=60)),
                ("date", models.DateField()),
                ("customer_name", models.CharField(max_length=180)),
                ("customer_phone", models.CharField(blank=True, max_length=50)),
                ("customer_address", models.CharField(blank=True, max_length=255)),
                ("customer_reference", models.CharField(blank=True, max_length=120)),
                ("subject", models.CharField(blank=True, max_length=180)),
                ("notes", models.TextField(blank=True)),
                ("vat_percent", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=5, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))])),
                ("status", models.CharField(choices=[("draft", "Draft"), ("issued", "Issued")], default="draft", max_length=20)),
                ("share_token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manual_documents", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-date", "-pk"]},
        ),
        migrations.CreateModel(
            name="BankAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bank_name", models.CharField(max_length=100)),
                ("account_name", models.CharField(max_length=180)),
                ("account_number", models.CharField(max_length=100)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("business", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bank_accounts", to="documents.businessprofile")),
            ],
            options={"ordering": ["sort_order", "pk"]},
        ),
        migrations.CreateModel(
            name="DocumentItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("description", models.CharField(max_length=255)),
                ("quantity", models.DecimalField(decimal_places=2, default=decimal.Decimal("1.00"), max_digits=14, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))])),
                ("unit", models.CharField(blank=True, max_length=30)),
                ("unit_price", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=16, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))])),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="documents.document")),
            ],
            options={"ordering": ["sort_order", "pk"]},
        ),
        migrations.AddConstraint(
            model_name="document",
            constraint=models.UniqueConstraint(
                fields=("document_type", "document_number"),
                name="uniq_manual_document_number_by_type",
            ),
        ),
    ]
