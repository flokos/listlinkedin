"""Settings shared by every environment. All secrets come from the environment."""

import os
from datetime import timedelta
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
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.postgres",  # search, trigram and array lookups (phase 8)
    "rest_framework",
    "drf_spectacular",
    "allauth",
    "allauth.account",
    "allauth.headless",
    "django_tasks",
    "django_tasks_db",  # app label `django_tasks_database`: its tables and migrations
    "apps.accounts",
    "apps.groups",
    "apps.metadata",
    "apps.sharing",
    "apps.shortener",
    "apps.versioning",
]

MIDDLEWARE = [
    "config.middleware.health_check",  # first: must bypass host checks and HTTPS redirect
    "config.middleware.request_id",  # before anything that logs
    "config.middleware.no_store",
    "config.middleware.content_security_policy",
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.request_size_limit",
    "config.middleware.noindex",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # DRF views are exempt; DRF's SessionAuthentication enforces CSRF itself for signed-in
    # requests, so the V1 bearer-token API is unaffected.
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "config.middleware.log_user",  # after authentication: who, on every log record
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# Needed for the Swagger UI page served by drf-spectacular (config.docs) and allauth's emails.
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

# Accounts. A custom user from the first auth migration on (docs/v2/adr/ADR-007).
AUTH_USER_MODEL = "accounts.User"
# Both refuse suspended accounts (apps.accounts.backends), at sign-in and on every request.
AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.ModelBackend",
    "apps.accounts.backends.AuthenticationBackend",
]
# At least 8 characters, not a common password, not like the email address, not the site's
# name; any characters allowed (ASVS V6.2.5: no composition rules, so Django's
# NumericPasswordValidator is left out; common all-digit passwords are on the common list).
AUTH_PASSWORD_VALIDATORS = [
    *(
        {"NAME": f"django.contrib.auth.password_validation.{name}"}
        for name in (
            "UserAttributeSimilarityValidator",
            "MinimumLengthValidator",
            "CommonPasswordValidator",
        )
    ),
    {"NAME": "apps.accounts.validators.ContextWordsValidator"},
]
# Password-reset links work once and for an hour (Django's default is three days).
PASSWORD_RESET_TIMEOUT = 60 * 60

# The SPA is served from the same origin as the API, so the session cookie stays
# first-party. The CSRF cookie must be readable by the SPA (sent back as X-CSRFToken).
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [f"{_public.scheme}://{_public.netloc}"]

# django-allauth in headless mode: JSON endpoints under /_allauth/browser/v1/ for the SPA,
# no server-rendered pages. Emails link to the SPA's routes.
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_UNIQUE_EMAIL = True
# Signing in doesn't need a verified address; making things public will (docs/v2/13).
ACCOUNT_EMAIL_VERIFICATION = "optional"
# Refuses suspended accounts at sign-in (apps.accounts.adapter).
ACCOUNT_ADAPTER = "apps.accounts.adapter.AccountAdapter"
ACCOUNT_PREVENT_ENUMERATION = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[listlinkedin] "
HEADLESS_ONLY = True
HEADLESS_CLIENTS = ("browser",)  # session cookies + CSRF; no token-based app client
# Keys go in the URL fragment, which browsers never send to servers, so they stay out of
# nginx logs (as V1's edit links do). The SPA reads the key and removes it from the address bar.
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": f"{PUBLIC_BASE_URL}/verify-email#key={{key}}",
    "account_reset_password": f"{PUBLIC_BASE_URL}/reset-password",
    "account_reset_password_from_key": f"{PUBLIC_BASE_URL}/reset-password#key={{key}}",
    "account_signup": f"{PUBLIC_BASE_URL}/signup",
}
# allauth's own rate limits (failed sign-ins, sign-ups, reset requests) stay on, with its
# defaults except for sign-ups: 10 per hour per IP (docs/v2/13-SECURITY.md#rate-limits) instead
# of 20 a minute. The end-to-end suite turns them off for its throwaway stack, where every
# browser shares one IP.
ACCOUNT_RATE_LIMITS = {"signup": "10/h/ip"}
if os.environ.get("AUTH_RATE_LIMITS", "on") == "off":
    ACCOUNT_RATE_LIMITS = False

# Outgoing mail (verification, password reset). Development prints it to the console;
# production defaults to SMTP (config/settings/production.py).
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"
# `or`: compose passes unset values as empty strings.
DEFAULT_FROM_EMAIL = (
    os.environ.get("DEFAULT_FROM_EMAIL") or f"listlinkedin <no-reply@{_public.hostname}>"
)
# Mail is sent during the request (allauth's, and reports): a relay that hangs must not hold a
# Gunicorn worker until its own timeout.
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT") or "10")
# Where reports of abuse go (docs/v2/13-SECURITY.md#moderation). Empty: reports are only logged.
MODERATION_EMAIL = os.environ.get("MODERATION_EMAIL", "")

# Requests carry at most a title and a URL; reject anything much larger.
DATA_UPLOAD_MAX_MEMORY_SIZE = 16 * 1024
# The image upload routes (config.middleware.UPLOAD_PATH) take one file of up to 2 MB, plus
# room for the multipart framing. nginx allows 3 MB on the same routes.
UPLOAD_REQUEST_MAX_SIZE = 2 * 1024 * 1024 + 64 * 1024

# Uploaded images, re-encoded (apps.metadata.images). nginx serves MEDIA_URL from this
# directory in production; Django serves it only in development (DEBUG).
MEDIA_ROOT = os.environ.get("MEDIA_ROOT", "/srv/media")
MEDIA_URL = "/media/"

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

# Background tasks (docs/v2/adr/ADR-008): a queue in PostgreSQL, run by the `worker` service
# (`manage.py db_worker`). Tests use it too, running queued tasks with `db_worker --batch`:
# the immediate backend can't defer a task, which retries need. Code queues work only through
# apps.metadata.tasks.
TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend", "QUEUES": ["default"]}}
# A task must finish well within this. `check_worker` reports a queue that waits longer, and
# `recover_stuck_tasks` takes back tasks running longer (their worker died).
TASK_STALE_AFTER = timedelta(minutes=10)
# Extra address ranges the metadata fetcher never connects to, on top of its built-in ones
# (private, loopback, link-local and cloud metadata, apps.metadata.fetcher), e.g. a company's
# own public range or a VPN. Comma-separated CIDRs; additions only, nothing here can unblock.
FETCH_BLOCKED_NETWORKS = env_list("FETCH_BLOCKED_NETWORKS")
# End-to-end tests only: `name=service` pairs that let the fetcher reach a fixture site on the
# private compose network. Names must end in `.test`, a domain reserved so it never exists on
# the internet (RFC 2606); only the public-address check is skipped for them. Never set it in
# production: the app logs a warning at startup when it is set.
FETCH_TEST_HOSTS = env_list("FETCH_TEST_HOSTS")
# Fetching link metadata (task 7.3). Off for locked-down deployments.
METADATA_FETCH_ENABLED = os.environ.get("METADATA_FETCH_ENABLED", "true").lower() != "false"

# V1's anonymous list creation (POST /api/v1/lists/) answers 410 since V2. Test and e2e stacks
# turn it back on to create legacy lists for edit-link tests. Never on in production.
LEGACY_LIST_CREATION = os.environ.get("LEGACY_LIST_CREATION", "off") == "on"

# Hosts links may not point to (subdomains included), e.g. to shut down a phishing domain.
# This service's own host is always blocked: it would only create redirect loops/chains.
BLOCKED_DESTINATION_HOSTS = env_list("BLOCKED_DESTINATION_HOSTS")

SECURE_REFERRER_POLICY = "no-referrer"  # list/short URLs are capabilities; never leak them

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    # Every view declares its own: owner tokens per list in v1 (apps.sharing.permissions),
    # session login in v2 (apps.accounts.authentication).
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Maps domain errors to HTTP; adds a machine `code` to /api/v2/ error bodies.
    "EXCEPTION_HANDLER": "config.exceptions.exception_handler",
    # Per client IP. Overridable for load or end-to-end testing; keep the defaults in production.
    "DEFAULT_THROTTLE_RATES": {
        "list_create": os.environ.get("THROTTLE_LIST_CREATE", "30/hour"),
        "list_manage": os.environ.get("THROTTLE_LIST_MANAGE", "600/hour"),
        "group_create": os.environ.get("THROTTLE_GROUP_CREATE", "30/hour"),
        "group_manage": os.environ.get("THROTTLE_GROUP_MANAGE", "600/hour"),
        "account": os.environ.get("THROTTLE_ACCOUNT", "300/hour"),
        # Per user: adding people by email can probe which addresses have accounts.
        "member_add": os.environ.get("THROTTLE_MEMBER_ADD", "60/hour"),
        # Per user: each upload is decoded and re-encoded, which costs CPU and disk.
        "upload": os.environ.get("THROTTLE_UPLOAD", "120/hour"),
        # Per user or edit link: a restore rewrites a whole list (docs/v2/13-SECURITY.md).
        "restore": os.environ.get("THROTTLE_RESTORE", "120/hour"),
        # Per user: each refresh fetches a page (and 1/hour per link on top).
        "metadata_refresh": os.environ.get("THROTTLE_METADATA_REFRESH", "60/hour"),
        # Per client IP, signed in or not: directory searches and tag facets.
        "directory": os.environ.get("THROTTLE_DIRECTORY", "600/hour"),
        # Per user or client IP: each report emails the operator.
        "report": os.environ.get("THROTTLE_REPORT", "10/hour"),
    },
    # 0 = use the socket address. DRF's default (None) trusts a client-supplied
    # X-Forwarded-For, which would let anyone bypass rate limits.
    "NUM_PROXIES": 0,
}

SPECTACULAR_SETTINGS = {
    # The same editor/viewer choices appear on members and in requests: one named enum.
    "ENUM_NAME_OVERRIDES": {
        "MemberRoleEnum": "apps.sharing.models.MEMBER_ROLE_CHOICES",
        "OriginKindEnum": "apps.sharing.v2.serializers.ORIGIN_KIND_CHOICES",
        "RevisionKindEnum": "apps.versioning.models.RevisionKind",
        "MetadataStatusEnum": "apps.sharing.v2.serializers.METADATA_STATUSES",
        "VisibilityEnum": "apps.sharing.models.VISIBILITY_CHOICES",
    },
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
    # Served by config.docs from this origin, never from a CDN.
    "SWAGGER_UI_DIST": "/api/docs/assets",
    "SWAGGER_UI_FAVICON_HREF": "/api/docs/assets/favicon-32x32.png",
}

# Every record carries its request's id (config.logging); production logs JSON instead.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "config.logging.RequestIdFilter"}},
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s %(name)s [%(request_id)s %(user_id)s] %(message)s"
        },
        "json": {"()": "config.logging.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "filters": ["request_id"],
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
