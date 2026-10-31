"""DRF exception handler: maps domain errors to HTTP and adds `code` to v2 error bodies.

Responses outside the API (`/r/`) keep their plain shape. Under `/api/v2/` every error body
also carries a stable machine `code` (docs/v2/09-API-DESIGN.md#error-format).
"""

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.views import exception_handler as drf_exception_handler

from apps.common import errors

STATUS_BY_ERROR: dict[type[errors.DomainError], int] = {
    errors.NotVisible: status.HTTP_404_NOT_FOUND,
    errors.AuthenticationRequired: status.HTTP_401_UNAUTHORIZED,
    errors.Forbidden: status.HTTP_403_FORBIDDEN,
    errors.Expired: status.HTTP_410_GONE,
    errors.Conflict: status.HTTP_409_CONFLICT,
    errors.RevisionMismatch: status.HTTP_412_PRECONDITION_FAILED,
    errors.PreconditionRequired: status.HTTP_428_PRECONDITION_REQUIRED,
    errors.Unprocessable: status.HTTP_422_UNPROCESSABLE_ENTITY,
    errors.Unavailable: status.HTTP_503_SERVICE_UNAVAILABLE,
}


def exception_handler(exc, context):
    domain_error = exc if isinstance(exc, errors.DomainError) else None
    if domain_error is not None:
        exc = _as_api_exception(domain_error, context)

    response = drf_exception_handler(exc, context)
    if response is None or not context["request"].path.startswith("/api/v2/"):
        return response
    if isinstance(response.data, dict):
        response.data["code"] = domain_error.code if domain_error else _code_for(exc)
        if domain_error is not None:
            response.data.update(domain_error.extra)
    return response


def _as_api_exception(error: errors.DomainError, context) -> exceptions.APIException:
    if isinstance(error, errors.AuthenticationRequired):
        # Same 401-vs-403 rule as DRF: 401 only when the view names an auth challenge.
        api_exc = exceptions.NotAuthenticated(error.message, error.code)
        view, request = context.get("view"), context.get("request")
        header = view.get_authenticate_header(request) if view and request else None
        if header:
            api_exc.auth_header = header
        else:
            api_exc.status_code = status.HTTP_403_FORBIDDEN
        return api_exc
    api_exc = exceptions.APIException(error.message, error.code)
    api_exc.status_code = _status_for(error)
    return api_exc


def _status_for(error: errors.DomainError) -> int:
    for cls in type(error).__mro__:
        if cls in STATUS_BY_ERROR:
            return STATUS_BY_ERROR[cls]
    return status.HTTP_400_BAD_REQUEST


def _code_for(exc) -> str:
    if isinstance(exc, Http404):
        return "not_found"
    if isinstance(exc, DjangoPermissionDenied):
        return "permission_denied"
    if isinstance(exc, exceptions.ValidationError):
        return "invalid"
    if isinstance(exc, exceptions.APIException):
        codes = exc.get_codes()
        return codes if isinstance(codes, str) else "invalid"
    return "error"
