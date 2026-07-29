from __future__ import annotations

import csv
import io

from django.db import transaction

from sms.models import SMSContact, SMSContactGroup, SMSImportBatch
from sms.services.phones import is_valid_tz_phone, normalize_phone


def _first_value(row, names):
    normalized = {str(key or "").strip().lower(): value for key, value in row.items()}
    for name in names:
        value = normalized.get(name)
        if str(value or "").strip():
            return str(value).strip()
    return ""


def _rows_from_csv(uploaded_file):
    content = uploaded_file.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(content)))


def _rows_from_paste(pasted_text):
    rows = []
    for line in str(pasted_text or "").splitlines():
        value = line.strip()
        if not value:
            continue

        parts = [item.strip() for item in value.split(",")]
        if len(parts) == 1:
            rows.append({"phone": parts[0], "name": ""})
        else:
            rows.append({"name": parts[0], "phone": parts[1]})
    return rows


@transaction.atomic
def import_contacts(*, uploaded_file=None, pasted_text="", group=None, created_by=None):
    rows = _rows_from_csv(uploaded_file) if uploaded_file else _rows_from_paste(pasted_text)
    source_name = getattr(uploaded_file, "name", "") or "Pasted contacts"

    batch = SMSImportBatch.objects.create(
        source_name=source_name,
        total_rows=len(rows),
        created_by=created_by,
    )

    created_count = 0
    updated_count = 0
    skipped_count = 0
    errors = []

    for index, row in enumerate(rows, start=2 if uploaded_file else 1):
        name = _first_value(row, ["name", "customer", "customer name", "full_name"])
        phone = normalize_phone(
            _first_value(row, ["phone", "mobile", "phone number", "telephone"])
        )
        email = _first_value(row, ["email", "email address"])

        if not is_valid_tz_phone(phone):
            skipped_count += 1
            errors.append({"row": index, "phone": phone, "error": "Invalid phone number"})
            continue

        contact, created = SMSContact.objects.get_or_create(
            phone=phone,
            defaults={
                "name": name or "Customer",
                "email": email,
                "source": SMSContact.Source.IMPORT,
                "created_by": created_by,
            },
        )

        if created:
            created_count += 1
        else:
            changed = False
            if name and not contact.name:
                contact.name = name
                changed = True
            if email and not contact.email:
                contact.email = email
                changed = True
            if not contact.is_active:
                contact.is_active = True
                changed = True
            if changed:
                contact.save()
                updated_count += 1
            else:
                skipped_count += 1

        if group:
            contact.groups.add(group)

    batch.created_count = created_count
    batch.updated_count = updated_count
    batch.skipped_count = skipped_count
    batch.error_rows = errors[:100]
    batch.save(
        update_fields=[
            "created_count",
            "updated_count",
            "skipped_count",
            "error_rows",
        ]
    )

    return batch
