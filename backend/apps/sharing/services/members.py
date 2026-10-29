"""People on a list (docs/v2/12-AUTHORIZATION.md): the owner adds existing accounts by email
as editors or viewers, changes their roles and removes them; members may leave.

Every change takes the list's row lock and re-checks the policy under it, so it serializes
with writes on that list: an editor removed while saving can't commit after the removal.
"""

import logging
from uuid import UUID

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.accounts.selectors import user_to_share_with
from apps.common import errors

from ..models import ListMembership
from ..policy import Action, Role, can
from ..selectors import Principal
from .lists import _lock, denied

logger = logging.getLogger(__name__)

VERIFY_EMAIL_TO_SHARE = "Verify your email address to add people to your lists."
# The same answer for "no account", "not verified yet" and anything else that keeps us from
# adding someone, so the form reveals as little as it can about who has an account.
CANNOT_ADD = (
    "We couldn't add this person. They need an account with a verified email address: "
    "ask them to sign up, then try again."
)


@transaction.atomic
def add_member(principal: Principal, list_id: UUID, *, email: str, role: Role) -> ListMembership:
    locked, actor, facts = _lock(principal, list_id, with_email=True)
    if not can(actor, Action.MEMBERS, facts):
        raise denied(principal, "Only the list's owner can add people.")
    if not actor.email_verified:
        raise errors.Forbidden(VERIFY_EMAIL_TO_SHARE, code="email_unverified")
    user = user_to_share_with(email)
    if user is None:
        raise ValidationError({"email": [CANNOT_ADD]})
    if user.pk == locked.owner_id:
        raise ValidationError({"email": ["That's you. You own this list already."]})  # L6
    membership, created = ListMembership.objects.get_or_create(
        shared_list=locked, user=user, defaults={"role": role.value, "added_by": principal.user}
    )
    if not created:
        raise ValidationError({"email": ["This person is already on the list."]})
    logger.info("User %s added to list %s as %s", user.pk, locked.id, role.value)
    return membership


@transaction.atomic
def change_role(principal: Principal, list_id: UUID, user_id: UUID, role: Role) -> ListMembership:
    locked, actor, facts = _lock(principal, list_id)
    if not can(actor, Action.MEMBERS, facts):
        raise errors.Forbidden("Only the list's owner can change roles.")
    membership = _membership(locked, user_id)
    if membership.role != role.value:
        membership.role = role.value
        membership.save(update_fields=["role"])
        logger.info("User %s is now %s on list %s", user_id, role.value, locked.id)
    return membership


@transaction.atomic
def remove_member(principal: Principal, list_id: UUID, user_id: UUID) -> None:
    """The owner removes someone, or a member leaves (removes themselves)."""
    locked, actor, facts = _lock(principal, list_id)
    leaving = principal.user is not None and principal.user.pk == user_id
    if leaving and not can(actor, Action.LEAVE, facts):
        raise errors.Forbidden("Owners can't leave their own list. Delete it instead.")
    if not leaving and not can(actor, Action.MEMBERS, facts):
        raise errors.Forbidden("Only the list's owner can remove people.")
    _membership(locked, user_id).delete()
    logger.info("User %s removed from list %s", user_id, locked.id)


def _membership(shared_list, user_id: UUID) -> ListMembership:
    membership = ListMembership.objects.filter(shared_list=shared_list, user_id=user_id).first()
    if membership is None:
        raise errors.NotVisible("This person isn't on the list.")
    return membership
