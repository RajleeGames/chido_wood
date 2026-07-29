from django.urls import path

from . import views


urlpatterns = [
    # Sales list
    path(
        "",
        views.sale_list,
        name="sale-list",
    ),

    # Customer cutting services
    path(
        "cutting/",
        views.cutting_service_list,
        name="cutting-service-list",
    ),
    path(
        "<int:sale_pk>/cutting/new/",
        views.cutting_service_create,
        name="cutting-service-create",
    ),
    path(
        "cutting/<int:pk>/",
        views.cutting_service_detail,
        name="cutting-service-detail",
    ),
    path(
        "cutting/<int:pk>/edit/",
        views.cutting_service_edit,
        name="cutting-service-edit",
    ),
    path(
        "cutting/<int:pk>/complete/",
        views.cutting_service_complete,
        name="cutting-service-complete",
    ),
    path(
        "cutting/<int:pk>/cancel/",
        views.cutting_service_cancel,
        name="cutting-service-cancel",
    ),

    # Normal sales
    path(
        "new/",
        views.sale_create,
        name="sale-create",
    ),
    path(
        "<int:pk>/",
        views.sale_detail,
        name="sale-detail",
    ),
    path(
        "<int:pk>/edit/",
        views.sale_edit,
        name="sale-edit",
    ),
    path(
        "<int:pk>/complete/",
        views.sale_complete,
        name="sale-complete",
    ),
    path(
        "<int:pk>/cancel/",
        views.sale_cancel,
        name="sale-cancel",
    ),
    path(
        "<int:pk>/receipt/",
        views.sale_receipt,
        name="sale-receipt",
    ),
]