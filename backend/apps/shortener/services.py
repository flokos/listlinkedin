import logging
from collections.abc import Callable

from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound

from apps.sharing import selectors
from apps.sharing.domain import is_blocked_destination
from apps.sharing.exceptions import Gone
from apps.sharing.policy import Action, can

from . import generators
from .models import REDIRECT_CODE_CONSTRAINT, ShortRedirect

logger = logging.getLogger(__name__)

MAX_CODE_ATTEMPTS = 5


def create_with_unique_code[T](create: Callable[[str], T], constraint_name: str) -> T:
    """Insert a row identified by a fresh random code, retrying on a code collision.

    Uniqueness is enforced by the database constraint, so this is safe across concurrent
    processes. Each attempt runs in a savepoint so a collision does not abort the caller's
    transaction. Integrity errors from any other constraint are re-raised immediately.
    """
    for _ in range(MAX_CODE_ATTEMPTS):
        code = generators.generate_short_code()
        try:
            with transaction.atomic():
                return create(code)
        except IntegrityError as exc:
            if _violated_constraint(exc) != constraint_name:
                raise
            logger.warning("Short code collision on %s; retrying", constraint_name)
    raise RuntimeError(f"Could not generate a unique code after {MAX_CODE_ATTEMPTS} attempts")


def _violated_constraint(exc: IntegrityError) -> str | None:
    diag = getattr(exc.__cause__, "diag", None)
    return getattr(diag, "constraint_name", None)


def create_redirect(link) -> ShortRedirect:
    return create_with_unique_code(
        lambda code: ShortRedirect.objects.create(code=code, link=link),
        REDIRECT_CODE_CONSTRAINT,
    )


def resolve_destination(code: str, principal=None) -> str:
    """Return the current destination for a short code, or raise 404/410.

    The code never bypasses its list's visibility (S2): a private list's links answer 404,
    like unknown codes, unless `principal` (the requester) may view that list.
    """
    redirect = ShortRedirect.objects.select_related("link__shared_list").filter(code=code).first()
    if redirect is None:
        raise NotFound()
    shared_list = redirect.link.shared_list
    principal = principal or selectors.ANONYMOUS
    actor = selectors.actor_for(principal, shared_list)
    if not can(actor, Action.VIEW, selectors.facts_for(principal, shared_list)):
        raise NotFound()
    destination = redirect.link.destination_url
    # The denylist is re-checked here so blocking a host also disables links already shared.
    if (
        redirect.link.shared_list.is_expired
        or not redirect.is_active
        or is_blocked_destination(destination)
    ):
        raise Gone("This short URL is no longer available.")
    return destination
