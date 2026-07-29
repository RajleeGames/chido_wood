from __future__ import annotations

from django.utils import timezone

from sms.models import SMSCampaign, SMSMessage
from sms.services.beem import get_delivery_report


def _extract_delivery_status(payload):
    if not isinstance(payload, dict):
        return ""

    for key in ("delivery_status", "status"):
        if payload.get(key):
            return str(payload[key])

    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("delivery_status", "status"):
            if data.get(key):
                return str(data[key])

    if isinstance(data, list) and data and isinstance(data[0], dict):
        for key in ("delivery_status", "status"):
            if data[0].get(key):
                return str(data[0][key])

    return ""


def sync_message_delivery(message: SMSMessage):
    if not message.request_id or not message.dest_addr:
        return {"ok": False, "error": "Message has no request ID or destination."}

    response = get_delivery_report(
        dest_addr=message.dest_addr,
        request_id=message.request_id,
    )
    status_code = int(response.get("status_code") or 0)
    payload = response.get("json") or {}
    message.provider_response = payload

    if 200 <= status_code < 300:
        raw_status = _extract_delivery_status(payload).upper()

        if "UNDELIVER" in raw_status:
            message.status = SMSMessage.Status.UNDELIVERED
        elif "DELIVER" in raw_status:
            message.status = SMSMessage.Status.DELIVERED
            message.delivered_at = timezone.now()
        elif "REJECT" in raw_status:
            message.status = SMSMessage.Status.REJECTED
        elif "EXPIRE" in raw_status:
            message.status = SMSMessage.Status.EXPIRED
        elif "FAIL" in raw_status:
            message.status = SMSMessage.Status.FAILED

        message.save(
            update_fields=[
                "status",
                "delivered_at",
                "provider_response",
                "updated_at",
            ]
        )
        return {"ok": True, "status": message.status, "response": payload}

    message.save(update_fields=["provider_response", "updated_at"])
    return {"ok": False, "status": message.status, "response": payload}


def refresh_campaign_counts(campaign: SMSCampaign):
    campaign.total_recipients = campaign.messages.count()
    campaign.sent_count = campaign.messages.filter(
        status__in=[SMSMessage.Status.SENT, SMSMessage.Status.DELIVERED]
    ).count()
    campaign.delivered_count = campaign.messages.filter(
        status=SMSMessage.Status.DELIVERED
    ).count()
    campaign.failed_count = campaign.messages.filter(
        status__in=[
            SMSMessage.Status.FAILED,
            SMSMessage.Status.UNDELIVERED,
            SMSMessage.Status.REJECTED,
            SMSMessage.Status.EXPIRED,
        ]
    ).count()
    campaign.save(
        update_fields=[
            "total_recipients",
            "sent_count",
            "delivered_count",
            "failed_count",
            "updated_at",
        ]
    )


def sync_campaign_delivery(campaign: SMSCampaign):
    checked = 0
    updated = 0

    for message in campaign.messages.exclude(request_id="").exclude(
        request_id__isnull=True
    ):
        checked += 1
        if sync_message_delivery(message).get("ok"):
            updated += 1

    refresh_campaign_counts(campaign)
    return {"ok": True, "checked": checked, "updated": updated}
