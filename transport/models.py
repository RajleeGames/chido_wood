from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone


ZERO = Decimal("0.00")


def _reference(prefix):
    return f"{prefix}-{timezone.localdate():%Y%m%d}-{uuid4().hex[:6].upper()}"


class TransportRoute(models.Model):
    code = models.CharField(max_length=30, unique=True, blank=True)
    origin = models.CharField(max_length=150, db_index=True)
    destination = models.CharField(max_length=150, db_index=True)
    distance_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=ZERO,
    )
    default_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO,
    )
    estimated_duration_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Estimated journey time in minutes.",
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["origin", "destination"]
        verbose_name = "Transport route"
        verbose_name_plural = "Transport routes"
        constraints = [
            models.UniqueConstraint(
                fields=["origin", "destination"],
                name="unique_transport_origin_destination",
            ),
        ]

    def clean(self):
        super().clean()
        if self.origin and self.destination:
            if self.origin.strip().casefold() == self.destination.strip().casefold():
                raise ValidationError(
                    {"destination": "Destination must be different from origin."}
                )

    def save(self, *args, **kwargs):
        self.origin = (self.origin or "").strip()
        self.destination = (self.destination or "").strip()
        if not self.code:
            self.code = _reference("RT")
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.origin} → {self.destination}"

    def get_absolute_url(self):
        return reverse("transport-route-list")

    @property
    def estimated_duration_display(self):
        minutes = self.estimated_duration_minutes or 0
        hours, remaining = divmod(minutes, 60)
        if hours and remaining:
            return f"{hours} hr {remaining} min"
        if hours:
            return f"{hours} hr"
        return f"{remaining} min" if remaining else "Not set"


class Vehicle(models.Model):
    class VehicleType(models.TextChoices):
        TRUCK = "truck", "Truck"
        PICKUP = "pickup", "Pickup"
        VAN = "van", "Van"
        CAR = "car", "Car"
        MOTORCYCLE = "motorcycle", "Motorcycle"
        OTHER = "other", "Other"

    class FuelType(models.TextChoices):
        DIESEL = "diesel", "Diesel"
        PETROL = "petrol", "Petrol"
        ELECTRIC = "electric", "Electric"
        HYBRID = "hybrid", "Hybrid"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        MAINTENANCE = "maintenance", "Under maintenance"
        INACTIVE = "inactive", "Inactive"

    plate_number = models.CharField(max_length=30, unique=True)
    make = models.CharField(max_length=80, blank=True)
    model = models.CharField(max_length=80, blank=True)
    manufacture_year = models.PositiveIntegerField(null=True, blank=True)
    vehicle_type = models.CharField(
        max_length=20,
        choices=VehicleType.choices,
        default=VehicleType.TRUCK,
        db_index=True,
    )
    capacity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
    )
    capacity_unit = models.CharField(
        max_length=30,
        default="Tonnes",
        blank=True,
    )
    fuel_type = models.CharField(
        max_length=20,
        choices=FuelType.choices,
        default=FuelType.DIESEL,
    )
    current_odometer = models.DecimalField(
        max_digits=14,
        decimal_places=1,
        default=Decimal("0.0"),
        help_text="Current odometer reading in kilometres.",
    )
    insurance_expiry = models.DateField(null=True, blank=True)
    inspection_expiry = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["plate_number"]

    def save(self, *args, **kwargs):
        self.plate_number = (self.plate_number or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        details = " ".join(part for part in [self.make, self.model] if part)
        return f"{self.plate_number} — {details}" if details else self.plate_number

    def get_absolute_url(self):
        return reverse("transport-vehicle-detail", kwargs={"pk": self.pk})

    @property
    def is_available(self):
        return self.status == self.Status.ACTIVE

    @property
    def compliance_warning(self):
        today = timezone.localdate()
        warnings = []
        for label, expiry in (
            ("Insurance", self.insurance_expiry),
            ("Inspection", self.inspection_expiry),
        ):
            if not expiry:
                continue
            days = (expiry - today).days
            if days < 0:
                warnings.append(f"{label} expired")
            elif days <= 30:
                warnings.append(f"{label} expires in {days} days")
        return ", ".join(warnings)


class Driver(models.Model):
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=30, db_index=True)
    license_number = models.CharField(max_length=60, unique=True)
    license_class = models.CharField(max_length=30, blank=True)
    license_expiry = models.DateField(null=True, blank=True)
    assigned_vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_drivers",
    )
    monthly_salary = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO,
    )
    emergency_contact_name = models.CharField(max_length=120, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name"]

    def save(self, *args, **kwargs):
        self.first_name = (self.first_name or "").strip()
        self.last_name = (self.last_name or "").strip()
        self.license_number = (self.license_number or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name

    def get_absolute_url(self):
        return reverse("transport-driver-detail", kwargs={"pk": self.pk})

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def license_warning(self):
        if not self.license_expiry:
            return ""
        days = (self.license_expiry - timezone.localdate()).days
        if days < 0:
            return "License expired"
        if days <= 30:
            return f"License expires in {days} days"
        return ""


class Trip(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        IN_TRANSIT = "in_transit", "In transit"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile money"
        BANK = "bank", "Bank"
        CREDIT = "credit", "Credit"
        OTHER = "other", "Other"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIAL = "partial", "Partially paid"
        PAID = "paid", "Paid"

    trip_number = models.CharField(max_length=40, unique=True, blank=True)
    route = models.ForeignKey(
        TransportRoute,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trips",
    )
    origin = models.CharField(max_length=150)
    destination = models.CharField(max_length=150)
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name="trips",
    )
    driver = models.ForeignKey(
        Driver,
        on_delete=models.PROTECT,
        related_name="trips",
    )
    customer_name = models.CharField(max_length=150, blank=True)
    customer_phone = models.CharField(max_length=30, blank=True)
    cargo_description = models.CharField(max_length=255, blank=True)
    load_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
    )
    load_unit = models.CharField(max_length=30, blank=True)
    departure_datetime = models.DateTimeField(default=timezone.now, db_index=True)
    arrival_datetime = models.DateTimeField(null=True, blank=True)
    distance_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=ZERO,
    )
    odometer_start = models.DecimalField(
        max_digits=14,
        decimal_places=1,
        null=True,
        blank=True,
    )
    odometer_end = models.DecimalField(
        max_digits=14,
        decimal_places=1,
        null=True,
        blank=True,
    )
    amount_charged = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO,
    )
    amount_paid = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO,
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
        db_index=True,
        editable=False,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
        db_index=True,
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="transport_trips_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-departure_datetime", "-id"]

    def clean(self):
        super().clean()
        if self.origin and self.destination:
            if self.origin.strip().casefold() == self.destination.strip().casefold():
                raise ValidationError(
                    {"destination": "Destination must be different from origin."}
                )
        if self.amount_paid < ZERO:
            raise ValidationError({"amount_paid": "Amount paid cannot be negative."})
        if self.amount_charged < ZERO:
            raise ValidationError(
                {"amount_charged": "Amount charged cannot be negative."}
            )
        if self.amount_paid > self.amount_charged:
            raise ValidationError(
                {"amount_paid": "Amount paid cannot exceed amount charged."}
            )
        if (
            self.odometer_start is not None
            and self.odometer_end is not None
            and self.odometer_end < self.odometer_start
        ):
            raise ValidationError(
                {"odometer_end": "Ending odometer cannot be below starting odometer."}
            )
        if (
            self.arrival_datetime
            and self.departure_datetime
            and self.arrival_datetime < self.departure_datetime
        ):
            raise ValidationError(
                {"arrival_datetime": "Arrival cannot be before departure."}
            )

    def save(self, *args, **kwargs):
        if not self.trip_number:
            self.trip_number = _reference("TR")
        if self.route_id:
            if not self.origin:
                self.origin = self.route.origin
            if not self.destination:
                self.destination = self.route.destination
            if not self.distance_km:
                self.distance_km = self.route.distance_km
        self.origin = (self.origin or "").strip()
        self.destination = (self.destination or "").strip()
        if self.amount_paid <= ZERO:
            self.payment_status = self.PaymentStatus.UNPAID
        elif self.amount_paid < self.amount_charged:
            self.payment_status = self.PaymentStatus.PARTIAL
        else:
            self.payment_status = self.PaymentStatus.PAID
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.trip_number} — {self.origin} → {self.destination}"

    def get_absolute_url(self):
        return reverse("transport-trip-detail", kwargs={"pk": self.pk})

    @property
    def balance_due(self):
        return max(self.amount_charged - self.amount_paid, ZERO)

    @property
    def expense_total(self):
        return self.expenses.aggregate(total=Sum("amount"))["total"] or ZERO

    @property
    def net_profit(self):
        return self.amount_charged - self.expense_total

    @property
    def actual_distance(self):
        if self.odometer_start is None or self.odometer_end is None:
            return None
        return self.odometer_end - self.odometer_start


class TransportExpense(models.Model):
    class Category(models.TextChoices):
        FUEL = "fuel", "Fuel"
        REPAIR = "repair", "Repair"
        MILEAGE = "mileage", "Mileage / road allowance"
        SERVICE = "service", "Vehicle service"
        TOLL = "toll", "Road toll"
        LOADING = "loading", "Loading / unloading"
        PARKING = "parking", "Parking"
        DRIVER_ALLOWANCE = "driver_allowance", "Driver allowance"
        SALARY = "salary", "Salary / wages"
        INSURANCE = "insurance", "Insurance"
        INSPECTION = "inspection", "Inspection"
        FINE = "fine", "Fine"
        OFFICE = "office", "Office expense"
        OTHER = "other", "Other"

    expense_number = models.CharField(max_length=40, unique=True, blank=True)
    trip = models.ForeignKey(
        Trip,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transport_expenses",
    )
    driver = models.ForeignKey(
        Driver,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transport_expenses",
    )
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.FUEL,
        db_index=True,
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    expense_date = models.DateTimeField(default=timezone.now, db_index=True)
    vendor = models.CharField(max_length=150, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="transport_expenses_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expense_date", "-id"]

    def clean(self):
        super().clean()
        if self.amount is not None and self.amount <= ZERO:
            raise ValidationError({"amount": "Expense amount must be greater than zero."})

    def save(self, *args, **kwargs):
        if not self.expense_number:
            self.expense_number = _reference("EX")
        if self.trip_id:
            self.vehicle = self.vehicle or self.trip.vehicle
            self.driver = self.driver or self.trip.driver
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.expense_number} — {self.get_category_display()}"

    def get_absolute_url(self):
        return reverse("transport-expense-list")
