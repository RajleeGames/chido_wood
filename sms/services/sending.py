from __future__ import annotations

from typing import Any, Iterable

from django.db import transaction
from django.utils import timezone

from sms.models import SMSCampaign, SMSContact, SMSMessage, SMSSetting, SenderID
from sms.services.beem import send_sms_batch
from sms.services.personalization import calculate_sms_parts, render_personalized_message
from sms.services.phones import is_valid_tz_phone, normalize_phone


def _extract_provider_item(response_json: dict[str, Any], phone: str):
    if not isinstance(response_json, dict):
        return {}

    data = response_json.get("data")
    if isinstance(data, dict):
        return data

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            if normalize_phone(str(item.get("dest_addr", ""))) == phone:
                return item
        if data and isinstance(data[0], dict):
            return data[0]

    return response_json


def _sale_reference(sale):
    if not sale:
        return ""

    for field_name in ("sale_number", "invoice_number", "reference_number"):
        value = str(getattr(sale, field_name, "") or "").strip()
        if value:
            return value

    return f"Sale #{sale.pk}"


def _contact_context(contact, setting, *, sale=None, extra=None):
    customer = getattr(contact, "customer", None) if contact else None
    extra = extra or {}

    amount = extra.get("amount", "")
    if not amount and sale is not None:
        amount = getattr(sale, "total_amount", "")

    balance = extra.get("balance", "")
    if not balance and customer is not None:
        balance = getattr(customer, "current_balance", "")

    date_value = extra.get("date", "")
    if not date_value and sale is not None:
        sale_date = getattr(sale, "sale_date", None)
        if sale_date:
            try:
                date_value = timezone.localtime(sale_date).strftime("%d/%m/%Y")
            except (ValueError, TypeError):
                date_value = str(sale_date)

    return {
        "name": getattr(contact, "name", "") if contact else "Customer",
        "phone": getattr(contact, "phone", "") if contact else "",
        "company": setting.business_name,
        "amount": str(amount or ""),
        "balance": str(balance or ""),
        "receipt": str(extra.get("receipt") or _sale_reference(sale)),
        "date": str(date_value or ""),
    }


def _recipient_list(contacts, manual_numbers, message_type):
    seen = set()
    recipients = []

    for contact in contacts or []:
        phone = normalize_phone(contact.phone)
        if phone in seen or not is_valid_tz_phone(phone):
            continue

        if not contact.is_active or contact.opted_out:
            continue

        if message_type == SMSCampaign.MessageType.PROMOTIONAL:
            if not contact.allow_promotional_sms:
                continue
        elif not contact.allow_transaction_sms:
            continue

        seen.add(phone)
        recipients.append((phone, contact))

    for raw_phone in manual_numbers or []:
        phone = normalize_phone(raw_phone)
        if phone in seen or not is_valid_tz_phone(phone):
            continue
        seen.add(phone)
        recipients.append((phone, None))

    return recipients


@transaction.atomic
def send_personalized_messages(
    *,
    sender: SenderID,
    message_template: str,
    contacts: Iterable[SMSContact] | None = None,
    manual_numbers: Iterable[str] | None = None,
    message_type: str = SMSCampaign.MessageType.TRANSACTION,
    campaign: SMSCampaign | None = None,
    created_by=None,
    language: str = "sw",
    sale=None,
    context_by_phone: dict[str, dict[str, Any]] | None = None,
    is_automatic: bool = False,
):
    setting = SMSSetting.load()

    if not sender or not sender.can_send:
        return {"ok": False, "error": "Select an approved and active Sender ID."}

    template = str(message_template or "").strip()
    if not template:
        return {"ok": False, "error": "Message cannot be empty."}

    if message_type == SMSCampaign.MessageType.PROMOTIONAL:
        if not setting.promotional_sms_enabled:
            return {"ok": False, "error": "Promotional SMS is disabled in settings."}
    elif not setting.transaction_sms_enabled:
        return {"ok": False, "error": "Transaction SMS is disabled in settings."}

    recipients = _recipient_list(contacts, manual_numbers, message_type)
    if not recipients:
        return {"ok": False, "error": "No valid permitted recipients were found."}

    if len(recipients) > setting.send_limit:
        return {
            "ok": False,
            "error": f"A maximum of {setting.send_limit} recipients can be sent at once.",
        }

    if campaign:
        campaign.status = SMSCampaign.Status.SENDING
        campaign.started_at = timezone.now()
        campaign.total_recipients = len(recipients)
        campaign.save(
            update_fields=["status", "started_at", "total_recipients", "updated_at"]
        )

    sent_count = 0
    failed_count = 0
    message_ids = []

    for phone, contact in recipients:
        extra = (context_by_phone or {}).get(phone, {})
        context = _contact_context(contact, setting, sale=sale, extra=extra)
        context["phone"] = phone

        rendered_message = render_personalized_message(
            template,
            context,
            language=language,
            force_name_greeting=contact is not None,
        )
        analysis = calculate_sms_parts(rendered_message)

        message_obj = SMSMessage.objects.create(
            campaign=campaign,
            contact=contact,
            customer=getattr(contact, "customer", None) if contact else None,
            sale=sale,
            sender_id=sender,
            dest_addr=phone,
            message=rendered_message,
            message_type=message_type,
            status=SMSMessage.Status.PENDING,
            sms_parts=analysis["parts"],
            is_automatic=is_automatic,
            created_by=created_by,
        )
        message_ids.append(message_obj.id)

        response = send_sms_batch(
            recipients=[
                {
                    "recipient_id": str(message_obj.id),
                    "dest_addr": phone,
                }
            ],
            message=rendered_message,
            source_addr=sender.name,
        )

        status_code = int(response.get("status_code") or 0)
        response_json = response.get("json") or {}
        provider_item = _extract_provider_item(response_json, phone)
        api_ok = 200 <= status_code < 300

        if api_ok:
            provider_status = str(provider_item.get("status") or "sent").lower()
            if "fail" in provider_status or "reject" in provider_status:
                message_obj.status = SMSMessage.Status.FAILED
                failed_count += 1
            else:
                message_obj.status = SMSMessage.Status.SENT
                sent_count += 1

            message_obj.sent_at = timezone.now()
            message_obj.request_id = str(provider_item.get("request_id") or "")
            message_obj.recipient_id = str(
                provider_item.get("recipient_id") or message_obj.id
            )
        else:
            message_obj.status = SMSMessage.Status.FAILED
            message_obj.error_text = str(
                response_json.get("error")
                if isinstance(response_json, dict)
                else response_json
            )
            failed_count += 1

        message_obj.provider_response = response_json
        message_obj.save(
            update_fields=[
                "status",
                "sent_at",
                "request_id",
                "recipient_id",
                "provider_response",
                "error_text",
                "updated_at",
            ]
        )

    if campaign:
        campaign.sent_count = sent_count
        campaign.failed_count = failed_count
        campaign.completed_at = timezone.now()

        if sent_count and not failed_count:
            campaign.status = SMSCampaign.Status.SENT
        elif sent_count:
            campaign.status = SMSCampaign.Status.PARTIAL
        else:
            campaign.status = SMSCampaign.Status.FAILED

        campaign.save(
            update_fields=[
                "sent_count",
                "failed_count",
                "completed_at",
                "status",
                "updated_at",
            ]
        )

    return {
        "ok": sent_count > 0,
        "total": len(recipients),
        "sent": sent_count,
        "failed": failed_count,
        "message_ids": message_ids,
    }
