from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from sms.models import SMSContact, SMSContactGroup
from sms.services.phones import is_valid_tz_phone, normalize_phone


WEAK_NAMES = {
    "",
    "customer",
    "mteja",
    "walk-in",
    "walk in",
    "unknown",
    "n/a",
    "-",
    "—",
}


def _looks_like_phone_name(name, phone):
    name_digits = "".join(character for character in str(name or "") if character.isdigit())
    phone_digits = "".join(character for character in str(phone or "") if character.isdigit())
    return bool(name_digits and phone_digits and name_digits == phone_digits)


def _customer_name(customer):
    for field_name in ("name", "full_name"):
        value = str(getattr(customer, field_name, "") or "").strip()
        if value:
            return value

    first_name = str(getattr(customer, "first_name", "") or "").strip()
    last_name = str(getattr(customer, "last_name", "") or "").strip()
    return f"{first_name} {last_name}".strip()


def _customer_phone(customer):
    for field_name in ("phone", "phone_number", "mobile"):
        value = str(getattr(customer, field_name, "") or "").strip()
        if value:
            return value
    return ""


def _customer_email(customer):
    return str(getattr(customer, "email", "") or "").strip()


def _sale_identity(sale):
    customer = getattr(sale, "customer", None)
    sale_name = str(getattr(sale, "customer_name", "") or "").strip()
    sale_phone = str(getattr(sale, "customer_phone", "") or "").strip()

    name = sale_name
    phone = sale_phone

    if customer:
        customer_name = _customer_name(customer)
        customer_phone = _customer_phone(customer)
        phone = customer_phone or sale_phone

        customer_name_is_weak = (
            customer_name.lower() in WEAK_NAMES
            or _looks_like_phone_name(customer_name, phone)
        )
        name = sale_name if sale_name and customer_name_is_weak else (customer_name or sale_name)

    return customer, name, normalize_phone(phone)


def _ensure_sales_group(created_by=None):
    group, _ = SMSContactGroup.objects.get_or_create(
        name="Sales Customers",
        defaults={
            "description": "Customers collected automatically from completed sales.",
            "created_by": created_by,
        },
    )
    return group


def _ensure_customer_group(created_by=None):
    group, _ = SMSContactGroup.objects.get_or_create(
        name="Customer Records",
        defaults={
            "description": "Contacts synchronized from the Customers module.",
            "created_by": created_by,
        },
    )
    return group


@transaction.atomic
def sync_contact_from_customer(customer, *, created_by=None):
    if not customer:
        return None

    phone = normalize_phone(_customer_phone(customer))
    if not is_valid_tz_phone(phone):
        return None

    name = _customer_name(customer)
    email = _customer_email(customer)
    group = _ensure_customer_group(created_by=created_by)

    contact, created = SMSContact.objects.get_or_create(
        phone=phone,
        defaults={
            "customer": customer,
            "name": name or "Customer",
            "email": email,
            "source": SMSContact.Source.CUSTOMER,
            "is_active": True,
            "allow_transaction_sms": True,
            "allow_promotional_sms": False,
            "created_by": created_by,
        },
    )

    changed_fields = []
    if not created:
        current_name = str(contact.name or "").strip()
        if name and (
            current_name.lower() in WEAK_NAMES
            or _looks_like_phone_name(current_name, phone)
        ):
            contact.name = name
            changed_fields.append("name")

        if email and not contact.email:
            contact.email = email
            changed_fields.append("email")

        if not contact.customer_id:
            contact.customer = customer
            changed_fields.append("customer")

        if contact.source == SMSContact.Source.MANUAL:
            pass
        elif contact.source != SMSContact.Source.CUSTOMER:
            contact.source = SMSContact.Source.CUSTOMER
            changed_fields.append("source")

        if not contact.is_active:
            contact.is_active = True
            changed_fields.append("is_active")

        if changed_fields:
            changed_fields.append("updated_at")
            contact.save(update_fields=list(dict.fromkeys(changed_fields)))

    contact.groups.add(group)
    return contact


@transaction.atomic
def sync_contact_from_sale(sale, *, created_by=None):
    if not sale:
        return None

    status_value = str(getattr(sale, "status", "") or "")
    completed_value = str(getattr(getattr(sale, "Status", None), "COMPLETED", "completed"))
    if status_value != completed_value:
        return None

    customer, name, phone = _sale_identity(sale)
    if not is_valid_tz_phone(phone):
        return None

    group = _ensure_sales_group(created_by=created_by)
    sale_time = getattr(sale, "sale_date", None) or getattr(sale, "created_at", None) or timezone.now()

    contact, created = SMSContact.objects.get_or_create(
        phone=phone,
        defaults={
            "customer": customer,
            "name": name or "Customer",
            "email": _customer_email(customer) if customer else "",
            "source": SMSContact.Source.SALE,
            "is_active": True,
            "allow_transaction_sms": True,
            "allow_promotional_sms": False,
            "last_purchase_at": sale_time,
            "notes": "Automatically saved from a completed sale.",
            "created_by": created_by,
        },
    )

    changed_fields = []
    if not created:
        current_name = str(contact.name or "").strip()
        if name and (
            current_name.lower() in WEAK_NAMES
            or _looks_like_phone_name(current_name, phone)
        ):
            contact.name = name
            changed_fields.append("name")

        if customer and not contact.customer_id:
            contact.customer = customer
            changed_fields.append("customer")

        if contact.source not in {SMSContact.Source.MANUAL, SMSContact.Source.IMPORT}:
            contact.source = SMSContact.Source.SALE
            changed_fields.append("source")

        if not contact.is_active:
            contact.is_active = True
            changed_fields.append("is_active")

        if not contact.last_purchase_at or sale_time > contact.last_purchase_at:
            contact.last_purchase_at = sale_time
            changed_fields.append("last_purchase_at")

        if changed_fields:
            changed_fields.append("updated_at")
            contact.save(update_fields=list(dict.fromkeys(changed_fields)))

    contact.groups.add(group)
    return contact


def sync_all_customer_contacts(*, created_by=None):
    """Synchronize existing Customer records and completed Sale records."""
    from customers.models import Customer
    from sales.models import Sale

    result = {
        "processed": 0,
        "synced": 0,
        "skipped": 0,
        "customers_processed": 0,
        "sales_processed": 0,
    }

    for customer in Customer.objects.all().iterator():
        result["processed"] += 1
        result["customers_processed"] += 1
        if sync_contact_from_customer(customer, created_by=created_by):
            result["synced"] += 1
        else:
            result["skipped"] += 1

    completed_value = str(
        getattr(getattr(Sale, "Status", None), "COMPLETED", "completed")
    )
    completed_sales = Sale.objects.filter(status=completed_value).select_related("customer")

    for sale in completed_sales.iterator():
        result["processed"] += 1
        result["sales_processed"] += 1
        if sync_contact_from_sale(sale, created_by=created_by):
            result["synced"] += 1
        else:
            result["skipped"] += 1

    return result
