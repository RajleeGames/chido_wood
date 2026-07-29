from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.inventory_list,
        name="inventory-list",
    ),

    # Stock adjustments
    path(
        "adjustments/",
        views.stock_adjustment_list,
        name="stock-adjustment-list",
    ),
    path(
        "adjustments/new/",
        views.stock_adjustment_create,
        name="stock-adjustment-create",
    ),
    path(
        "adjustments/<int:pk>/",
        views.stock_adjustment_detail,
        name="stock-adjustment-detail",
    ),
    path(
        "adjustments/<int:pk>/edit/",
        views.stock_adjustment_edit,
        name="stock-adjustment-edit",
    ),
    path(
        "adjustments/<int:pk>/post/",
        views.stock_adjustment_post,
        name="stock-adjustment-post",
    ),
    path(
        "adjustments/<int:pk>/cancel/",
        views.stock_adjustment_cancel,
        name="stock-adjustment-cancel",
    ),

    # Wood conversions
    path(
        "conversions/",
        views.wood_conversion_list,
        name="wood-conversion-list",
    ),
    path(
        "conversions/new/",
        views.wood_conversion_create,
        name="wood-conversion-create",
    ),
    path(
        "conversions/<int:pk>/",
        views.wood_conversion_detail,
        name="wood-conversion-detail",
    ),
    path(
        "conversions/<int:pk>/edit/",
        views.wood_conversion_edit,
        name="wood-conversion-edit",
    ),
    path(
        "conversions/<int:pk>/post/",
        views.wood_conversion_post,
        name="wood-conversion-post",
    ),
    path(
        "conversions/<int:pk>/cancel/",
        views.wood_conversion_cancel,
        name="wood-conversion-cancel",
    ),

    # Product inventory detail must remain last.
    path(
        "<int:pk>/",
        views.inventory_detail,
        name="inventory-detail",
    ),
]