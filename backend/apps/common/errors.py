"""Business errors that domain and service code raises without knowing about HTTP.

This module must not import Django or DRF. `config.exceptions.exception_handler` maps each
class to an HTTP status and puts `code` in the response body (docs/v2/09-API-DESIGN.md).
Subclass the closest category; the status follows the class hierarchy.
"""

from typing import Any


class DomainError(Exception):
    code = "error"
    default_message = "The request could not be completed."

    def __init__(
        self, message: str | None = None, *, code: str | None = None, **extra: Any
    ) -> None:
        self.message = message or self.default_message
        if code is not None:
            self.code = code  # a more specific code than the class's, e.g. idempotency_key_reused
        self.extra = extra  # additional response fields, e.g. a fresh fingerprint
        super().__init__(self.message)


class NotVisible(DomainError):
    """The resource doesn't exist or the actor may not see it (indistinguishable on purpose)."""

    code = "not_found"
    default_message = "Not found."


class AuthenticationRequired(DomainError):
    code = "not_authenticated"
    default_message = "Sign in to continue."


class Forbidden(DomainError):
    code = "permission_denied"
    default_message = "You don't have permission to do this."


class Expired(DomainError):
    code = "gone"
    default_message = "This has expired."


class Conflict(DomainError):
    code = "conflict"
    default_message = "The request conflicts with the current state."


class RevisionMismatch(DomainError):
    code = "revision_mismatch"
    default_message = "This changed since you loaded it."


class PreconditionRequired(DomainError):
    code = "precondition_required"
    default_message = "This request needs an If-Match header."


class Unprocessable(DomainError):
    code = "unprocessable"
    default_message = "The request can't be applied."
