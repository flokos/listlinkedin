"""Settings shared by every environment. All secrets come from the environment."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

# Absolute public URLs (/l/..., /r/...) are built from this; no domain is hardcoded.
PUBLIC_BASE_URL = os.environ["PUBLIC_BASE_URL"].rstrip("/")
_public = urlsplit(PUBLIC_BASE_URL)
if _public.scheme not in ("http", "https") or not _public.hostname:
    raise ImproperlyConfigured(
        "PUBLIC_BASE_URL must be an absolute http(s) URL such as https://go.example.com"
    )

INSTALLED_APPS = [
    "rest_framework",
    "drf_spectacular",
    "apps.sharing",
    "apps.shortener",
]

MIDDLEWARE = [
    "config.middleware.health_check",  # first: must bypass host checks and HTTPS redirect
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.request_size_limit",
    "config.middleware.noindex",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# Needed only for the Swagger UI / ReDoc pages served by drf-spectacular.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["POSTGRES_DB"],
        "USER": os.environ["POSTGRES_USER"],
        "PASSWORD": os.environ["POSTGRES_PASSWORD"],
        "HOST": os.environ["POSTGRES_HOST"],
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

USE_TZ = True
TIME_ZONE = "UTC"
USE_I18N = False

# Requests carry at most a title and a URL; reject anything much larger.
DATA_UPLOAD_MAX_MEMORY_SIZE = 16 * 1024

# Backs rate limiting. A PostgreSQL table, so counters are shared by every worker and
# instance without adding Redis. Created by `manage.py createcachetable` (migrate service).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "rate_limit_cache",
        # Django's default (300) culls live throttle histories once exceeded, resetting
        # limits. Expired rows are pruned anyway, so a high ceiling is safe.
        "OPTIONS": {"MAX_ENTRIES": 100_000},
    }
}

# Hosts links may not point to (subdomains included), e.g. to shut down a phishing domain.
# This service's own host is always blocked: it would only create redirect loops/chains.
BLOCKED_DESTINATION_HOSTS = env_list("BLOCKED_DESTINATION_HOSTS")

SECURE_REFERRER_POLICY = "no-referrer"  # list/short URLs are capabilities; never leak them

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    # No user accounts: ownership is checked per list (apps.sharing.permissions).
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Per client IP. Overridable for load or end-to-end testing; keep the defaults in production.
    "DEFAULT_THROTTLE_RATES": {
        "list_create": os.environ.get("THROTTLE_LIST_CREATE", "30/hour"),
        "list_manage": os.environ.get("THROTTLE_LIST_MANAGE", "600/hour"),
    },
    # 0 = use the socket address. DRF's default (None) trusts a client-supplied
    # X-Forwarded-For, which would let anyone bypass rate limits.
    "NUM_PROXIES": 0,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Temporary Link Sharing API",
    "DESCRIPTION": (
        "Anonymous, temporary link lists with a built-in URL shortener.\n\n"
        "* Creating a list returns a private `owner_token` **once**. It cannot be recovered.\n"
        "* Owner-only operations require `Authorization: Bearer <owner_token>`.\n"
        "* Lists expire exactly 30 days after creation. Expired lists, their links and "
        "short URLs answer `410 Gone` until they are physically deleted (`404` afterwards).\n"
        "* `GET /r/{code}` redirects (302) to the link's current destination; "
        "`GET /l/{code}` redirects (302) to the list's API representation."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "default"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
