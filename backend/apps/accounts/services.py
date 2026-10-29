"""Write operations on accounts. Sign-up, sign-in and passwords are handled by allauth."""

import logging

from allauth.account.models import EmailAddress
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.common import errors
from apps.sharing.services.lists import delete_lists_owned_by
from apps.sharing.services.members import remove_memberships_of

from .models import DELETION_GRACE, User

logger = logging.getLogger(__name__)

CONFIRM_MISMATCH = "Type your email address exactly as shown to confirm."


def update_profile(user: User, *, display_name: str) -> User:
    user.display_name = display_name
    user.save(update_fields=["display_name"])
    return user


@transaction.atomic
def delete_account(user: User, *, confirm: str) -> User:
    """Start deleting the account, once the user has typed their email address.

    It takes effect for everyone else at once: every session ends, the lists it owns are
    hidden, and it no longer appears on lists it was added to. Its data is erased only after
    DELETION_GRACE (`purge_deleted_accounts`); signing in before then can restore it
    (docs/v2/adr/ADR-016).
    """
    if confirm.strip().lower() != user.email.lower():
        raise ValidationError({"confirm": [CONFIRM_MISMATCH]})
    locked = User.objects.select_for_update().get(pk=user.pk)
    if locked.deleted_at is None:
        now = timezone.now()
        locked.deleted_at = locked.sessions_revoked_at = now
        locked.save(update_fields=["deleted_at", "sessions_revoked_at"])
        logger.info("Scheduled deletion of user %s", locked.pk)
    return locked


@transaction.atomic
def restore_account(user: User) -> User:
    """Undo a deletion within the grace period: lists and memberships come back as they were."""
    locked = User.objects.select_for_update().get(pk=user.pk)
    if locked.deleted_at is None:
        return locked
    if not locked.is_active:  # already erased: there is nothing left to restore
        raise errors.Conflict("This account has already been deleted.")
    locked.deleted_at = None
    locked.save(update_fields=["deleted_at"])
    logger.info("Restored user %s", locked.pk)
    return locked


def purge_deleted_accounts(now=None) -> int:
    """Erase every account whose grace period is over. Returns how many were erased."""
    cutoff = (now or timezone.now()) - DELETION_GRACE
    ids = User.objects.filter(deleted_at__lte=cutoff, is_active=True).values_list("pk", flat=True)
    return sum(1 for user_id in list(ids) if purge_account(user_id))


@transaction.atomic
def purge_account(user_id) -> bool:
    """Erase one account's personal data and everything it owns, keeping an anonymous row.

    The lists it owns are deleted (links, short URLs, memberships and history with them), it
    is taken off other people's lists, and its email addresses, name and password go. The row
    stays, inactive, so the revisions it wrote on other lists keep an author ("Deleted
    account") without the revision rows ever changing. Returns False if it was restored or
    erased in the meantime.
    """
    user = User.objects.select_for_update().filter(pk=user_id).first()
    if user is None or user.deleted_at is None or not user.is_active:
        return False
    deleted_lists = delete_lists_owned_by(user)
    removed = remove_memberships_of(user)
    EmailAddress.objects.filter(user=user).delete()
    user.email = f"deleted-{user.pk}@deleted.invalid"  # frees the address for a new sign-up
    user.display_name = user.first_name = user.last_name = ""
    user.set_unusable_password()
    user.is_active = False
    user.save()
    logger.info(
        "Erased user %s: %d lists deleted, %d memberships removed",
        user.pk,
        deleted_lists,
        removed,
    )
    return True
