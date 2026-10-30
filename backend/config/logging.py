"""Logging (docs/v2/14-INFRASTRUCTURE.md#health-checks-and-observability): every record
carries the id of the request it belongs to, and production writes one JSON object per line.

nginx gives each request an id ($request_id, sent as X-Request-ID), which it also writes to
its access log; `config.middleware.request_id` adopts it, or makes one when there is no nginx
in front (development). Records outside a request, in the worker or a command, have "-".
"""

import contextvars
import json
import logging
import re
import uuid
from datetime import UTC, datetime

REQUEST_ID = contextvars.ContextVar("request_id", default="-")
# The signed-in user's id while handling a request ("who" in ASVS V16.2.1), never an address.
USER_ID = contextvars.ContextVar("user_id", default="-")

# What we accept from the header: nginx sends 32 hex digits. Anything else is replaced, so a
# client can't put arbitrary text into the logs.
_VALID_ID = re.compile(r"[A-Za-z0-9-]{8,64}")


def request_id_from(header: str | None) -> str:
    """The request's id: the one nginx sent, or a new one."""
    if header and _VALID_ID.fullmatch(header):
        return header
    return uuid.uuid4().hex


class RequestIdFilter(logging.Filter):
    """Adds `request_id` and `user_id` to every record, for the formatters."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = REQUEST_ID.get()
        record.user_id = USER_ID.get()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line: time (UTC), level, logger, message, request id, user id and,
    for errors, the traceback. Log aggregators read it without a parsing rule."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "user_id": getattr(record, "user_id", "-"),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)
