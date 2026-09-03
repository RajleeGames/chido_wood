import base64
import json
import logging
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST


logger = logging.getLogger(__name__)

QZ_KEY_DIR = Path(settings.BASE_DIR) / "qz_keys"
QZ_CERTIFICATE_FILE = QZ_KEY_DIR / "digital-certificate.txt"
QZ_PRIVATE_KEY_FILE = QZ_KEY_DIR / "private-key.pem"
MAX_SIGN_REQUEST_BYTES = 2_000_000


def _plain_response(message, *, status=200):
    response = HttpResponse(
        message,
        status=status,
        content_type="text/plain; charset=utf-8",
    )
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    return response


@require_GET
@never_cache
def qz_certificate(request):
    """Return the public QZ Tray certificate to the browser."""
    if not QZ_CERTIFICATE_FILE.is_file():
        logger.error(
            "QZ certificate missing: %s",
            QZ_CERTIFICATE_FILE,
        )
        return _plain_response(
            "QZ certificate is not installed. Expected: "
            f"{QZ_CERTIFICATE_FILE}",
            status=503,
        )

    try:
        certificate = QZ_CERTIFICATE_FILE.read_text(
            encoding="utf-8-sig"
        ).strip()
    except OSError:
        logger.exception(
            "Unable to read QZ certificate: %s",
            QZ_CERTIFICATE_FILE,
        )
        return _plain_response(
            "Unable to read the QZ certificate.",
            status=500,
        )

    if not certificate:
        return _plain_response(
            "QZ certificate file is empty.",
            status=503,
        )

    return _plain_response(certificate + "\n")


@lru_cache(maxsize=1)
def _load_private_key():
    """
    Load the matching QZ Tray PKCS#8 PEM private key.

    The result is cached for the lifetime of the Django process. Restart
    Django/Gunicorn after replacing the key files.
    """
    if not QZ_PRIVATE_KEY_FILE.is_file():
        raise FileNotFoundError(
            f"QZ private key is missing: {QZ_PRIVATE_KEY_FILE}"
        )

    key_bytes = QZ_PRIVATE_KEY_FILE.read_bytes()

    private_key = serialization.load_pem_private_key(
        key_bytes,
        password=None,
    )

    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise ValueError("QZ private key must be an RSA private key.")

    if private_key.key_size < 2048:
        raise ValueError("QZ RSA private key must be at least 2048 bits.")

    return private_key


@login_required
@require_POST
@never_cache
def qz_sign(request):
    """
    Sign a QZ Tray request using RSA PKCS#1 v1.5 + SHA-512.

    Browser JSON:
        {"request": "<QZ string to sign>"}

    Response:
        Base64-encoded signature as plain text.
    """
    if len(request.body) > MAX_SIGN_REQUEST_BYTES:
        return _plain_response(
            "QZ signing request is too large.",
            status=413,
        )

    try:
        payload = json.loads(
            request.body.decode("utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _plain_response(
            "Invalid JSON signing request.",
            status=400,
        )

    data_to_sign = payload.get("request")

    if not isinstance(data_to_sign, str) or not data_to_sign:
        return _plain_response(
            "Missing QZ request to sign.",
            status=400,
        )

    try:
        private_key = _load_private_key()
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return _plain_response(
            "QZ private key is not installed. Expected: "
            f"{QZ_PRIVATE_KEY_FILE}",
            status=503,
        )
    except (TypeError, ValueError):
        logger.exception(
            "QZ private key is invalid, encrypted, or not RSA"
        )
        return _plain_response(
            "QZ private key is invalid. Use the unencrypted "
            "private-key.pem that matches digital-certificate.txt.",
            status=500,
        )
    except OSError:
        logger.exception(
            "Unable to read QZ private key: %s",
            QZ_PRIVATE_KEY_FILE,
        )
        return _plain_response(
            "Unable to read the QZ private key.",
            status=500,
        )

    try:
        signature_bytes = private_key.sign(
            data_to_sign.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA512(),
        )
    except Exception:
        logger.exception("Unable to sign QZ request")
        return _plain_response(
            "Unable to sign the QZ request.",
            status=500,
        )

    signature = base64.b64encode(
        signature_bytes
    ).decode("ascii")

    return _plain_response(signature)
