from django.contrib import admin
from .models import (
    CustomerCuttingService,
    Sale,
    SaleItem,
    SaleItemBatchUsage,
)

@admin.register(CustomerCuttingService)
class CustomerCuttingServiceAdmin(
    admin.ModelAdmin
):
    list_display = (
        "cutting_number",
        "sale",
        "sale_item",
        "quantity_cut",
        "number_of_cuts",
        "fee_per_cut",
        "total_fee",
        "amount_paid",
        "status",
        "service_date",
    )

    list_filter = (
        "status",
        "payment_method",
        "service_date",
    )

    search_fields = (
        "cutting_number",
        "sale__sale_number",
        "sale__customer__name",
        "sale_item__product__name",
        "sale_item__product__code",
    )

    autocomplete_fields = (
        "sale",
        "sale_item",
        "created_by",
        "completed_by",
    )

    readonly_fields = (
        "cutting_number",
        "total_fee",
        "amount_paid",
        "change_due",
        "completed_by",
        "completed_at",
        "created_at",
        "updated_at",
    )

    date_hierarchy = "service_date"

class SaleItemBatchUsageInline(
    admin.TabularInline
):
    model = SaleItemBatchUsage
    extra = 0
    can_delete = False

    readonly_fields = (
        "batch",
        "quantity_used",
        "unit_cost",
        "total_cost",
    )


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1

    fields = (
        "product",
        "quantity",
        "unit_price",
        "line_discount",
        "line_total",
        "cost_total",
        "profit_amount",
    )

    readonly_fields = (
        "line_total",
        "cost_total",
        "profit_amount",
    )


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "sale_number",
        "sale_date",
        "customer",
        "payment_method",
        "total_amount",
        "amount_paid",
        "change_due",
        "status",
        "created_by",
    )

    list_filter = (
        "status",
        "payment_method",
        "sale_date",
    )

    search_fields = (
        "sale_number",
        "customer__name",
        "customer__phone",
        "notes",
    )

    autocomplete_fields = (
        "customer",
        "created_by",
        "completed_by",
    )

    readonly_fields = (
        "sale_number",
        "subtotal",
        "total_amount",
        "amount_paid",
        "change_due",
        "completed_by",
        "completed_at",
        "created_at",
        "updated_at",
    )

    inlines = [
        SaleItemInline,
    ]

    date_hierarchy = "sale_date"


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = (
        "sale",
        "product",
        "quantity",
        "unit_price",
        "line_total",
        "cost_total",
        "profit_amount",
    )

    search_fields = (
        "sale__sale_number",
        "product__name",
        "product__code",
    )

    autocomplete_fields = (
        "sale",
        "product",
    )

    readonly_fields = (
        "line_total",
        "cost_total",
        "profit_amount",
    )

    inlines = [
        SaleItemBatchUsageInline,
        
    ]

    