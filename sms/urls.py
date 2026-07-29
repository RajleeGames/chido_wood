from django.urls import path

from . import views


urlpatterns = [
    path("", views.sms_dashboard, name="sms-dashboard"),
    path("send/", views.sms_compose, name="sms-compose"),
    path("balance/check/", views.sms_check_balance, name="sms-check-balance"),

    path("contacts/", views.sms_contact_list, name="sms-contact-list"),
    path("contacts/new/", views.sms_contact_create, name="sms-contact-create"),
    path("contacts/import/", views.sms_contact_import, name="sms-contact-import"),
    path("contacts/export/", views.sms_contact_export, name="sms-contact-export"),
    path("contacts/sync-customers/", views.sms_sync_customers, name="sms-sync-customers"),
    path("contacts/<int:pk>/", views.sms_contact_detail, name="sms-contact-detail"),
    path("contacts/<int:pk>/edit/", views.sms_contact_edit, name="sms-contact-edit"),
    path("contacts/<int:pk>/toggle/", views.sms_contact_toggle, name="sms-contact-toggle"),
    path("contacts/<int:pk>/delete/", views.sms_contact_delete, name="sms-contact-delete"),

    path("groups/", views.sms_group_list, name="sms-group-list"),
    path("groups/new/", views.sms_group_create, name="sms-group-create"),
    path("groups/<int:pk>/edit/", views.sms_group_edit, name="sms-group-edit"),
    path("groups/<int:pk>/delete/", views.sms_group_delete, name="sms-group-delete"),

    path("templates/", views.sms_template_list, name="sms-template-list"),
    path("templates/new/", views.sms_template_create, name="sms-template-create"),
    path("templates/<int:pk>/edit/", views.sms_template_edit, name="sms-template-edit"),
    path("templates/<int:pk>/delete/", views.sms_template_delete, name="sms-template-delete"),

    path("senders/", views.sms_sender_list, name="sms-sender-list"),
    path("senders/new/", views.sms_sender_create, name="sms-sender-create"),
    path("senders/<int:pk>/edit/", views.sms_sender_edit, name="sms-sender-edit"),
    path("senders/<int:pk>/delete/", views.sms_sender_delete, name="sms-sender-delete"),

    path("campaigns/", views.sms_campaign_list, name="sms-campaign-list"),
    path("campaigns/<int:pk>/", views.sms_campaign_detail, name="sms-campaign-detail"),
    path("campaigns/<int:pk>/sync/", views.sms_campaign_sync, name="sms-campaign-sync"),

    path("messages/", views.sms_message_list, name="sms-message-list"),
    path("messages/<int:pk>/", views.sms_message_detail, name="sms-message-detail"),
    path("messages/<int:pk>/sync/", views.sms_message_sync, name="sms-message-sync"),

    path("settings/", views.sms_settings, name="sms-settings"),
]
