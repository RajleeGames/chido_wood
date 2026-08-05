from django.urls import path

from . import views


urlpatterns = [
    path("", views.transport_dashboard, name="transport-dashboard"),

    path("routes/", views.route_list, name="transport-route-list"),
    path("routes/add/", views.route_create, name="transport-route-create"),
    path("routes/<int:pk>/edit/", views.route_edit, name="transport-route-edit"),
    path("routes/<int:pk>/delete/", views.route_delete, name="transport-route-delete"),

    path("vehicles/", views.vehicle_list, name="transport-vehicle-list"),
    path("vehicles/add/", views.vehicle_create, name="transport-vehicle-create"),
    path("vehicles/<int:pk>/", views.vehicle_detail, name="transport-vehicle-detail"),
    path("vehicles/<int:pk>/edit/", views.vehicle_edit, name="transport-vehicle-edit"),
    path("vehicles/<int:pk>/delete/", views.vehicle_delete, name="transport-vehicle-delete"),

    path("drivers/", views.driver_list, name="transport-driver-list"),
    path("drivers/add/", views.driver_create, name="transport-driver-create"),
    path("drivers/<int:pk>/", views.driver_detail, name="transport-driver-detail"),
    path("drivers/<int:pk>/edit/", views.driver_edit, name="transport-driver-edit"),
    path("drivers/<int:pk>/delete/", views.driver_delete, name="transport-driver-delete"),

    path("trips/", views.trip_list, name="transport-trip-list"),
    path("trips/add/", views.trip_create, name="transport-trip-create"),
    path("trips/<int:pk>/", views.trip_detail, name="transport-trip-detail"),
    path("trips/<int:pk>/edit/", views.trip_edit, name="transport-trip-edit"),
    path("trips/<int:pk>/status/", views.trip_status_update, name="transport-trip-status"),
    path("trips/<int:pk>/delete/", views.trip_delete, name="transport-trip-delete"),

    path("expenses/", views.expense_list, name="transport-expense-list"),
    path("expenses/add/", views.expense_create, name="transport-expense-create"),
    path("expenses/<int:pk>/edit/", views.expense_edit, name="transport-expense-edit"),
    path("expenses/<int:pk>/delete/", views.expense_delete, name="transport-expense-delete"),
]
