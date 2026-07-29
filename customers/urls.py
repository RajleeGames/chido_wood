from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.customer_list,
        name="customer-list",
    ),

    # Customer accounts and debts
    path(
        "accounts/",
        views.customer_account_list,
        name="customer-account-list",
    ),
    path(
        "accounts/<int:pk>/",
        views.customer_account_detail,
        name="customer-account-detail",
    ),
    path(
        "accounts/<int:pk>/payments/new/",
        views.customer_payment_create,
        name="customer-payment-create",
    ),

    # Customer payments
    path(
        "payments/<int:pk>/",
        views.customer_payment_detail,
        name="customer-payment-detail",
    ),
    path(
        "payments/<int:pk>/receipt/",
        views.customer_payment_receipt,
        name="customer-payment-receipt",
    ),
    path(
        "payments/<int:pk>/cancel/",
        views.customer_payment_cancel,
        name="customer-payment-cancel",
    ),

    # Normal customer detail must remain last.
    path(
        "<int:pk>/",
        views.customer_detail,
        name="customer-detail",
    ),
]