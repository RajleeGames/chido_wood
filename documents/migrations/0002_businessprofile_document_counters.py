from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "documents",
            "0001_initial",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="businessprofile",
            name="next_delivery_note_number",
            field=models.PositiveBigIntegerField(
                default=1,
                editable=False,
            ),
        ),
        migrations.AddField(
            model_name="businessprofile",
            name="next_invoice_number",
            field=models.PositiveBigIntegerField(
                default=1,
                editable=False,
            ),
        ),
        migrations.AlterField(
            model_name="document",
            name="document_number",
            field=models.CharField(
                editable=False,
                max_length=60,
            ),
        ),
    ]
