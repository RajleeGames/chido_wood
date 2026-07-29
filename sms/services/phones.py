from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


PHONE_PATTERN = re.compile(r"^255[67]\d{8}$")


def _expand_scientific_notation(value: str) -> str:
    raw = str(value or "").strip()
    if not raw or "e" not in raw.lower():
        return raw

    try:
        number = Decimal(raw)
        return format(number.quantize(Decimal("1")), "f")
    except (InvalidOperation, ValueError):
        return raw


def normalize_phone(value: str) -> str:
    """Normalize Tanzanian mobile numbers to 2556XXXXXXXX or 2557XXXXXXXX."""
    raw = _expand_scientific_notation(value)
    raw = raw.strip().replace(" ", "").replace("-", "")
    raw = raw.replace("(", "").replace(")", "")

    if "," in raw:
        raw = raw.split(",", 1)[0]

    if raw.startswith("+"):
        raw = raw[1:]

    digits = re.sub(r"\D", "", raw)

    if digits.startswith("0") and len(digits) == 10:
        digits = "255" + digits[1:]
    elif digits.startswith(("6", "7")) and len(digits) == 9:
        digits = "255" + digits

    if digits.startswith("255") and len(digits) > 12:
        digits = digits[:12]

    return digits


def is_valid_tz_phone(value: str) -> bool:
    return bool(PHONE_PATTERN.fullmatch(normalize_phone(value)))


def split_phone_values(value: str):
    for item in re.split(r"[\n,;]+", str(value or "")):
        cleaned = item.strip()
        if cleaned:
            yield cleaned
