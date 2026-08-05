from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TransportRoute",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(blank=True, max_length=30, unique=True)),
                ("origin", models.CharField(db_index=True, max_length=150)),
                ("destination", models.CharField(db_index=True, max_length=150)),
                ("distance_km", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10)),
                ("default_price", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("estimated_duration_minutes", models.PositiveIntegerField(default=0, help_text="Estimated journey time in minutes.")),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Transport route",
                "verbose_name_plural": "Transport routes",
                "ordering": ["origin", "destination"],
            },
        ),
        migrations.CreateModel(
            name="Vehicle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("plate_number", models.CharField(max_length=30, unique=True)),
                ("make", models.CharField(blank=True, max_length=80)),
                ("model", models.CharField(blank=True, max_length=80)),
                ("manufacture_year", models.PositiveIntegerField(blank=True, null=True)),
                ("vehicle_type", models.CharField(choices=[("truck", "Truck"), ("pickup", "Pickup"), ("van", "Van"), ("car", "Car"), ("motorcycle", "Motorcycle"), ("other", "Other")], db_index=True, default="truck", max_length=20)),
                ("capacity", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("capacity_unit", models.CharField(blank=True, default="Tonnes", max_length=30)),
                ("fuel_type", models.CharField(choices=[("diesel", "Diesel"), ("petrol", "Petrol"), ("electric", "Electric"), ("hybrid", "Hybrid"), ("other", "Other")], default="diesel", max_length=20)),
                ("current_odometer", models.DecimalField(decimal_places=1, default=Decimal("0.0"), help_text="Current odometer reading in kilometres.", max_digits=14)),
                ("insurance_expiry", models.DateField(blank=True, null=True)),
                ("inspection_expiry", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("active", "Active"), ("maintenance", "Under maintenance"), ("inactive", "Inactive")], db_index=True, default="active", max_length=20)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["plate_number"]},
        ),
        migrations.CreateModel(
            name="Driver",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("first_name", models.CharField(max_length=80)),
                ("last_name", models.CharField(blank=True, max_length=80)),
                ("phone", models.CharField(db_index=True, max_length=30)),
                ("license_number", models.CharField(max_length=60, unique=True)),
                ("license_class", models.CharField(blank=True, max_length=30)),
                ("license_expiry", models.DateField(blank=True, null=True)),
                ("monthly_salary", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("emergency_contact_name", models.CharField(blank=True, max_length=120)),
                ("emergency_contact_phone", models.CharField(blank=True, max_length=30)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_vehicle", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_drivers", to="transport.vehicle")),
            ],
            options={"ordering": ["first_name", "last_name"]},
        ),
        migrations.CreateModel(
            name="Trip",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trip_number", models.CharField(blank=True, max_length=40, unique=True)),
                ("origin", models.CharField(max_length=150)),
                ("destination", models.CharField(max_length=150)),
                ("customer_name", models.CharField(blank=True, max_length=150)),
                ("customer_phone", models.CharField(blank=True, max_length=30)),
                ("cargo_description", models.CharField(blank=True, max_length=255)),
                ("load_quantity", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("load_unit", models.CharField(blank=True, max_length=30)),
                ("departure_datetime", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("arrival_datetime", models.DateTimeField(blank=True, null=True)),
                ("distance_km", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10)),
                ("odometer_start", models.DecimalField(blank=True, decimal_places=1, max_digits=14, null=True)),
                ("odometer_end", models.DecimalField(blank=True, decimal_places=1, max_digits=14, null=True)),
                ("amount_charged", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("amount_paid", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("payment_method", models.CharField(choices=[("cash", "Cash"), ("mobile_money", "Mobile money"), ("bank", "Bank"), ("credit", "Credit"), ("other", "Other")], default="cash", max_length=20)),
                ("payment_status", models.CharField(choices=[("unpaid", "Unpaid"), ("partial", "Partially paid"), ("paid", "Paid")], db_index=True, default="unpaid", editable=False, max_length=20)),
                ("status", models.CharField(choices=[("scheduled", "Scheduled"), ("in_transit", "In transit"), ("completed", "Completed"), ("cancelled", "Cancelled")], db_index=True, default="scheduled", max_length=20)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transport_trips_created", to=settings.AUTH_USER_MODEL)),
                ("driver", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trips", to="transport.driver")),
                ("route", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="trips", to="transport.transportroute")),
                ("vehicle", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trips", to="transport.vehicle")),
            ],
            options={"ordering": ["-departure_datetime", "-id"]},
        ),
        migrations.CreateModel(
            name="TransportExpense",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("expense_number", models.CharField(blank=True, max_length=40, unique=True)),
                ("category", models.CharField(choices=[("fuel", "Fuel"), ("repair", "Repair"), ("service", "Vehicle service"), ("toll", "Road toll"), ("loading", "Loading / unloading"), ("parking", "Parking"), ("driver_allowance", "Driver allowance"), ("salary", "Salary / wages"), ("insurance", "Insurance"), ("inspection", "Inspection"), ("fine", "Fine"), ("office", "Office expense"), ("other", "Other")], db_index=True, default="fuel", max_length=30)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("expense_date", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("vendor", models.CharField(blank=True, max_length=150)),
                ("reference", models.CharField(blank=True, max_length=100)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("driver", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="transport_expenses", to="transport.driver")),
                ("recorded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transport_expenses_recorded", to=settings.AUTH_USER_MODEL)),
                ("trip", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="expenses", to="transport.trip")),
                ("vehicle", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="transport_expenses", to="transport.vehicle")),
            ],
            options={"ordering": ["-expense_date", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="transportroute",
            constraint=models.UniqueConstraint(fields=("origin", "destination"), name="unique_transport_origin_destination"),
        ),
    ]
