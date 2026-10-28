import os
import re

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import DATABASES, REST_FRAMEWORK

DEBUG = False

# TLS terminates at the reverse proxy, which must set X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
# Session (sign-in) and CSRF cookies only ever travel over HTTPS.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SILENCED_SYSTEM_CHECKS = [
    "security.W021",  # HSTS preload is an irreversible, domain-wide decision for the operator
]

# Lets rate limiting read the real client IP from X-Forwarded-For.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "NUM_PROXIES": int(os.environ.get("DJANGO_NUM_PROXIES", "1")),
}
# allauth's sign-in and password-reset rate limits read the client IP the same way.
ALLAUTH_TRUSTED_PROXY_COUNT = REST_FRAMEWORK["NUM_PROXIES"]

# Real mail in production (verification and password-reset links). Configure EMAIL_* in .env.
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)


def _pg_duration(name: str, default: str) -> str:
    value = os.environ.get(name, default)
    if not re.fullmatch(r"\d+(ms|s|min)?", value):
        raise ImproperlyConfigured(f"{name} must be a PostgreSQL duration such as 20s or 0")
    return value


DATABASES = {
    "default": {
        **DATABASES["default"],
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        # Fail fast instead of parking sync Gunicorn workers behind a stuck lock or query.
        # The statement timeout stays below Gunicorn's 30 s worker timeout so a slow query
        # ends in a clean error, not a killed worker. The one-shot `migrate` service sets
        # DB_STATEMENT_TIMEOUT=0 so a long data migration only fails on real problems.
        "OPTIONS": {
            "options": (
                f"-c lock_timeout={_pg_duration('DB_LOCK_TIMEOUT', '5s')}"
                f" -c statement_timeout={_pg_duration('DB_STATEMENT_TIMEOUT', '20s')}"
            )
        },
    }
}
