from django.contrib import admin

from .models import Driver, TransportExpense, TransportRoute, Trip, Vehicle


@admin.register(TransportRoute)
class TransportRouteAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "origin",
        "destination",
        "distance_km",
        "default_price",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = ("code", "origin", "destination")


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        "plate_number",
        "make",
        "model",
        "vehicle_type",
        "capacity",
        "status",
        "current_odometer",
    )
    list_filter = ("status", "vehicle_type", "fuel_type")
    search_fields = ("plate_number", "make", "model")


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "phone",
        "license_number",
        "assigned_vehicle",
        "license_expiry",
        "is_active",
    )
    list_filter = ("is_active", "license_class")
    search_fields = (
        "first_name",
        "last_name",
        "phone",
        "license_number",
    )


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = (
        "trip_number",
        "departure_datetime",
        "origin",
        "destination",
        "vehicle",
        "driver",
        "amount_charged",
        "payment_status",
        "status",
    )
    list_filter = ("status", "payment_status", "payment_method")
    search_fields = (
        "trip_number",
        "customer_name",
        "customer_phone",
        "origin",
        "destination",
        "vehicle__plate_number",
    )
    autocomplete_fields = ("route", "vehicle", "driver")
    readonly_fields = ("payment_status", "created_at", "updated_at")


@admin.register(TransportExpense)
class TransportExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "expense_number",
        "expense_date",
        "category",
        "trip",
        "vehicle",
        "amount",
        "recorded_by",
    )
    list_filter = ("category", "expense_date")
    search_fields = (
        "expense_number",
        "vendor",
        "reference",
        "trip__trip_number",
        "vehicle__plate_number",
    )
    autocomplete_fields = ("trip", "vehicle", "driver")
    readonly_fields = ("created_at", "updated_at")
