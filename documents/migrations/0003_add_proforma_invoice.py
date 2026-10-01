from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "documents",
            "0002_businessprofile_document_counters",
        ),
    ]

    operations = [

        migrations.AddField(
            model_name="businessprofile",
            name="next_proforma_invoice_number",
            field=models.PositiveBigIntegerField(
                default=1,
                editable=False,
            ),
        ),

        migrations.AlterField(
            model_name="document",
            name="document_type",
            field=models.CharField(
                choices=[
                    (
                        "invoice",
                        "Invoice",
                    ),
                    (
                        "proforma_invoice",
                        "Proforma Invoice",
                    ),
                    (
                        "delivery_note",
                        "Delivery Note",
                    ),
                ],
                default="invoice",
                max_length=20,
            ),
        ),

    ]