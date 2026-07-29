from __future__ import annotations

import math
import re
from typing import Any, Mapping


PLACEHOLDER_ALIASES = {
    "name": ["{name}", "{{name}}", "{{ name }}", "[name]"],
    "first_name": [
        "{first_name}",
        "{{first_name}}",
        "{{ first_name }}",
        "[first_name]",
    ],
    "phone": ["{phone}", "{{phone}}", "{{ phone }}", "[phone]"],
    "company": ["{company}", "{{company}}", "{{ company }}", "[company]"],
    "amount": ["{amount}", "{{amount}}", "{{ amount }}", "[amount]"],
    "balance": ["{balance}", "{{balance}}", "{{ balance }}", "[balance]"],
    "receipt": ["{receipt}", "{{receipt}}", "{{ receipt }}", "[receipt]"],
    "date": ["{date}", "{{date}}", "{{ date }}", "[date]"],
}

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

GENERIC_GREETING_PATTERN = re.compile(
    r"^(hello|hi|hey|dear(?:\s+customer)?|habari|hujambo|mambo|salamu?|ndugu|ndg|mteja(?:\s+wetu)?|bwana|bi)\s*[,!:-]?\s*",
    flags=re.IGNORECASE,
)

GSM_7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM_7_EXTENDED = set("^{}\\[~]|€")


def _clean_name(name: str, phone: str = "") -> str:
    value = str(name or "").strip()
    if value.lower() in WEAK_NAMES:
        return "Customer"

    name_digits = re.sub(r"\D", "", value)
    phone_digits = re.sub(r"\D", "", str(phone or ""))
    if name_digits and name_digits == phone_digits:
        return "Customer"

    return value or "Customer"


def _first_name(name: str) -> str:
    parts = str(name or "").strip().split()
    return parts[0] if parts else "Customer"


def contains_placeholder(message: str) -> bool:
    lowered = str(message or "").lower()
    return any(
        alias.lower() in lowered
        for aliases in PLACEHOLDER_ALIASES.values()
        for alias in aliases
    )


def render_personalized_message(
    template: str,
    context: Mapping[str, Any] | None = None,
    *,
    language: str = "sw",
    force_name_greeting: bool = True,
) -> str:
    context = dict(context or {})
    message = str(template or "").strip()

    phone = str(context.get("phone") or "").strip()
    name = _clean_name(str(context.get("name") or ""), phone)
    is_english = str(language or "").lower().startswith("en")

    if name == "Customer" and not is_english:
        name = "Mteja"

    first_name = str(context.get("first_name") or "").strip() or _first_name(name)

    values = {
        "name": name,
        "first_name": first_name,
        "phone": phone,
        "company": str(context.get("company") or "").strip(),
        "amount": str(context.get("amount") or "").strip(),
        "balance": str(context.get("balance") or "").strip(),
        "receipt": str(context.get("receipt") or "").strip(),
        "date": str(context.get("date") or "").strip(),
    }

    had_placeholder = contains_placeholder(message)

    for key, aliases in PLACEHOLDER_ALIASES.items():
        replacement = values.get(key, "")
        for alias in sorted(aliases, key=len, reverse=True):
            message = re.sub(re.escape(alias), replacement, message, flags=re.IGNORECASE)

    message = message.strip()

    if had_placeholder or not force_name_greeting:
        return message

    body = GENERIC_GREETING_PATTERN.sub("", message).strip()
    if not body:
        body = (
            "Thank you for doing business with us."
            if is_english
            else "Asante kwa kufanya biashara nasi. Karibu tena."
        )

    greeting = "Dear" if is_english else "Ndugu"
    return f"{greeting} {first_name}, {body}".strip()


def _gsm_septet_length(message: str):
    total = 0
    for character in str(message or ""):
        if character in GSM_7_BASIC:
            total += 1
        elif character in GSM_7_EXTENDED:
            total += 2
        else:
            return None
    return total


def calculate_sms_parts(message: str):
    text = str(message or "")
    septets = _gsm_septet_length(text)

    if septets is not None:
        parts = 1 if septets <= 160 else math.ceil(septets / 153)
        return {
            "encoding": "gsm7",
            "characters": len(text),
            "billable_characters": septets,
            "parts": max(1, parts),
        }

    characters = len(text)
    parts = 1 if characters <= 70 else math.ceil(characters / 67)
    return {
        "encoding": "unicode",
        "characters": characters,
        "billable_characters": characters,
        "parts": max(1, parts),
    }
