from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ReceiptSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("business_name", models.CharField(default="CHIDO WOOD", max_length=120)),
                ("receipt_title", models.CharField(default="SALES RECEIPT", max_length=80)),
                ("address", models.CharField(blank=True, max_length=200)),
                ("phone", models.CharField(blank=True, max_length=60)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("tin", models.CharField(blank=True, max_length=60, verbose_name="TIN")),
                ("vrn", models.CharField(blank=True, max_length=60, verbose_name="VRN")),
                ("header_note", models.CharField(blank=True, max_length=200)),
                ("footer_line_1", models.CharField(blank=True, default="Thank you for your business.", max_length=160)),
                ("footer_line_2", models.CharField(blank=True, default="Karibu tena.", max_length=160)),
                ("characters_per_line", models.PositiveSmallIntegerField(
                    default=42,
                    validators=[
                        django.core.validators.MinValueValidator(32),
                        django.core.validators.MaxValueValidator(64),
                    ],
                )),
                ("feed_lines_before_cut", models.PositiveSmallIntegerField(
                    default=6,
                    validators=[
                        django.core.validators.MinValueValidator(2),
                        django.core.validators.MaxValueValidator(12),
                    ],
                )),
                ("show_customer_phone", models.BooleanField(default=True)),
                ("show_cashier", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Receipt settings",
                "verbose_name_plural": "Receipt settings",
            },
        ),
    ]
