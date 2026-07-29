from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import (
    can_manage_sms,
    can_send_promotional_sms,
    sms_manage_required,
    sms_required,
)
from .forms import (
    SMSContactForm,
    SMSContactGroupForm,
    SMSImportForm,
    SMSSendForm,
    SMSSettingForm,
    SMSTemplateForm,
    SenderIDForm,
)
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
from .services.beem import check_balance, credentials_configured
from .services.contacts import sync_all_customer_contacts
from .services.delivery import sync_campaign_delivery, sync_message_delivery
from .services.importing import import_contacts
from .services.personalization import calculate_sms_parts
from .services.sending import send_personalized_messages


FAILED_STATUSES = [
    SMSMessage.Status.FAILED,
    SMSMessage.Status.UNDELIVERED,
    SMSMessage.Status.REJECTED,
    SMSMessage.Status.EXPIRED,
]


def _base_context(request, active_page):
    return {
        "sms_active_page": active_page,
        "sms_can_manage": can_manage_sms(request.user),
        "sms_can_send_promotional": can_send_promotional_sms(request.user),
    }


def _paginate(request, queryset, per_page=25):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("page"))


def _extract_balance(payload):
    if not isinstance(payload, dict):
        return None

    candidates = [payload]
    data = payload.get("data")
    if isinstance(data, dict):
        candidates.append(data)

    for candidate in candidates:
        for key in ("balance", "credit_balance", "sms_balance", "amount"):
            value = candidate.get(key)
            if value in (None, ""):
                continue
            try:
                return Decimal(str(value).replace(",", ""))
            except (InvalidOperation, ValueError):
                continue

    return None


@sms_required
def sms_dashboard(request):
    today = timezone.localdate()
    setting = SMSSetting.load()

    contact_queryset = SMSContact.objects.all()
    campaign_queryset = SMSCampaign.objects.all()
    message_queryset = SMSMessage.objects.all()

    context = {
        "page_title": "SMS Center",
        "setting": setting,
        "credentials_ready": credentials_configured(),
        "summary": {
            "contacts": contact_queryset.count(),
            "active_contacts": contact_queryset.filter(is_active=True).count(),
            "promotional_contacts": contact_queryset.filter(
                is_active=True,
                opted_out=False,
                allow_promotional_sms=True,
            ).count(),
            "messages_today": message_queryset.filter(created_at__date=today).count(),
            "sent": message_queryset.filter(
                status__in=[SMSMessage.Status.SENT, SMSMessage.Status.DELIVERED]
            ).count(),
            "delivered": message_queryset.filter(
                status=SMSMessage.Status.DELIVERED
            ).count(),
            "failed": message_queryset.filter(status__in=FAILED_STATUSES).count(),
            "campaigns": campaign_queryset.count(),
            "senders_ready": SenderID.objects.filter(
                status=SenderID.Status.APPROVED,
                is_active=True,
            ).count(),
        },
        "recent_messages": message_queryset.select_related(
            "contact", "sender_id", "campaign"
        )[:10],
        "recent_campaigns": campaign_queryset.select_related(
            "sender_id", "template", "created_by"
        )[:6],
        **_base_context(request, "dashboard"),
    }

    return render(request, "sms/dashboard.html", context)


@sms_required
def sms_compose(request):
    allow_promotional = can_send_promotional_sms(request.user)
    form = SMSSendForm(
        request.POST or None,
        allow_promotional=allow_promotional,
    )

    template_data = {
        str(template.pk): {
            "message": template.message,
            "language": template.language,
            "category": template.category,
        }
        for template in SMSTemplate.objects.filter(is_active=True)
    }

    if request.method == "GET":
        contact_id = str(request.GET.get("contact") or "").strip()
        if contact_id.isdigit():
            contact = SMSContact.objects.filter(pk=contact_id, is_active=True).first()
            if contact:
                form.fields["audience"].initial = SMSSendForm.AUDIENCE_SELECTED
                form.fields["contacts"].initial = [contact.pk]

        template_id = str(request.GET.get("template") or "").strip()
        if template_id and template_id in template_data:
            form.fields["template"].initial = template_id
            form.fields["message"].initial = template_data[template_id]["message"]
            form.fields["language"].initial = template_data[template_id]["language"]

    if request.method == "POST" and form.is_valid():
        cleaned = form.cleaned_data
        audience = cleaned["audience"]
        contacts = SMSContact.objects.none()
        groups = SMSContactGroup.objects.none()
        manual_numbers = cleaned.get("normalized_manual_numbers", [])

        if audience == SMSSendForm.AUDIENCE_SELECTED:
            contacts = cleaned["contacts"]
        elif audience == SMSSendForm.AUDIENCE_GROUPS:
            groups = cleaned["groups"]
            contacts = SMSContact.objects.filter(
                groups__in=groups,
                is_active=True,
            ).distinct()
        elif audience == SMSSendForm.AUDIENCE_ALL_TRANSACTION:
            contacts = SMSContact.objects.filter(
                is_active=True,
                opted_out=False,
                allow_transaction_sms=True,
            )
        elif audience == SMSSendForm.AUDIENCE_ALL_PROMOTIONAL:
            contacts = SMSContact.objects.filter(
                is_active=True,
                opted_out=False,
                allow_promotional_sms=True,
            )

        recipient_estimate = contacts.values("id").distinct().count() + len(manual_numbers)
        title = str(cleaned.get("campaign_title") or "").strip()
        if not title:
            title = f"SMS {timezone.localtime():%d %b %Y %H:%M}"

        campaign = SMSCampaign.objects.create(
            title=title,
            template=cleaned.get("template"),
            message=cleaned["message"],
            sender_id=cleaned["sender"],
            message_type=cleaned["message_type"],
            status=SMSCampaign.Status.QUEUED,
            total_recipients=recipient_estimate,
            created_by=request.user,
        )
        campaign.contacts.set(contacts)
        campaign.groups.set(groups)

        result = send_personalized_messages(
            sender=cleaned["sender"],
            message_template=cleaned["message"],
            contacts=contacts,
            manual_numbers=manual_numbers,
            message_type=cleaned["message_type"],
            campaign=campaign,
            created_by=request.user,
            language=cleaned["language"],
        )

        if result.get("ok"):
            messages.success(
                request,
                f'SMS campaign "{campaign.title}" completed: '
                f'{result["sent"]} sent and {result["failed"]} failed.',
            )
            return redirect("sms-campaign-detail", pk=campaign.pk)

        if campaign.status == SMSCampaign.Status.QUEUED:
            campaign.status = SMSCampaign.Status.FAILED
            campaign.completed_at = timezone.now()
            campaign.save(update_fields=["status", "completed_at", "updated_at"])

        messages.error(request, result.get("error", "SMS sending failed."))

    context = {
        "page_title": "Send SMS",
        "form": form,
        "template_data": template_data,
        "setting": SMSSetting.load(),
        "sms_analysis": calculate_sms_parts(
            str(form.data.get("message") or form.initial.get("message") or "")
        ),
        **_base_context(request, "compose"),
    }
    return render(request, "sms/compose.html", context)


@sms_required
@require_POST
def sms_check_balance(request):
    result = check_balance()
    status_code = int(result.get("status_code") or 0)
    payload = result.get("json") or {}

    if 200 <= status_code < 300:
        setting = SMSSetting.load()
        balance = _extract_balance(payload)
        setting.balance_checked_at = timezone.now()
        update_fields = ["balance_checked_at", "updated_at"]
        if balance is not None:
            setting.cached_balance = balance
            update_fields.append("cached_balance")
        setting.save(update_fields=update_fields)
        messages.success(request, "SMS balance was refreshed successfully.")
    else:
        error = payload.get("error") if isinstance(payload, dict) else payload
        messages.error(request, f"Could not check SMS balance: {error or 'Provider error'}")

    return redirect(request.POST.get("next") or "sms-dashboard")


@sms_required
def sms_contact_list(request):
    query = str(request.GET.get("q") or "").strip()
    source = str(request.GET.get("source") or "").strip()
    status_filter = str(request.GET.get("status") or "").strip()
    group_id = str(request.GET.get("group") or "").strip()

    contacts = SMSContact.objects.select_related("customer").prefetch_related("groups")

    if query:
        contacts = contacts.filter(
            Q(name__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
        )
    if source in SMSContact.Source.values:
        contacts = contacts.filter(source=source)
    if status_filter == "active":
        contacts = contacts.filter(is_active=True)
    elif status_filter == "inactive":
        contacts = contacts.filter(is_active=False)
    elif status_filter == "opted_out":
        contacts = contacts.filter(opted_out=True)
    elif status_filter == "promotional":
        contacts = contacts.filter(
            is_active=True,
            opted_out=False,
            allow_promotional_sms=True,
        )
    if group_id.isdigit():
        contacts = contacts.filter(groups__id=group_id)

    page_obj = _paginate(request, contacts.distinct(), per_page=30)
    context = {
        "page_title": "SMS Contacts",
        "page_obj": page_obj,
        "contacts": page_obj.object_list,
        "groups": SMSContactGroup.objects.annotate(contact_count=Count("contacts")),
        "source_choices": SMSContact.Source.choices,
        "query": query,
        "source_filter": source,
        "status_filter": status_filter,
        "group_filter": group_id,
        **_base_context(request, "contacts"),
    }
    return render(request, "sms/contact_list.html", context)


@sms_required
def sms_contact_create(request):
    contact = SMSContact(created_by=request.user)
    form = SMSContactForm(request.POST or None, instance=contact)

    if request.method == "POST" and form.is_valid():
        contact = form.save(commit=False)
        contact.created_by = request.user
        contact.save()
        form.save_m2m()
        messages.success(request, f'Contact "{contact}" was created.')
        return redirect("sms-contact-detail", pk=contact.pk)

    return render(
        request,
        "sms/contact_form.html",
        {
            "page_title": "New SMS Contact",
            "form": form,
            "contact": None,
            **_base_context(request, "contacts"),
        },
    )


@sms_required
def sms_contact_edit(request, pk):
    contact = get_object_or_404(SMSContact, pk=pk)
    form = SMSContactForm(request.POST or None, instance=contact)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f'Contact "{contact}" was updated.')
        return redirect("sms-contact-detail", pk=contact.pk)

    return render(
        request,
        "sms/contact_form.html",
        {
            "page_title": "Edit SMS Contact",
            "form": form,
            "contact": contact,
            **_base_context(request, "contacts"),
        },
    )


@sms_required
def sms_contact_detail(request, pk):
    contact = get_object_or_404(
        SMSContact.objects.select_related("customer").prefetch_related("groups"),
        pk=pk,
    )
    page_obj = _paginate(
        request,
        contact.messages.select_related("sender_id", "campaign"),
        per_page=20,
    )
    return render(
        request,
        "sms/contact_detail.html",
        {
            "page_title": str(contact),
            "contact": contact,
            "page_obj": page_obj,
            "contact_messages": page_obj.object_list,
            **_base_context(request, "contacts"),
        },
    )


@sms_required
@require_POST
def sms_contact_toggle(request, pk):
    contact = get_object_or_404(SMSContact, pk=pk)
    contact.is_active = not contact.is_active
    contact.save(update_fields=["is_active", "updated_at"])
    messages.success(
        request,
        f'Contact "{contact}" was {"activated" if contact.is_active else "deactivated"}.',
    )
    return redirect(request.POST.get("next") or "sms-contact-list")


@sms_manage_required
@require_POST
def sms_contact_delete(request, pk):
    contact = get_object_or_404(SMSContact, pk=pk)
    label = str(contact)
    contact.delete()
    messages.success(request, f'Contact "{label}" was deleted.')
    return redirect("sms-contact-list")


@sms_required
def sms_contact_export(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="sms_contacts.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Name",
            "Phone",
            "Email",
            "Source",
            "Active",
            "Transaction SMS",
            "Promotional SMS",
            "Opted Out",
            "Groups",
        ]
    )

    for contact in SMSContact.objects.prefetch_related("groups"):
        writer.writerow(
            [
                contact.name,
                contact.phone,
                contact.email,
                contact.get_source_display(),
                "Yes" if contact.is_active else "No",
                "Yes" if contact.allow_transaction_sms else "No",
                "Yes" if contact.allow_promotional_sms else "No",
                "Yes" if contact.opted_out else "No",
                ", ".join(contact.groups.values_list("name", flat=True)),
            ]
        )

    return response


@sms_required
def sms_contact_import(request):
    form = SMSImportForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        batch = import_contacts(
            uploaded_file=form.cleaned_data.get("csv_file"),
            pasted_text=form.cleaned_data.get("pasted_contacts", ""),
            group=form.cleaned_data.get("group"),
            created_by=request.user,
        )
        messages.success(
            request,
            f"Import completed: {batch.created_count} created, "
            f"{batch.updated_count} updated and {batch.skipped_count} skipped.",
        )
        return redirect("sms-contact-import")

    return render(
        request,
        "sms/contact_import.html",
        {
            "page_title": "Import SMS Contacts",
            "form": form,
            "recent_imports": SMSImportBatch.objects.select_related("created_by")[:10],
            **_base_context(request, "contacts"),
        },
    )


@sms_required
@require_POST
def sms_sync_customers(request):
    result = sync_all_customer_contacts(created_by=request.user)
    messages.success(
        request,
        f'Customer and sale sync finished: {result["synced"]} synchronized and '
        f'{result["skipped"]} skipped.',
    )
    return redirect("sms-contact-list")


@sms_required
def sms_group_list(request):
    groups = SMSContactGroup.objects.annotate(contact_count=Count("contacts"))
    return render(
        request,
        "sms/group_list.html",
        {
            "page_title": "SMS Contact Groups",
            "groups": groups,
            **_base_context(request, "groups"),
        },
    )


@sms_manage_required
def sms_group_create(request):
    form = SMSContactGroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        group = form.save(commit=False)
        group.created_by = request.user
        group.save()
        messages.success(request, f'Group "{group.name}" was created.')
        return redirect("sms-group-list")

    return render(
        request,
        "sms/generic_form.html",
        {
            "page_title": "New SMS Group",
            "form": form,
            "cancel_url": "sms-group-list",
            "submit_label": "Create group",
            **_base_context(request, "groups"),
        },
    )


@sms_manage_required
def sms_group_edit(request, pk):
    group = get_object_or_404(SMSContactGroup, pk=pk)
    form = SMSContactGroupForm(request.POST or None, instance=group)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f'Group "{group.name}" was updated.')
        return redirect("sms-group-list")

    return render(
        request,
        "sms/generic_form.html",
        {
            "page_title": "Edit SMS Group",
            "form": form,
            "cancel_url": "sms-group-list",
            "submit_label": "Save changes",
            **_base_context(request, "groups"),
        },
    )


@sms_manage_required
@require_POST
def sms_group_delete(request, pk):
    group = get_object_or_404(SMSContactGroup, pk=pk)
    label = group.name
    group.delete()
    messages.success(request, f'Group "{label}" was deleted.')
    return redirect("sms-group-list")


@sms_required
def sms_template_list(request):
    templates = SMSTemplate.objects.all()
    category = str(request.GET.get("category") or "").strip()
    language = str(request.GET.get("language") or "").strip()
    query = str(request.GET.get("q") or "").strip()

    if category in SMSTemplate.Category.values:
        templates = templates.filter(category=category)
    if language in SMSTemplate.Language.values:
        templates = templates.filter(language=language)
    if query:
        templates = templates.filter(
            Q(title__icontains=query) | Q(message__icontains=query)
        )

    return render(
        request,
        "sms/template_list.html",
        {
            "page_title": "SMS Templates",
            "templates": templates,
            "category_choices": SMSTemplate.Category.choices,
            "language_choices": SMSTemplate.Language.choices,
            "category_filter": category,
            "language_filter": language,
            "query": query,
            **_base_context(request, "templates"),
        },
    )


@sms_manage_required
def sms_template_create(request):
    template = SMSTemplate(created_by=request.user)
    form = SMSTemplateForm(request.POST or None, instance=template)
    if request.method == "POST" and form.is_valid():
        template = form.save(commit=False)
        template.created_by = request.user
        template.save()
        messages.success(request, f'Template "{template.title}" was created.')
        return redirect("sms-template-list")

    return render(
        request,
        "sms/template_form.html",
        {
            "page_title": "New SMS Template",
            "form": form,
            "template": None,
            **_base_context(request, "templates"),
        },
    )


@sms_manage_required
def sms_template_edit(request, pk):
    template = get_object_or_404(SMSTemplate, pk=pk)
    form = SMSTemplateForm(request.POST or None, instance=template)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f'Template "{template.title}" was updated.')
        return redirect("sms-template-list")

    return render(
        request,
        "sms/template_form.html",
        {
            "page_title": "Edit SMS Template",
            "form": form,
            "template": template,
            **_base_context(request, "templates"),
        },
    )


@sms_manage_required
@require_POST
def sms_template_delete(request, pk):
    template = get_object_or_404(SMSTemplate, pk=pk)
    label = template.title
    template.delete()
    messages.success(request, f'Template "{label}" was deleted.')
    return redirect("sms-template-list")


@sms_manage_required
def sms_sender_list(request):
    return render(
        request,
        "sms/sender_list.html",
        {
            "page_title": "SMS Sender IDs",
            "senders": SenderID.objects.annotate(message_count=Count("messages")),
            **_base_context(request, "senders"),
        },
    )


@sms_manage_required
def sms_sender_create(request):
    sender = SenderID(created_by=request.user)
    form = SenderIDForm(request.POST or None, instance=sender, can_approve=True)
    if request.method == "POST" and form.is_valid():
        sender = form.save(commit=False)
        sender.created_by = request.user
        sender.save()
        messages.success(request, f'Sender ID "{sender.name}" was saved.')
        return redirect("sms-sender-list")

    return render(
        request,
        "sms/sender_form.html",
        {
            "page_title": "New Sender ID",
            "form": form,
            "sender": None,
            **_base_context(request, "senders"),
        },
    )


@sms_manage_required
def sms_sender_edit(request, pk):
    sender = get_object_or_404(SenderID, pk=pk)
    form = SenderIDForm(
        request.POST or None,
        instance=sender,
        can_approve=True,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f'Sender ID "{sender.name}" was updated.')
        return redirect("sms-sender-list")

    return render(
        request,
        "sms/sender_form.html",
        {
            "page_title": "Edit Sender ID",
            "form": form,
            "sender": sender,
            **_base_context(request, "senders"),
        },
    )


@sms_manage_required
@require_POST
def sms_sender_delete(request, pk):
    sender = get_object_or_404(SenderID, pk=pk)
    label = sender.name
    sender.delete()
    messages.success(request, f'Sender ID "{label}" was deleted.')
    return redirect("sms-sender-list")


@sms_required
def sms_campaign_list(request):
    campaigns = SMSCampaign.objects.select_related("sender_id", "template", "created_by")
    status_filter = str(request.GET.get("status") or "").strip()
    message_type = str(request.GET.get("message_type") or "").strip()
    query = str(request.GET.get("q") or "").strip()

    if status_filter in SMSCampaign.Status.values:
        campaigns = campaigns.filter(status=status_filter)
    if message_type in SMSCampaign.MessageType.values:
        campaigns = campaigns.filter(message_type=message_type)
    if query:
        campaigns = campaigns.filter(
            Q(title__icontains=query) | Q(message__icontains=query)
        )

    page_obj = _paginate(request, campaigns, per_page=25)
    return render(
        request,
        "sms/campaign_list.html",
        {
            "page_title": "SMS Campaigns",
            "campaigns": page_obj.object_list,
            "page_obj": page_obj,
            "status_choices": SMSCampaign.Status.choices,
            "message_type_choices": SMSCampaign.MessageType.choices,
            "status_filter": status_filter,
            "message_type_filter": message_type,
            "query": query,
            **_base_context(request, "campaigns"),
        },
    )


@sms_required
def sms_campaign_detail(request, pk):
    campaign = get_object_or_404(
        SMSCampaign.objects.select_related("sender_id", "template", "created_by").prefetch_related(
            "groups", "contacts"
        ),
        pk=pk,
    )
    page_obj = _paginate(
        request,
        campaign.messages.select_related("contact", "sender_id"),
        per_page=30,
    )
    return render(
        request,
        "sms/campaign_detail.html",
        {
            "page_title": campaign.title,
            "campaign": campaign,
            "campaign_messages": page_obj.object_list,
            "page_obj": page_obj,
            **_base_context(request, "campaigns"),
        },
    )


@sms_required
@require_POST
def sms_campaign_sync(request, pk):
    campaign = get_object_or_404(SMSCampaign, pk=pk)
    result = sync_campaign_delivery(campaign)
    messages.success(
        request,
        f'Delivery refresh checked {result["checked"]} messages and updated '
        f'{result["updated"]}.',
    )
    return redirect("sms-campaign-detail", pk=campaign.pk)


@sms_required
def sms_message_list(request):
    messages_qs = SMSMessage.objects.select_related(
        "contact", "customer", "sender_id", "campaign", "created_by"
    )
    status_filter = str(request.GET.get("status") or "").strip()
    message_type = str(request.GET.get("message_type") or "").strip()
    query = str(request.GET.get("q") or "").strip()
    date_from = str(request.GET.get("date_from") or "").strip()
    date_to = str(request.GET.get("date_to") or "").strip()

    if status_filter in SMSMessage.Status.values:
        messages_qs = messages_qs.filter(status=status_filter)
    if message_type in SMSCampaign.MessageType.values:
        messages_qs = messages_qs.filter(message_type=message_type)
    if query:
        messages_qs = messages_qs.filter(
            Q(dest_addr__icontains=query)
            | Q(message__icontains=query)
            | Q(contact__name__icontains=query)
            | Q(request_id__icontains=query)
        )
    if date_from:
        messages_qs = messages_qs.filter(created_at__date__gte=date_from)
    if date_to:
        messages_qs = messages_qs.filter(created_at__date__lte=date_to)

    page_obj = _paginate(request, messages_qs, per_page=30)
    return render(
        request,
        "sms/message_list.html",
        {
            "page_title": "SMS Message Log",
            "message_rows": page_obj.object_list,
            "page_obj": page_obj,
            "status_choices": SMSMessage.Status.choices,
            "message_type_choices": SMSCampaign.MessageType.choices,
            "status_filter": status_filter,
            "message_type_filter": message_type,
            "query": query,
            "date_from": date_from,
            "date_to": date_to,
            **_base_context(request, "messages"),
        },
    )


@sms_required
def sms_message_detail(request, pk):
    message_obj = get_object_or_404(
        SMSMessage.objects.select_related(
            "contact", "customer", "sender_id", "campaign", "sale", "created_by"
        ),
        pk=pk,
    )
    return render(
        request,
        "sms/message_detail.html",
        {
            "page_title": f"SMS to {message_obj.dest_addr}",
            "message_obj": message_obj,
            **_base_context(request, "messages"),
        },
    )


@sms_required
@require_POST
def sms_message_sync(request, pk):
    message_obj = get_object_or_404(SMSMessage, pk=pk)
    result = sync_message_delivery(message_obj)
    if result.get("ok"):
        messages.success(request, f"Delivery status is now {message_obj.get_status_display()}.")
    else:
        messages.error(request, result.get("error", "Could not refresh delivery status."))
    return redirect("sms-message-detail", pk=message_obj.pk)


@sms_manage_required
def sms_settings(request):
    setting = SMSSetting.load()
    form = SMSSettingForm(request.POST or None, instance=setting)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "SMS settings were updated successfully.")
        return redirect("sms-settings")

    return render(
        request,
        "sms/settings.html",
        {
            "page_title": "SMS Settings",
            "form": form,
            "setting": setting,
            "credentials_ready": credentials_configured(),
            **_base_context(request, "settings"),
        },
    )
