from django.contrib import admin

from .models import (
    BankAccount,
    BusinessProfile,
    Document,
    DocumentItem,
)


class BankAccountInline(
    admin.TabularInline
):
    model = BankAccount
    extra = 1


@admin.register(BusinessProfile)
class BusinessProfileAdmin(
    admin.ModelAdmin
):
    inlines = [
        BankAccountInline,
    ]

    readonly_fields = (
        "next_invoice_number",
        "next_delivery_note_number",
    )

    fieldsets = (
        (
            "Brand",
            {
                "fields": (
                    "company_name",
                    "logo",
                )
            },
        ),
        (
            "Contact details",
            {
                "fields": (
                    "email",
                    "phone_1",
                    "phone_2",
                    "address",
                    "tin",
                    "vrn",
                )
            },
        ),
        (
            "Automatic numbering",
            {
                "fields": (
                    "next_invoice_number",
                    "next_delivery_note_number",
                ),
                "description": (
                    "These counters are managed "
                    "automatically by the system."
                ),
            },
        ),
    )

    def has_add_permission(
        self,
        request,
    ):
        if BusinessProfile.objects.exists():
            return False

        return super().has_add_permission(
            request
        )


class DocumentItemInline(
    admin.TabularInline
):
    model = DocumentItem
    extra = 0


@admin.register(Document)
class DocumentAdmin(
    admin.ModelAdmin
):
    list_display = (
        "document_number",
        "document_type",
        "customer_name",
        "date",
        "status",
        "created_by",
    )

    list_filter = (
        "document_type",
        "status",
        "date",
    )

    search_fields = (
        "document_number",
        "customer_name",
        "customer_phone",
        "customer_reference",
    )

    readonly_fields = (
        "document_number",
        "share_token",
        "created_at",
        "updated_at",
    )

    inlines = [
        DocumentItemInline,
    ]


@admin.register(BankAccount)
class BankAccountAdmin(
    admin.ModelAdmin
):
    list_display = (
        "bank_name",
        "account_name",
        "account_number",
        "is_active",
        "sort_order",
    )

    list_filter = (
        "is_active",
    )
