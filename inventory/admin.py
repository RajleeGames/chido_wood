from django.contrib import admin

from .models import (
    ConversionBatchUsage,
    ConversionOutput,
    StockAdjustment,
    StockAdjustmentBatchUsage,
    StockBatch,
    StockMovement,
    WoodConversion,
)


@admin.register(StockBatch)
class StockBatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "product",
        "source_type",
        "source_reference",
        "supplier",
        "received_quantity",
        "remaining_quantity",
        "unit_cost",
        "received_at",
        "is_active",
    )

    list_filter = (
        "source_type",
        "is_active",
        "received_at",
    )

    search_fields = (
        "product__name",
        "product__code",
        "source_reference",
        "supplier__name",
    )

    autocomplete_fields = (
        "product",
        "supplier",
        "created_by",
    )

    readonly_fields = (
        "created_at",
    )

    ordering = (
        "received_at",
        "id",
    )

    list_select_related = (
        "product",
        "supplier",
        "created_by",
    )

    date_hierarchy = "received_at"


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "product",
        "movement_type",
        "quantity_delta",
        "unit_cost",
        "total_cost",
        "batch",
        "reference",
        "created_by",
    )

    list_filter = (
        "movement_type",
        "created_at",
    )

    search_fields = (
        "product__name",
        "product__code",
        "reference",
        "notes",
    )

    autocomplete_fields = (
        "product",
        "batch",
        "created_by",
    )

    readonly_fields = (
        "created_at",
    )

    ordering = (
        "-created_at",
        "-id",
    )

    list_select_related = (
        "product",
        "batch",
        "created_by",
    )

    date_hierarchy = "created_at"


class StockAdjustmentBatchUsageInline(
    admin.TabularInline
):
    model = StockAdjustmentBatchUsage
    extra = 0
    can_delete = False

    fields = (
        "batch",
        "quantity_used",
        "unit_cost",
        "total_cost",
    )

    readonly_fields = (
        "batch",
        "quantity_used",
        "unit_cost",
        "total_cost",
    )

    autocomplete_fields = (
        "batch",
    )


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = (
        "adjustment_number",
        "adjustment_date",
        "product",
        "adjustment_type",
        "quantity",
        "unit_cost",
        "total_cost",
        "status",
        "created_by",
        "posted_by",
    )

    list_filter = (
        "adjustment_type",
        "status",
        "adjustment_date",
    )

    search_fields = (
        "adjustment_number",
        "product__name",
        "product__code",
        "reason",
        "notes",
    )

    autocomplete_fields = (
        "product",
        "created_batch",
        "created_by",
        "posted_by",
    )

    readonly_fields = (
        "adjustment_number",
        "total_cost",
        "created_batch",
        "posted_by",
        "posted_at",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Adjustment information",
            {
                "fields": (
                    "adjustment_number",
                    "product",
                    "adjustment_type",
                    "adjustment_date",
                    "quantity",
                    "unit_cost",
                )
            },
        ),
        (
            "Reason and notes",
            {
                "fields": (
                    "reason",
                    "notes",
                )
            },
        ),
        (
            "Posting information",
            {
                "fields": (
                    "status",
                    "total_cost",
                    "created_batch",
                    "created_by",
                    "posted_by",
                    "posted_at",
                )
            },
        ),
        (
            "Audit information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    inlines = [
        StockAdjustmentBatchUsageInline,
    ]

    ordering = (
        "-adjustment_date",
        "-id",
    )

    list_select_related = (
        "product",
        "created_by",
        "posted_by",
        "created_batch",
    )

    date_hierarchy = "adjustment_date"


class ConversionOutputInline(admin.TabularInline):
    model = ConversionOutput
    extra = 1

    fields = (
        "product",
        "quantity",
        "allocated_cost",
        "unit_cost",
        "output_batch",
    )

    readonly_fields = (
        "allocated_cost",
        "unit_cost",
        "output_batch",
    )

    autocomplete_fields = (
        "product",
    )


class ConversionBatchUsageInline(
    admin.TabularInline
):
    model = ConversionBatchUsage
    extra = 0
    can_delete = False

    fields = (
        "batch",
        "quantity_used",
        "unit_cost",
        "total_cost",
    )

    readonly_fields = (
        "batch",
        "quantity_used",
        "unit_cost",
        "total_cost",
    )

    autocomplete_fields = (
        "batch",
    )


@admin.register(WoodConversion)
class WoodConversionAdmin(admin.ModelAdmin):
    list_display = (
        "conversion_number",
        "conversion_date",
        "source_product",
        "source_quantity",
        "additional_cutting_cost",
        "source_cost",
        "total_conversion_cost",
        "status",
        "created_by",
        "posted_by",
    )

    list_filter = (
        "status",
        "conversion_date",
    )

    search_fields = (
        "conversion_number",
        "source_product__name",
        "source_product__code",
        "notes",
    )

    autocomplete_fields = (
        "source_product",
        "created_by",
        "posted_by",
    )

    readonly_fields = (
        "conversion_number",
        "source_cost",
        "total_conversion_cost",
        "posted_by",
        "posted_at",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Conversion information",
            {
                "fields": (
                    "conversion_number",
                    "conversion_date",
                    "source_product",
                    "source_quantity",
                    "additional_cutting_cost",
                )
            },
        ),
        (
            "Cost information",
            {
                "fields": (
                    "source_cost",
                    "total_conversion_cost",
                )
            },
        ),
        (
            "Notes",
            {
                "fields": (
                    "notes",
                )
            },
        ),
        (
            "Posting information",
            {
                "fields": (
                    "status",
                    "created_by",
                    "posted_by",
                    "posted_at",
                )
            },
        ),
        (
            "Audit information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    inlines = [
        ConversionOutputInline,
        ConversionBatchUsageInline,
    ]

    ordering = (
        "-conversion_date",
        "-id",
    )

    list_select_related = (
        "source_product",
        "created_by",
        "posted_by",
    )

    date_hierarchy = "conversion_date"