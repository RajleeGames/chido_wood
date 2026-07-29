from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


def _credentials():
    return (
        str(getattr(settings, "BEEM_API_KEY", "") or "").strip(),
        str(getattr(settings, "BEEM_SECRET_KEY", "") or "").strip(),
    )


def credentials_configured():
    api_key, secret_key = _credentials()
    return bool(api_key and secret_key)


def _auth():
    api_key, secret_key = _credentials()
    if not api_key or not secret_key:
        return None
    return HTTPBasicAuth(api_key, secret_key)


def _safe_json(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
        return data if isinstance(data, dict) else {"data": data}
    except ValueError:
        return {
            "http_status": response.status_code,
            "text": response.text,
        }


def send_sms_batch(*, recipients, message, source_addr=None):
    auth = _auth()
    if auth is None:
        return {
            "status_code": 0,
            "json": {
                "successful": False,
                "error": "Beem API credentials are not configured.",
            },
        }

    url = getattr(
        settings,
        "BEEM_API_URL_SEND",
        "https://apisms.beem.africa/v1/send",
    )
    sender = source_addr or getattr(settings, "BEEM_SENDER_ID", "")

    payload = {
        "source_addr": sender,
        "encoding": 0,
        "message": str(message or ""),
        "recipients": recipients,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            auth=auth,
            timeout=getattr(settings, "BEEM_REQUEST_TIMEOUT", 30),
        )
        return {
            "status_code": response.status_code,
            "json": _safe_json(response),
        }
    except requests.RequestException as exc:
        logger.exception("Beem SMS request failed")
        return {
            "status_code": 0,
            "json": {"successful": False, "error": str(exc)},
        }


def check_balance():
    auth = _auth()
    if auth is None:
        return {
            "status_code": 0,
            "json": {
                "successful": False,
                "error": "Beem API credentials are not configured.",
            },
        }

    url = getattr(
        settings,
        "BEEM_BALANCE_URL",
        "https://apisms.beem.africa/public/v1/vendors/balance",
    )

    try:
        response = requests.get(
            url,
            auth=auth,
            timeout=getattr(settings, "BEEM_REQUEST_TIMEOUT", 20),
        )
        return {
            "status_code": response.status_code,
            "json": _safe_json(response),
        }
    except requests.RequestException as exc:
        logger.exception("Beem balance request failed")
        return {
            "status_code": 0,
            "json": {"successful": False, "error": str(exc)},
        }


def get_delivery_report(*, dest_addr, request_id):
    auth = _auth()
    if auth is None:
        return {
            "status_code": 0,
            "json": {
                "successful": False,
                "error": "Beem API credentials are not configured.",
            },
        }

    url = getattr(
        settings,
        "BEEM_DLR_URL",
        "https://dlrapi.beem.africa/public/v1/delivery-reports",
    )

    try:
        response = requests.get(
            url,
            params={"dest_addr": dest_addr, "request_id": request_id},
            auth=auth,
            timeout=getattr(settings, "BEEM_REQUEST_TIMEOUT", 20),
        )
        return {
            "status_code": response.status_code,
            "json": _safe_json(response),
        }
    except requests.RequestException as exc:
        logger.exception("Beem delivery report request failed")
        return {
            "status_code": 0,
            "json": {"successful": False, "error": str(exc)},
        }
