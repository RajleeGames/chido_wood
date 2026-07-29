from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from sales.models import Sale

from .models import SMSCampaign, SMSMessage, SMSSetting
from .services.contacts import sync_contact_from_sale
from .services.sending import send_personalized_messages

logger = logging.getLogger(__name__)


def _completed_status():
    return str(getattr(getattr(Sale, "Status", None), "COMPLETED", "completed"))


def _sale_actor(sale):
    return (
        getattr(sale, "completed_by", None)
        or getattr(sale, "created_by", None)
        or getattr(sale, "user", None)
    )


def _sync_contact_after_commit(sale_id, actor_id=None):
    try:
        sale = Sale.objects.select_related("customer").get(pk=sale_id)
        actor = _sale_actor(sale)
        sync_contact_from_sale(sale, created_by=actor)
    except Exception:
        logger.exception("Could not synchronize SMS contact for sale %s", sale_id)


def _send_automatic_sale_sms_after_commit(sale_id):
    try:
        sale = Sale.objects.select_related("customer").get(pk=sale_id)
        setting = SMSSetting.load()

        if not setting.automatic_sale_sms_enabled:
            return
        if not setting.transaction_sms_enabled:
            return
        if not setting.default_sender_id or not setting.default_sender.can_send:
            return
        if not setting.automatic_sale_template_id:
            return
        if SMSMessage.objects.filter(sale=sale, is_automatic=True).exists():
            return

        actor = _sale_actor(sale)
        contact = sync_contact_from_sale(sale, created_by=actor)
        if not contact:
            return

        send_personalized_messages(
            sender=setting.default_sender,
            message_template=setting.automatic_sale_template.message,
            contacts=[contact],
            message_type=SMSCampaign.MessageType.TRANSACTION,
            created_by=actor,
            language=setting.automatic_sale_template.language,
            sale=sale,
            is_automatic=True,
        )
    except IntegrityError:
        # A concurrent save may already have created the automatic SMS.
        return
    except Exception:
        logger.exception("Could not send automatic SMS for sale %s", sale_id)


@receiver(post_save, sender=Sale)
def handle_completed_sale_sms(sender, instance, **kwargs):
    if str(getattr(instance, "status", "")) != _completed_status():
        return

    sale_id = instance.pk
    actor = _sale_actor(instance)
    actor_id = getattr(actor, "pk", None)

    transaction.on_commit(
        lambda: _sync_contact_after_commit(sale_id, actor_id=actor_id)
    )
    transaction.on_commit(lambda: _send_automatic_sale_sms_after_commit(sale_id))
