from django.contrib import admin

from .models import (
    SMSCampaign,
    SMSContact,
    SMSContactGroup,
    SMSImportBatch,
    SMSMessage,
    SMSSetting,
    SMSTemplate,
    SenderID,
)


@admin.register(SenderID)
class SenderIDAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "status",
        "is_default",
        "is_active",
        "requested_at",
        "approved_at",
    )
    list_filter = ("status", "is_default", "is_active")
    search_fields = ("name", "provider_reference")
    readonly_fields = ("requested_at", "approved_at", "created_at", "updated_at")
    raw_id_fields = ("created_by",)


@admin.register(SMSSetting)
class SMSSettingAdmin(admin.ModelAdmin):
    list_display = (
        "business_name",
        "provider",
        "default_sender",
        "transaction_sms_enabled",
        "promotional_sms_enabled",
        "automatic_sale_sms_enabled",
        "cached_balance",
        "balance_checked_at",
    )
    readonly_fields = ("cached_balance", "balance_checked_at", "created_at", "updated_at")

    def has_add_permission(self, request):
        return not SMSSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SMSContactGroup)
class SMSContactGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "created_at")
    search_fields = ("name", "description")
    raw_id_fields = ("created_by",)


@admin.register(SMSContact)
class SMSContactAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "phone",
        "source",
        "is_active",
        "allow_transaction_sms",
        "allow_promotional_sms",
        "opted_out",
        "last_purchase_at",
    )
    list_filter = (
        "source",
        "is_active",
        "allow_transaction_sms",
        "allow_promotional_sms",
        "opted_out",
        "groups",
    )
    search_fields = ("name", "phone", "email")
    raw_id_fields = ("customer", "created_by")
    filter_horizontal = ("groups",)
    readonly_fields = ("created_at", "updated_at", "opted_out_at", "last_purchase_at")


@admin.register(SMSTemplate)
class SMSTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "language", "is_active", "created_at")
    list_filter = ("category", "language", "is_active")
    search_fields = ("title", "message")
    raw_id_fields = ("created_by",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(SMSCampaign)
class SMSCampaignAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "message_type",
        "status",
        "sender_id",
        "total_recipients",
        "sent_count",
        "delivered_count",
        "failed_count",
        "created_at",
    )
    list_filter = ("message_type", "status", "sender_id")
    search_fields = ("title", "message")
    raw_id_fields = ("template", "sender_id", "created_by")
    filter_horizontal = ("groups", "contacts")
    readonly_fields = (
        "total_recipients",
        "sent_count",
        "delivered_count",
        "failed_count",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    )


@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
    list_display = (
        "dest_addr",
        "status",
        "message_type",
        "sender_id",
        "campaign",
        "sms_parts",
        "is_automatic",
        "sent_at",
        "delivered_at",
    )
    list_filter = ("status", "message_type", "sender_id", "is_automatic")
    search_fields = (
        "dest_addr",
        "message",
        "request_id",
        "recipient_id",
        "contact__name",
        "campaign__title",
    )
    raw_id_fields = (
        "campaign",
        "contact",
        "customer",
        "sale",
        "sender_id",
        "created_by",
    )
    readonly_fields = (
        "provider_response",
        "created_at",
        "updated_at",
        "sent_at",
        "delivered_at",
    )
    date_hierarchy = "created_at"


@admin.register(SMSImportBatch)
class SMSImportBatchAdmin(admin.ModelAdmin):
    list_display = (
        "source_name",
        "total_rows",
        "created_count",
        "updated_count",
        "skipped_count",
        "created_by",
        "created_at",
    )
    readonly_fields = (
        "source_name",
        "total_rows",
        "created_count",
        "updated_count",
        "skipped_count",
        "error_rows",
        "created_by",
        "created_at",
    )
