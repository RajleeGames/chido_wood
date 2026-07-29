from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "allow_cutting",
        "default_cutting_fee",
        "is_active",
    )

    list_filter = (
        "allow_cutting",
        "is_active",
    )

    search_fields = (
        "name",
        "code",
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "category",
        "measurement_unit",
        "selling_price",
        "allow_customer_cutting",
        "track_stock",
        "is_active",
    )

    list_filter = (
        "category",
        "measurement_unit",
        "allow_customer_cutting",
        "track_stock",
        "is_active",
    )

    search_fields = (
        "name",
        "code",
        "barcode",
        "wood_type",
        "dimension_note",
    )

    autocomplete_fields = (
        "category",
    )