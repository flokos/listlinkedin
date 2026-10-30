"""Write operations on accounts. Sign-up, sign-in and passwords are handled by allauth."""

import logging
import uuid

from allauth.account.models import EmailAddress
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.common import errors
from apps.groups.services import (
    delete_groups_owned_by,
    make_groups_private_owned_by,
    remove_group_memberships_of,
)
from apps.sharing.services.lists import delete_lists_owned_by
from apps.sharing.services.members import remove_memberships_of
from apps.sharing.services.moderation import make_lists_private_owned_by

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

    The lists and groups it owns are deleted (links, short URLs, memberships and history with
    them), it is taken off other people's lists and groups, and its email addresses, name and
    password go. The row stays, inactive, so the revisions it wrote on other lists keep an
    author ("Deleted account") without the revision rows ever changing. Returns False if it
    was restored or erased in the meantime.
    """
    user = User.objects.select_for_update().filter(pk=user_id).first()
    if user is None or user.deleted_at is None or not user.is_active:
        return False
    deleted_groups = delete_groups_owned_by(user)
    deleted_lists = delete_lists_owned_by(user)
    removed = remove_memberships_of(user) + remove_group_memberships_of(user)
    EmailAddress.objects.filter(user=user).delete()
    user.email = f"deleted-{user.pk}@deleted.invalid"  # frees the address for a new sign-up
    user.display_name = user.first_name = user.last_name = ""
    user.set_unusable_password()
    user.is_active = False
    user.save()
    logger.info(
        "Erased user %s: %d groups and %d lists deleted, %d memberships removed",
        user.pk,
        deleted_groups,
        deleted_lists,
        removed,
    )
    return True


# Moderation (docs/v2/13-SECURITY.md#moderation): the operator's management commands.


def find_account(email_or_id: str) -> User:
    """The account with this email address or user id (as report emails show it)."""
    value = email_or_id.strip()
    try:
        user = User.objects.filter(pk=uuid.UUID(value)).first()
    except ValueError:
        user = User.objects.filter(email__iexact=value).first()
    if user is None:
        raise errors.NotVisible(f"There is no account {value}.")
    return user


@transaction.atomic
def suspend_account(user: User, *, reason: str, unpublish: bool = False) -> tuple[int, int]:
    """Stop an account from signing in, and end its sessions on every device. With
    `unpublish`, its public and unlisted lists and groups become private too. Returns how
    many lists and groups were unpublished. Suspending again changes nothing more."""
    locked = User.objects.select_for_update().get(pk=user.pk)
    if locked.suspended_at is None:
        locked.suspended_at = locked.sessions_revoked_at = timezone.now()
        locked.save(update_fields=["suspended_at", "sessions_revoked_at"])
    lists = groups = 0
    if unpublish:
        lists = make_lists_private_owned_by(locked)
        groups = make_groups_private_owned_by(locked)
    logger.info(
        "Operator suspended user %s (%d lists and %d groups unpublished): %s",
        locked.pk,
        lists,
        groups,
        reason,
    )
    return lists, groups


@transaction.atomic
def unsuspend_account(user: User, *, reason: str) -> None:
    """Let the account sign in again. Sessions ended by the suspension stay ended, and
    unpublished lists and groups stay private: their owner decides again."""
    locked = User.objects.select_for_update().get(pk=user.pk)
    if locked.suspended_at is not None:
        locked.suspended_at = None
        locked.save(update_fields=["suspended_at"])
    logger.info("Operator unsuspended user %s: %s", locked.pk, reason)
