from django.contrib import admin

from .models import (
    Supplier,
    SupplierPayment,
    SupplierPaymentAllocation,
)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "contact_person",
        "phone",
        "tin",
        "opening_balance",
        "opening_balance_paid",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = (
        "name",
        "contact_person",
        "phone",
        "email",
        "tin",
    )
    readonly_fields = ("opening_balance_paid",)


class SupplierPaymentAllocationInline(admin.TabularInline):
    model = SupplierPaymentAllocation
    extra = 0
    readonly_fields = (
        "allocation_type",
        "purchase",
        "amount",
        "created_at",
    )
    can_delete = False


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "payment_number",
        "supplier",
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
        "supplier__name",
        "reference",
    )
    readonly_fields = (
        "payment_number",
        "supplier",
        "payment_date",
        "amount",
        "payment_method",
        "reference",
        "notes",
        "status",
        "created_by",
        "cancelled_by",
        "cancelled_at",
        "cancellation_reason",
        "created_at",
        "updated_at",
    )
    inlines = [SupplierPaymentAllocationInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SupplierPaymentAllocation)
class SupplierPaymentAllocationAdmin(admin.ModelAdmin):
    list_display = (
        "payment",
        "allocation_type",
        "purchase",
        "amount",
    )
    list_filter = ("allocation_type",)
    search_fields = (
        "payment__payment_number",
        "payment__supplier__name",
        "purchase__purchase_number",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
