import os

from .base import *  # noqa: F403
from .base import DATABASES, REST_FRAMEWORK

DEBUG = False

# TLS terminates at the reverse proxy, which must set X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
# The API sets no cookies today; keep them secure if that ever changes.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SILENCED_SYSTEM_CHECKS = [
    "security.W003",  # no CSRF middleware: no cookies or session auth, only bearer tokens
    "security.W021",  # HSTS preload is an irreversible, domain-wide decision for the operator
]

# Lets rate limiting read the real client IP from X-Forwarded-For.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "NUM_PROXIES": int(os.environ.get("DJANGO_NUM_PROXIES", "1")),
}

DATABASES = {
    "default": {
        **DATABASES["default"],
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        # Fail fast instead of parking sync Gunicorn workers behind a stuck lock or query.
        # The statement timeout stays below Gunicorn's 30 s worker timeout so a slow query
        # ends in a clean error, not a killed worker. Raise only for a heavy migration.
        "OPTIONS": {"options": "-c lock_timeout=5s -c statement_timeout=20s"},
    }
}
