from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .models import Driver, TransportExpense, TransportRoute, Trip, Vehicle


class StyledModelForm(forms.ModelForm):
    """Apply CHIDO's existing form classes without extra libraries."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-checkbox")
            else:
                existing = widget.attrs.get("class", "")
                widget.attrs["class"] = f"{existing} form-control".strip()


class TransportRouteForm(StyledModelForm):
    class Meta:
        model = TransportRoute
        fields = [
            "code",
            "origin",
            "destination",
            "distance_km",
            "default_price",
            "estimated_duration_minutes",
            "notes",
            "is_active",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
            "distance_km": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "default_price": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "estimated_duration_minutes": forms.NumberInput(attrs={"min": "0"}),
        }
        help_texts = {
            "code": "Leave blank and the system will generate a route code.",
            "default_price": "Suggested charge when creating a trip on this route.",
        }


class VehicleForm(StyledModelForm):
    class Meta:
        model = Vehicle
        fields = [
            "plate_number",
            "make",
            "model",
            "manufacture_year",
            "vehicle_type",
            "capacity",
            "capacity_unit",
            "fuel_type",
            "current_odometer",
            "insurance_expiry",
            "inspection_expiry",
            "status",
            "notes",
        ]
        widgets = {
            "manufacture_year": forms.NumberInput(attrs={"min": "1950"}),
            "capacity": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "current_odometer": forms.NumberInput(attrs={"min": "0", "step": "0.1"}),
            "insurance_expiry": forms.DateInput(attrs={"type": "date"}),
            "inspection_expiry": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }


class DriverForm(StyledModelForm):
    class Meta:
        model = Driver
        fields = [
            "first_name",
            "last_name",
            "phone",
            "license_number",
            "license_class",
            "license_expiry",
            "assigned_vehicle",
            "monthly_salary",
            "emergency_contact_name",
            "emergency_contact_phone",
            "notes",
            "is_active",
        ]
        widgets = {
            "license_expiry": forms.DateInput(attrs={"type": "date"}),
            "monthly_salary": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        vehicle_qs = Vehicle.objects.order_by("plate_number")
        if not self.instance.pk:
            vehicle_qs = vehicle_qs.filter(status=Vehicle.Status.ACTIVE)
        self.fields["assigned_vehicle"].queryset = vehicle_qs


class TripForm(StyledModelForm):
    class Meta:
        model = Trip
        fields = [
            "route",
            "origin",
            "destination",
            "vehicle",
            "driver",
            "customer_name",
            "customer_phone",
            "cargo_description",
            "load_quantity",
            "load_unit",
            "departure_datetime",
            "arrival_datetime",
            "distance_km",
            "odometer_start",
            "odometer_end",
            "amount_charged",
            "amount_paid",
            "payment_method",
            "status",
            "notes",
        ]
        widgets = {
            "departure_datetime": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "arrival_datetime": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "load_quantity": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "distance_km": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "odometer_start": forms.NumberInput(attrs={"min": "0", "step": "0.1"}),
            "odometer_end": forms.NumberInput(attrs={"min": "0", "step": "0.1"}),
            "amount_charged": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "amount_paid": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {
            "route": "When origin or destination is left blank, the selected route values are used when saving.",
            "amount_paid": "A balance is created automatically when less than the charge is paid.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["origin"].required = False
        self.fields["destination"].required = False
        self.fields["departure_datetime"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["arrival_datetime"].input_formats = ["%Y-%m-%dT%H:%M"]

        routes = TransportRoute.objects.order_by("origin", "destination")
        vehicles = Vehicle.objects.order_by("plate_number")
        drivers = Driver.objects.order_by("first_name", "last_name")

        if not self.instance.pk:
            routes = routes.filter(is_active=True)
            vehicles = vehicles.filter(status=Vehicle.Status.ACTIVE)
            drivers = drivers.filter(is_active=True)

        self.fields["route"].queryset = routes
        self.fields["vehicle"].queryset = vehicles
        self.fields["driver"].queryset = drivers

    def clean(self):
        cleaned = super().clean()
        route = cleaned.get("route")
        origin = (cleaned.get("origin") or "").strip()
        destination = (cleaned.get("destination") or "").strip()
        amount_charged = cleaned.get("amount_charged") or Decimal("0.00")
        distance_km = cleaned.get("distance_km") or Decimal("0.00")

        if route:
            origin = origin or route.origin
            destination = destination or route.destination
            if amount_charged == Decimal("0.00"):
                cleaned["amount_charged"] = route.default_price
            if distance_km == Decimal("0.00"):
                cleaned["distance_km"] = route.distance_km

        if not origin:
            self.add_error("origin", "Enter an origin or select a route.")
        if not destination:
            self.add_error("destination", "Enter a destination or select a route.")

        cleaned["origin"] = origin
        cleaned["destination"] = destination
        return cleaned


class TransportExpenseForm(StyledModelForm):
    class Meta:
        model = TransportExpense
        fields = [
            "trip",
            "vehicle",
            "driver",
            "category",
            "amount",
            "expense_date",
            "vendor",
            "reference",
            "description",
        ]
        widgets = {
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "expense_date": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "description": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {
            "trip": "Optional. Link this expense to a specific trip for profit calculation.",
            "vehicle": "Optional for office or general transport expenses.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["expense_date"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["trip"].queryset = Trip.objects.exclude(
            status=Trip.Status.CANCELLED
        ).order_by("-departure_datetime")
        self.fields["vehicle"].queryset = Vehicle.objects.order_by("plate_number")
        self.fields["driver"].queryset = Driver.objects.order_by(
            "first_name", "last_name"
        )
