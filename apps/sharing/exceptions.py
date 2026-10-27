from rest_framework import status
from rest_framework.exceptions import APIException


class Gone(APIException):
    """The resource still exists but has expired (or was deactivated)."""

    status_code = status.HTTP_410_GONE
    default_detail = "This list has expired."
    default_code = "gone"
