from django.contrib import admin

from .models import ReceiptSettings


@admin.register(ReceiptSettings)
class ReceiptSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Receipt header", {
            "fields": (
                "business_name", "receipt_title", "address", "phone",
                "email", "tin", "vrn", "header_note",
            )
        }),
        ("Receipt footer", {
            "fields": ("footer_line_1", "footer_line_2")
        }),
        ("Thermal layout", {
            "fields": (
                "characters_per_line", "feed_lines_before_cut",
                "show_customer_phone", "show_cashier",
            )
        }),
        ("Audit", {"fields": ("updated_at",)}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not ReceiptSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
