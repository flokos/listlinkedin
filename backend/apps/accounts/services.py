"""Write operations on accounts. Sign-up, sign-in and passwords are handled by allauth."""

import logging

from django.db import transaction
from django.db.models import ProtectedError
from rest_framework.exceptions import ValidationError

from apps.common import errors
from apps.sharing.services.lists import delete_lists_owned_by

from .models import User

logger = logging.getLogger(__name__)

CONFIRM_MISMATCH = "Type your email address exactly as shown to confirm."


def update_profile(user: User, *, display_name: str) -> User:
    user.display_name = display_name
    user.save(update_fields=["display_name"])
    return user


@transaction.atomic
def delete_account(user: User, *, confirm: str) -> int:
    """Delete the account and every list it owns, once the user has typed their email address.

    Returns how many lists were deleted. Memberships on other people's lists, email addresses
    and allauth's records go with the user row (CASCADE).
    """
    if confirm.strip().lower() != user.email.lower():
        raise ValidationError({"confirm": [CONFIRM_MISMATCH]})
    deleted = delete_lists_owned_by(user)
    user_id = user.pk
    try:
        with transaction.atomic():
            user.delete()
    except ProtectedError:
        # A list became theirs after the lists were locked (a claim or creation racing this).
        raise errors.Conflict(
            "Your lists changed while deleting your account. Try again."
        ) from None
    logger.info("Deleted user %s and %d owned lists", user_id, deleted)
    return deleted
