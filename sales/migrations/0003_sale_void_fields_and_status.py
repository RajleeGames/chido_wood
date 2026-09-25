# Generated for CHIDO Wood ERP sale void support.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "sales",
            "0002_customercuttingservice",
        ),
        migrations.swappable_dependency(
            settings.AUTH_USER_MODEL
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="void_reason",
            field=models.TextField(
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="voided_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="voided_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=(
                    django.db.models.deletion.PROTECT
                ),
                related_name="voided_sales",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="sale",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("completed", "Completed"),
                    ("cancelled", "Cancelled"),
                    ("voided", "Voided"),
                ],
                db_index=True,
                default="draft",
                max_length=20,
            ),
        ),
    ]
