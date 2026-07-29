from django.contrib import admin

from .models import Purchase, PurchaseItem


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1

    readonly_fields = (
        "allocated_cost",
        "effective_unit_cost",
        "stock_batch",
    )


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "purchase_number",
        "supplier",
        "purchase_date",
        "payment_method",
        "total_amount",
        "amount_paid",
        "status",
        "created_by",
    )

    list_filter = (
        "status",
        "payment_method",
        "purchase_date",
    )

    search_fields = (
        "purchase_number",
        "supplier__name",
        "supplier_invoice_number",
    )

    autocomplete_fields = (
        "supplier",
        "created_by",
        "posted_by",
    )

    readonly_fields = (
        "purchase_number",
        "subtotal",
        "total_amount",
        "posted_by",
        "posted_at",
        "created_at",
        "updated_at",
    )

    inlines = [
        PurchaseItemInline,
    ]