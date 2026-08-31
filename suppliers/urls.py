from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.supplier_list,
        name="supplier-list",
    ),

    path(
        "accounts/",
        views.supplier_account_list,
        name="supplier-account-list",
    ),
    path(
        "accounts/<int:pk>/",
        views.supplier_account_detail,
        name="supplier-account-detail",
    ),
    path(
        "accounts/<int:pk>/payments/new/",
        views.supplier_payment_create,
        name="supplier-payment-create",
    ),

    path(
        "payments/<int:pk>/",
        views.supplier_payment_detail,
        name="supplier-payment-detail",
    ),
    path(
        "payments/<int:pk>/receipt/",
        views.supplier_payment_receipt,
        name="supplier-payment-receipt",
    ),
    path(
        "payments/<int:pk>/cancel/",
        views.supplier_payment_cancel,
        name="supplier-payment-cancel",
    ),
]
