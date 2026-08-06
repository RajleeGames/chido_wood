
import os
from pathlib import Path

from dotenv import load_dotenv


# =========================================================
# BASE DIRECTORY AND ENVIRONMENT VARIABLES
# =========================================================

# Project directory containing manage.py.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load API credentials from:
# project_folder/.env
load_dotenv(
    dotenv_path=BASE_DIR / ".env",
    override=False,
)


# =========================================================
# SECURITY
# =========================================================

# Production secret key.
#
# Keep your GitHub repository private because this key is
# stored directly in settings.py.
SECRET_KEY = (
    "django-insecure-chido-wood-erp-production-"
    "7x9p4m2k8v6q1r5t3w0n9c7b4a2s8d6f"
)

# Production mode.
DEBUG = False

# Domains permitted to access the Django application.
ALLOWED_HOSTS = [
    "chidowood.store",
    "www.chidowood.store",
    "127.0.0.1",
    "localhost",
]


# =========================================================
# CSRF TRUSTED ORIGINS
# =========================================================

CSRF_TRUSTED_ORIGINS = [
    "https://chidowood.store",
    "https://www.chidowood.store",
]


# =========================================================
# PRODUCTION HTTPS SECURITY
# =========================================================

# Tells Django that HTTPS is handled by Nginx.
#
# Your Nginx proxy configuration must contain:
# proxy_set_header X-Forwarded-Proto $scheme;
SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)

# Redirect normal HTTP traffic to HTTPS.
SECURE_SSL_REDIRECT = True

# Cookies are sent over HTTPS only.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Prevent JavaScript from reading the session cookie.
SESSION_COOKIE_HTTPONLY = False

# Standard cross-site cookie protection.
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Prevent MIME-type sniffing.
SECURE_CONTENT_TYPE_NOSNIFF = True

# Control referrer information.
SECURE_REFERRER_POLICY = "same-origin"

# Protect against cross-origin window attacks.
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# Prevent the website from being loaded inside an iframe.
X_FRAME_OPTIONS = "DENY"


# =========================================================
# HTTP STRICT TRANSPORT SECURITY
# =========================================================

# Browser should always use HTTPS for one year.
#
# Enable this only after the SSL certificate for both
# domains is working correctly.
SECURE_HSTS_SECONDS = 31536000

# Apply HSTS to www.chidowood.store and other subdomains.
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# Permit browser HSTS preload support.
SECURE_HSTS_PRELOAD = True


# =========================================================
# APPLICATIONS
# =========================================================

INSTALLED_APPS = [
    # Django applications.
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    # CHIDO Wood ERP applications.
    "accounts",
    "core",
    "products",
    "inventory",
    "suppliers",
    "purchases",
    "customers",
    "sales",
    "expenses",
    "reports",
    "sms.apps.SMSConfig",
    "transport.apps.TransportConfig",
]


# =========================================================
# MIDDLEWARE
# =========================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =========================================================
# URLS, TEMPLATES, WSGI AND ASGI
# =========================================================

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": (
            "django.template.backends.django."
            "DjangoTemplates"
        ),
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                (
                    "django.template.context_processors."
                    "request"
                ),
                (
                    "django.contrib.auth.context_processors."
                    "auth"
                ),
                (
                    "django.contrib.messages.context_processors."
                    "messages"
                ),
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

ASGI_APPLICATION = "config.asgi.application"


# =========================================================
# DATABASE — SQLITE ONLY
# =========================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            # Wait before returning "database is locked".
            "timeout": 30,
        },
    },
}


# =========================================================
# PASSWORD VALIDATION
# =========================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# =========================================================
# INTERNATIONALIZATION
# =========================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Africa/Dar_es_Salaam"

USE_I18N = True

USE_TZ = True


# =========================================================
# STATIC FILES
# =========================================================

STATIC_URL = "/static/"

# Source static files used while developing.
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Destination created by:
# python manage.py collectstatic
STATIC_ROOT = BASE_DIR / "staticfiles"


# =========================================================
# MEDIA FILES
# =========================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"

FILE_UPLOAD_PERMISSIONS = 0o644

FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755


# =========================================================
# DEFAULT PRIMARY KEY
# =========================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =========================================================
# CUSTOM USER AND AUTHENTICATION
# =========================================================

AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "login"

LOGIN_REDIRECT_URL = "dashboard"

LOGOUT_REDIRECT_URL = "login"


# =========================================================
# SESSION CONFIGURATION
# =========================================================

SESSION_ENGINE = (
    "django.contrib.sessions.backends.db"
)

# Keep a logged-in session for eight hours.
SESSION_COOKIE_AGE = 60 * 60 * 8

# Do not update the session expiry on every request.
SESSION_SAVE_EVERY_REQUEST = False

# Keep the user logged in when the browser closes.
SESSION_EXPIRE_AT_BROWSER_CLOSE = False


# =========================================================
# BEEM AFRICA SMS
# =========================================================

# Only these sensitive API credentials are read from .env.
BEEM_API_KEY = os.getenv(
    "BEEM_API_KEY",
    "",
).strip()

BEEM_SECRET_KEY = os.getenv(
    "BEEM_SECRET_KEY",
    "",
).strip()

BEEM_SENDER_ID = os.getenv(
    "BEEM_SENDER_ID",
    "",
).strip().upper()

# API addresses can remain directly in settings.py.
BEEM_API_URL_SEND = (
    "https://apisms.beem.africa/v1/send"
)

BEEM_BALANCE_URL = (
    "https://apisms.beem.africa/"
    "public/v1/vendors/balance"
)

BEEM_DLR_URL = (
    "https://dlrapi.beem.africa/"
    "public/v1/delivery-reports"
)

BEEM_REQUEST_TIMEOUT = 30

SMS_SYNC_SEND_LIMIT = 50


# =========================================================
# EMAIL CONFIGURATION
# =========================================================

# Console backend means emails are printed in Gunicorn logs.
# This avoids requiring email API credentials for now.
EMAIL_BACKEND = (
    "django.core.mail.backends.console.EmailBackend"
)

DEFAULT_FROM_EMAIL = (
    "CHIDO Wood ERP <noreply@chidowood.store>"
)

SERVER_EMAIL = "errors@chidowood.store"


# =========================================================
# LOGGING
# =========================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "standard": {
            "format": (
                "{levelname} "
                "{asctime} "
                "{name}: "
                "{message}"
            ),
            "style": "{",
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },

    "root": {
        "handlers": [
            "console",
        ],
        "level": "INFO",
    },

    "loggers": {
        "django": {
            "handlers": [
                "console",
            ],
            "level": "INFO",
            "propagate": False,
        },

        "django.request": {
            "handlers": [
                "console",
            ],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

