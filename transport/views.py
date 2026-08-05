from calendar import monthrange
from datetime import datetime, time
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import management_required, manager_required

from .forms import (
    DriverForm,
    TransportExpenseForm,
    TransportRouteForm,
    TripForm,
    VehicleForm,
)
from .models import Driver, TransportExpense, TransportRoute, Trip, Vehicle


ZERO = Decimal("0.00")


def _parse_date(value):
    try:
        return datetime.strptime(value or "", "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _date_start(value):
    return timezone.make_aware(datetime.combine(value, time.min))


def _date_end(value):
    return timezone.make_aware(datetime.combine(value, time.max))


def _money_total(queryset, field="amount"):
    return queryset.aggregate(total=Sum(field))["total"] or ZERO


def _paginate(request, queryset, per_page=25):
    page_obj = Paginator(queryset, per_page).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return page_obj, params.urlencode()


def _delete_object(request, obj, success_message, redirect_name, template_name):
    if request.method == "POST":
        try:
            obj.delete()
        except ProtectedError:
            messages.error(
                request,
                "This record is already used by other transport records and cannot be deleted. Mark it inactive instead.",
            )
        else:
            messages.success(request, success_message)
        return redirect(redirect_name)
    return render(
        request,
        template_name,
        {"object": obj, "page_title": "Confirm deletion"},
    )


@manager_required
def transport_dashboard(request):
    today = timezone.localdate()
    selected_date = _parse_date(request.GET.get("date")) or today

    selected_trips = Trip.objects.exclude(status=Trip.Status.CANCELLED).filter(
        departure_datetime__date=selected_date
    )
    selected_expenses = TransportExpense.objects.filter(expense_date__date=selected_date)

    month_start = selected_date.replace(day=1)
    month_end = selected_date.replace(day=monthrange(selected_date.year, selected_date.month)[1])
    monthly_trips = Trip.objects.exclude(status=Trip.Status.CANCELLED).filter(
        departure_datetime__date__range=(month_start, month_end)
    )
    monthly_expenses = TransportExpense.objects.filter(
        expense_date__date__range=(month_start, month_end)
    )

    day_revenue = _money_total(selected_trips, "amount_charged")
    day_received = _money_total(selected_trips, "amount_paid")
    day_expenses = _money_total(selected_expenses)
    month_revenue = _money_total(monthly_trips, "amount_charged")
    month_expenses = _money_total(monthly_expenses)

    warning_vehicles = [
        vehicle
        for vehicle in Vehicle.objects.exclude(status=Vehicle.Status.INACTIVE)
        if vehicle.compliance_warning
    ][:8]
    warning_drivers = [
        driver
        for driver in Driver.objects.filter(is_active=True)
        if driver.license_warning
    ][:8]

    context = {
        "page_title": "Transport dashboard",
        "selected_date": selected_date.isoformat(),
        "day_revenue": day_revenue,
        "day_received": day_received,
        "day_expenses": day_expenses,
        "day_net": day_revenue - day_expenses,
        "day_trip_count": selected_trips.count(),
        "month_revenue": month_revenue,
        "month_expenses": month_expenses,
        "month_net": month_revenue - month_expenses,
        "active_trip_count": Trip.objects.filter(
            status__in=[Trip.Status.SCHEDULED, Trip.Status.IN_TRANSIT]
        ).count(),
        "active_vehicle_count": Vehicle.objects.filter(status=Vehicle.Status.ACTIVE).count(),
        "active_driver_count": Driver.objects.filter(is_active=True).count(),
        "route_count": TransportRoute.objects.filter(is_active=True).count(),
        "recent_trips": Trip.objects.select_related(
            "route", "vehicle", "driver"
        )[:8],
        "recent_expenses": TransportExpense.objects.select_related(
            "trip", "vehicle", "driver"
        )[:8],
        "warning_vehicles": warning_vehicles,
        "warning_drivers": warning_drivers,
    }
    return render(request, "transport/dashboard.html", context)


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@manager_required
def route_list(request):
    queryset = TransportRoute.objects.all()
    q = (request.GET.get("q") or "").strip()
    active = (request.GET.get("active") or "").strip()
    if q:
        queryset = queryset.filter(
            Q(code__icontains=q)
            | Q(origin__icontains=q)
            | Q(destination__icontains=q)
        )
    if active == "yes":
        queryset = queryset.filter(is_active=True)
    elif active == "no":
        queryset = queryset.filter(is_active=False)
    page_obj, query_string = _paginate(request, queryset)
    return render(
        request,
        "transport/route_list.html",
        {
            "page_title": "Transport routes",
            "routes": page_obj.object_list,
            "page_obj": page_obj,
            "query_string": query_string,
            "q": q,
            "active_filter": active,
        },
    )


@manager_required
def route_create(request):
    form = TransportRouteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        route = form.save()
        messages.success(request, f"Route {route} created successfully.")
        return redirect("transport-route-list")
    return render(
        request,
        "transport/route_form.html",
        {"form": form, "page_title": "Add transport route", "is_editing": False},
    )


@manager_required
def route_edit(request, pk):
    route = get_object_or_404(TransportRoute, pk=pk)
    form = TransportRouteForm(request.POST or None, instance=route)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Route updated successfully.")
        return redirect("transport-route-list")
    return render(
        request,
        "transport/route_form.html",
        {
            "form": form,
            "route": route,
            "page_title": "Edit transport route",
            "is_editing": True,
        },
    )


@management_required
def route_delete(request, pk):
    route = get_object_or_404(TransportRoute, pk=pk)
    return _delete_object(
        request,
        route,
        "Route deleted successfully.",
        "transport-route-list",
        "transport/route_confirm_delete.html",
    )


# -----------------------------------------------------------------------------
# Vehicles
# -----------------------------------------------------------------------------
@manager_required
def vehicle_list(request):
    queryset = Vehicle.objects.all()
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    vehicle_type = (request.GET.get("vehicle_type") or "").strip()
    if q:
        queryset = queryset.filter(
            Q(plate_number__icontains=q)
            | Q(make__icontains=q)
            | Q(model__icontains=q)
        )
    if status in dict(Vehicle.Status.choices):
        queryset = queryset.filter(status=status)
    if vehicle_type in dict(Vehicle.VehicleType.choices):
        queryset = queryset.filter(vehicle_type=vehicle_type)
    page_obj, query_string = _paginate(request, queryset)
    return render(
        request,
        "transport/vehicle_list.html",
        {
            "page_title": "Vehicles",
            "vehicles": page_obj.object_list,
            "page_obj": page_obj,
            "query_string": query_string,
            "q": q,
            "status_filter": status,
            "type_filter": vehicle_type,
            "status_choices": Vehicle.Status.choices,
            "type_choices": Vehicle.VehicleType.choices,
        },
    )


@manager_required
def vehicle_create(request):
    form = VehicleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        vehicle = form.save()
        messages.success(request, f"Vehicle {vehicle.plate_number} created successfully.")
        return redirect(vehicle)
    return render(
        request,
        "transport/vehicle_form.html",
        {"form": form, "page_title": "Add vehicle", "is_editing": False},
    )


@manager_required
def vehicle_detail(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    trips = vehicle.trips.select_related("route", "driver").all()[:10]
    expenses = vehicle.transport_expenses.select_related("trip", "driver").all()[:10]
    return render(
        request,
        "transport/vehicle_detail.html",
        {
            "page_title": vehicle.plate_number,
            "vehicle": vehicle,
            "trips": trips,
            "expenses": expenses,
            "total_revenue": _money_total(
                vehicle.trips.exclude(status=Trip.Status.CANCELLED), "amount_charged"
            ),
            "total_expenses": _money_total(vehicle.transport_expenses.all()),
        },
    )


@manager_required
def vehicle_edit(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    form = VehicleForm(request.POST or None, instance=vehicle)
    if request.method == "POST" and form.is_valid():
        vehicle = form.save()
        messages.success(request, "Vehicle updated successfully.")
        return redirect(vehicle)
    return render(
        request,
        "transport/vehicle_form.html",
        {
            "form": form,
            "vehicle": vehicle,
            "page_title": "Edit vehicle",
            "is_editing": True,
        },
    )


@management_required
def vehicle_delete(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    return _delete_object(
        request,
        vehicle,
        "Vehicle deleted successfully.",
        "transport-vehicle-list",
        "transport/vehicle_confirm_delete.html",
    )


# -----------------------------------------------------------------------------
# Drivers
# -----------------------------------------------------------------------------
@manager_required
def driver_list(request):
    queryset = Driver.objects.select_related("assigned_vehicle")
    q = (request.GET.get("q") or "").strip()
    active = (request.GET.get("active") or "").strip()
    vehicle_id = (request.GET.get("vehicle") or "").strip()
    if q:
        queryset = queryset.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(phone__icontains=q)
            | Q(license_number__icontains=q)
        )
    if active == "yes":
        queryset = queryset.filter(is_active=True)
    elif active == "no":
        queryset = queryset.filter(is_active=False)
    if vehicle_id.isdigit():
        queryset = queryset.filter(assigned_vehicle_id=vehicle_id)
    page_obj, query_string = _paginate(request, queryset)
    return render(
        request,
        "transport/driver_list.html",
        {
            "page_title": "Drivers",
            "drivers": page_obj.object_list,
            "page_obj": page_obj,
            "query_string": query_string,
            "q": q,
            "active_filter": active,
            "vehicle_filter": vehicle_id,
            "vehicles": Vehicle.objects.order_by("plate_number"),
        },
    )


@manager_required
def driver_create(request):
    form = DriverForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        driver = form.save()
        messages.success(request, f"Driver {driver.full_name} created successfully.")
        return redirect(driver)
    return render(
        request,
        "transport/driver_form.html",
        {"form": form, "page_title": "Add driver", "is_editing": False},
    )


@manager_required
def driver_detail(request, pk):
    driver = get_object_or_404(Driver.objects.select_related("assigned_vehicle"), pk=pk)
    trips = driver.trips.select_related("route", "vehicle").all()[:10]
    expenses = driver.transport_expenses.select_related("trip", "vehicle").all()[:10]
    return render(
        request,
        "transport/driver_detail.html",
        {
            "page_title": driver.full_name,
            "driver": driver,
            "trips": trips,
            "expenses": expenses,
            "total_revenue": _money_total(
                driver.trips.exclude(status=Trip.Status.CANCELLED), "amount_charged"
            ),
            "total_expenses": _money_total(driver.transport_expenses.all()),
        },
    )


@manager_required
def driver_edit(request, pk):
    driver = get_object_or_404(Driver, pk=pk)
    form = DriverForm(request.POST or None, instance=driver)
    if request.method == "POST" and form.is_valid():
        driver = form.save()
        messages.success(request, "Driver updated successfully.")
        return redirect(driver)
    return render(
        request,
        "transport/driver_form.html",
        {
            "form": form,
            "driver": driver,
            "page_title": "Edit driver",
            "is_editing": True,
        },
    )


@management_required
def driver_delete(request, pk):
    driver = get_object_or_404(Driver, pk=pk)
    return _delete_object(
        request,
        driver,
        "Driver deleted successfully.",
        "transport-driver-list",
        "transport/driver_confirm_delete.html",
    )


# -----------------------------------------------------------------------------
# Trips
# -----------------------------------------------------------------------------
@manager_required
def trip_list(request):
    queryset = Trip.objects.select_related("route", "vehicle", "driver", "created_by")
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    payment_status = (request.GET.get("payment_status") or "").strip()
    route_id = (request.GET.get("route") or "").strip()
    vehicle_id = (request.GET.get("vehicle") or "").strip()
    driver_id = (request.GET.get("driver") or "").strip()
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))

    if q:
        queryset = queryset.filter(
            Q(trip_number__icontains=q)
            | Q(customer_name__icontains=q)
            | Q(customer_phone__icontains=q)
            | Q(origin__icontains=q)
            | Q(destination__icontains=q)
            | Q(vehicle__plate_number__icontains=q)
            | Q(driver__first_name__icontains=q)
            | Q(driver__last_name__icontains=q)
        )
    if status in dict(Trip.Status.choices):
        queryset = queryset.filter(status=status)
    if payment_status in dict(Trip.PaymentStatus.choices):
        queryset = queryset.filter(payment_status=payment_status)
    if route_id.isdigit():
        queryset = queryset.filter(route_id=route_id)
    if vehicle_id.isdigit():
        queryset = queryset.filter(vehicle_id=vehicle_id)
    if driver_id.isdigit():
        queryset = queryset.filter(driver_id=driver_id)
    if date_from:
        queryset = queryset.filter(departure_datetime__gte=_date_start(date_from))
    if date_to:
        queryset = queryset.filter(departure_datetime__lte=_date_end(date_to))

    filtered_revenue = _money_total(
        queryset.exclude(status=Trip.Status.CANCELLED), "amount_charged"
    )
    filtered_paid = _money_total(
        queryset.exclude(status=Trip.Status.CANCELLED), "amount_paid"
    )
    page_obj, query_string = _paginate(request, queryset, per_page=30)

    return render(
        request,
        "transport/trip_list.html",
        {
            "page_title": "Transport trips",
            "trips": page_obj.object_list,
            "page_obj": page_obj,
            "query_string": query_string,
            "filtered_revenue": filtered_revenue,
            "filtered_paid": filtered_paid,
            "filtered_balance": filtered_revenue - filtered_paid,
            "q": q,
            "status_filter": status,
            "payment_status_filter": payment_status,
            "route_filter": route_id,
            "vehicle_filter": vehicle_id,
            "driver_filter": driver_id,
            "date_from": date_from.isoformat() if date_from else "",
            "date_to": date_to.isoformat() if date_to else "",
            "status_choices": Trip.Status.choices,
            "payment_status_choices": Trip.PaymentStatus.choices,
            "routes": TransportRoute.objects.order_by("origin", "destination"),
            "vehicles": Vehicle.objects.order_by("plate_number"),
            "drivers": Driver.objects.order_by("first_name", "last_name"),
        },
    )


@manager_required
def trip_create(request):
    initial = {}
    route_id = request.GET.get("route")
    if route_id and str(route_id).isdigit():
        route = TransportRoute.objects.filter(pk=route_id, is_active=True).first()
        if route:
            initial = {
                "route": route,
                "origin": route.origin,
                "destination": route.destination,
                "distance_km": route.distance_km,
                "amount_charged": route.default_price,
            }
    form = TripForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            trip = form.save(commit=False)
            trip.created_by = request.user
            trip.save()
        messages.success(request, f"Trip {trip.trip_number} created successfully.")
        return redirect(trip)
    return render(
        request,
        "transport/trip_form.html",
        {"form": form, "page_title": "Record transport trip", "is_editing": False},
    )


@manager_required
def trip_detail(request, pk):
    trip = get_object_or_404(
        Trip.objects.select_related("route", "vehicle", "driver", "created_by"),
        pk=pk,
    )
    expenses = trip.expenses.select_related("vehicle", "driver", "recorded_by")
    return render(
        request,
        "transport/trip_detail.html",
        {
            "page_title": trip.trip_number,
            "trip": trip,
            "expenses": expenses,
        },
    )


@manager_required
def trip_edit(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    form = TripForm(request.POST or None, instance=trip)
    if request.method == "POST" and form.is_valid():
        trip = form.save()
        messages.success(request, "Trip updated successfully.")
        return redirect(trip)
    return render(
        request,
        "transport/trip_form.html",
        {
            "form": form,
            "trip": trip,
            "page_title": "Edit transport trip",
            "is_editing": True,
        },
    )


@require_POST
@manager_required
def trip_status_update(request, pk):
    action = (request.POST.get("action") or "").strip().lower()
    with transaction.atomic():
        trip = get_object_or_404(Trip.objects.select_for_update(), pk=pk)
        now = timezone.now()
        if action == "start" and trip.status == Trip.Status.SCHEDULED:
            trip.status = Trip.Status.IN_TRANSIT
            messages.success(request, "Trip marked as in transit.")
        elif action == "complete" and trip.status in {
            Trip.Status.SCHEDULED,
            Trip.Status.IN_TRANSIT,
        }:
            trip.status = Trip.Status.COMPLETED
            trip.arrival_datetime = trip.arrival_datetime or now
            if trip.odometer_end is not None:
                trip.vehicle.current_odometer = max(
                    trip.vehicle.current_odometer,
                    trip.odometer_end,
                )
                trip.vehicle.save(update_fields=["current_odometer", "updated_at"])
            messages.success(request, "Trip marked as completed.")
        elif action == "cancel" and trip.status != Trip.Status.COMPLETED:
            trip.status = Trip.Status.CANCELLED
            messages.success(request, "Trip cancelled.")
        elif action == "reopen" and request.user.is_manager_user:
            trip.status = Trip.Status.SCHEDULED
            trip.arrival_datetime = None
            messages.success(request, "Trip reopened as scheduled.")
        else:
            messages.error(request, "That status change is not allowed.")
            return redirect(trip)
        trip.save()
    return redirect(trip)


@management_required
def trip_delete(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    return _delete_object(
        request,
        trip,
        "Trip deleted successfully.",
        "transport-trip-list",
        "transport/trip_confirm_delete.html",
    )


# -----------------------------------------------------------------------------
# Expenses
# -----------------------------------------------------------------------------
@manager_required
def expense_list(request):
    queryset = TransportExpense.objects.select_related(
        "trip", "vehicle", "driver", "recorded_by"
    )
    q = (request.GET.get("q") or "").strip()
    category = (request.GET.get("category") or "").strip()
    vehicle_id = (request.GET.get("vehicle") or "").strip()
    trip_id = (request.GET.get("trip") or "").strip()
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))

    if q:
        queryset = queryset.filter(
            Q(expense_number__icontains=q)
            | Q(vendor__icontains=q)
            | Q(reference__icontains=q)
            | Q(description__icontains=q)
            | Q(vehicle__plate_number__icontains=q)
            | Q(trip__trip_number__icontains=q)
        )
    if category in dict(TransportExpense.Category.choices):
        queryset = queryset.filter(category=category)
    if vehicle_id.isdigit():
        queryset = queryset.filter(vehicle_id=vehicle_id)
    if trip_id.isdigit():
        queryset = queryset.filter(trip_id=trip_id)
    if date_from:
        queryset = queryset.filter(expense_date__gte=_date_start(date_from))
    if date_to:
        queryset = queryset.filter(expense_date__lte=_date_end(date_to))

    total_filtered = _money_total(queryset)
    page_obj, query_string = _paginate(request, queryset, per_page=30)
    return render(
        request,
        "transport/expense_list.html",
        {
            "page_title": "Transport expenses",
            "expenses": page_obj.object_list,
            "page_obj": page_obj,
            "query_string": query_string,
            "total_filtered": total_filtered,
            "q": q,
            "category_filter": category,
            "vehicle_filter": vehicle_id,
            "trip_filter": trip_id,
            "date_from": date_from.isoformat() if date_from else "",
            "date_to": date_to.isoformat() if date_to else "",
            "category_choices": TransportExpense.Category.choices,
            "vehicles": Vehicle.objects.order_by("plate_number"),
            "trips_filter": Trip.objects.order_by("-departure_datetime")[:200],
        },
    )


@manager_required
def expense_create(request):
    initial = {}
    trip_id = request.GET.get("trip")
    vehicle_id = request.GET.get("vehicle")
    driver_id = request.GET.get("driver")
    if trip_id and str(trip_id).isdigit():
        trip = Trip.objects.filter(pk=trip_id).first()
        if trip:
            initial = {"trip": trip, "vehicle": trip.vehicle, "driver": trip.driver}
    else:
        if vehicle_id and str(vehicle_id).isdigit():
            initial["vehicle"] = Vehicle.objects.filter(pk=vehicle_id).first()
        if driver_id and str(driver_id).isdigit():
            initial["driver"] = Driver.objects.filter(pk=driver_id).first()
    form = TransportExpenseForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False)
        expense.recorded_by = request.user
        expense.save()
        messages.success(request, f"Expense {expense.expense_number} recorded successfully.")
        if expense.trip_id:
            return redirect(expense.trip)
        return redirect("transport-expense-list")
    return render(
        request,
        "transport/expense_form.html",
        {"form": form, "page_title": "Record transport expense", "is_editing": False},
    )


@manager_required
def expense_edit(request, pk):
    expense = get_object_or_404(TransportExpense, pk=pk)
    form = TransportExpenseForm(request.POST or None, instance=expense)
    if request.method == "POST" and form.is_valid():
        expense = form.save()
        messages.success(request, "Transport expense updated successfully.")
        if expense.trip_id:
            return redirect(expense.trip)
        return redirect("transport-expense-list")
    return render(
        request,
        "transport/expense_form.html",
        {
            "form": form,
            "expense": expense,
            "page_title": "Edit transport expense",
            "is_editing": True,
        },
    )


@management_required
def expense_delete(request, pk):
    expense = get_object_or_404(TransportExpense, pk=pk)
    return _delete_object(
        request,
        expense,
        "Transport expense deleted successfully.",
        "transport-expense-list",
        "transport/expense_confirm_delete.html",
    )
