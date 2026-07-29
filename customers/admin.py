from django.contrib import admin

from .models import (
    Customer,
    CustomerPayment,
    CustomerPaymentAllocation,
)


class CustomerPaymentAllocationInline(
    admin.TabularInline
):
    model = CustomerPaymentAllocation
    extra = 0
    can_delete = False

    readonly_fields = (
        "allocation_type",
        "sale",
        "cutting_service",
        "amount",
        "created_at",
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "customer_code",
        "name",
        "phone",
        "opening_balance",
        "opening_balance_paid",
        "credit_limit",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
        "created_at",
    )

    search_fields = (
        "customer_code",
        "name",
        "phone",
        "email",
        "address",
    )

    readonly_fields = (
        "customer_code",
        "opening_balance_paid",
        "created_by",
        "created_at",
        "updated_at",
    )


@admin.register(CustomerPayment)
class CustomerPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "payment_number",
        "customer",
        "payment_date",
        "amount",
        "payment_method",
        "status",
        "created_by",
    )

    list_filter = (
        "status",
        "payment_method",
        "payment_date",
    )

    search_fields = (
        "payment_number",
        "customer__name",
        "customer__phone",
        "reference",
    )

    readonly_fields = (
        "payment_number",
        "status",
        "created_by",
        "cancelled_by",
        "cancelled_at",
        "created_at",
        "updated_at",
    )

    inlines = [
        CustomerPaymentAllocationInline,
    ]

    date_hierarchy = "payment_date"