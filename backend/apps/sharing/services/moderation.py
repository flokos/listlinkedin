"""Moderation (docs/v2/13-SECURITY.md#moderation): reports from people who can see a list or
group, and what the operator does about them.

A report emails the operator at once, from the api, as allauth's mail is sent; the worker
isn't used, since its egress rules may keep it from the mail relay. Operator actions run
from a shell through management commands. Shell access is their authorization, so they
don't go through the policy (docs/v2/12-AUTHORIZATION.md#operator-actions).
"""

import logging
import smtplib
from enum import StrEnum
from urllib.parse import urlsplit
from uuid import UUID

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from apps.common import errors

from .. import selectors
from ..models import SharedLink, SharedList
from ..policy import Action, Visibility, can
from ..selectors import Principal

logger = logging.getLogger(__name__)

MAX_DETAILS_LENGTH = 1000


class Reason(StrEnum):
    PHISHING = "phishing"  # phishing or malware
    SPAM = "spam"
    ILLEGAL = "illegal"
    OTHER = "other"


REASON_LABELS = {
    Reason.PHISHING: "Phishing or malware",
    Reason.SPAM: "Spam",
    Reason.ILLEGAL: "Illegal content",
    Reason.OTHER: "Something else",
}


def report_list(principal: Principal, code: str, *, reason: Reason, details: str = "") -> None:
    """Tell the operator about a list. Anyone who can view it may, except its owner (and
    the holder of a legacy list's edit link). 404 if not viewable, 410 if expired."""
    shared_list, access = selectors.get_list_for(principal, code)
    if not can(access.actor, Action.REPORT, access.facts):
        raise errors.Forbidden("You can't report your own list.")
    owner = f"user {shared_list.owner_id}" if shared_list.owner_id else "an edit link (no account)"
    notify_operator(
        kind="list",
        title=shared_list.title,
        url=f"{settings.PUBLIC_BASE_URL}/l/{shared_list.public_code}/{shared_list.slug}",
        code=shared_list.public_code,
        visibility=shared_list.visibility,
        owner=owner,
        reporter=principal.user,
        reason=reason,
        details=details,
        actions=[
            f"python manage.py unpublish_list {shared_list.public_code} --reason '…'",
            f"python manage.py delete_list {shared_list.public_code} --reason '…' --yes",
        ]
        + (
            [f"python manage.py suspend_account {shared_list.owner_id} --reason '…' --unpublish"]
            if shared_list.owner_id
            else []
        ),
        object_id=shared_list.pk,
    )


def notify_operator(
    *,
    kind: str,
    title: str,
    url: str,
    code: str,
    visibility: str,
    owner: str,
    reporter,
    reason: Reason,
    details: str,
    actions: list[str],
    object_id: UUID,
) -> None:
    """Email a report to MODERATION_EMAIL. The reporter appears by user id only: never their
    email address or IP. Without MODERATION_EMAIL the report is only logged, without its
    details (they are the reporter's own words). A failing relay is a 503."""
    who = f"user {reporter.pk}" if reporter is not None else "someone who wasn't signed in"
    logger.info("Report on %s %s: %s, by %s", kind, object_id, reason.value, who)
    if not settings.MODERATION_EMAIL:
        logger.warning("Report on %s %s not emailed: MODERATION_EMAIL isn't set", kind, object_id)
        return
    one_line = " ".join(title.split())[:80]
    subject = f"[listlinkedin] Report: {REASON_LABELS[reason]}, {kind} “{one_line}”"
    body = "\n".join(
        [
            f"Someone reported a {kind} on listlinkedin.",
            "",
            f"Reason: {REASON_LABELS[reason]}",
            f"Details: {details.strip() or '(none)'}",
            "",
            f"{kind.capitalize()}: {title}",
            f"Address: {url}",
            f"Code: {code}",
            f"Visibility: {visibility}",
            f"Owner: {owner}",
            f"Reported by: {who}",
            "",
            "To act on it, run on the server (docs/v2/13-SECURITY.md#moderation):",
            *(f"  {action}" for action in actions),
            "",
        ]
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [settings.MODERATION_EMAIL])
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("Report on %s %s not emailed: %s", kind, object_id, type(exc).__name__)
        raise errors.Unavailable("Your report couldn't be sent. Please try again later.") from exc


# Operator actions (management commands).


@transaction.atomic
def unpublish_list(code: str, *, reason: str) -> SharedList:
    """Make a list private: only its owner and the people on it can still open it, and its
    short URLs answer 404 to everyone else. A legacy list must stay unlisted (CHECK L3), so
    it can only be deleted."""
    locked = _lock_by_code(code)
    if locked.is_legacy:
        raise errors.Conflict(
            "This list has no account owner, so it can't be private. Delete it instead."
        )
    if locked.visibility != Visibility.PRIVATE.value:
        locked.visibility = Visibility.PRIVATE.value
        locked.save(update_fields=["visibility", "updated_at"])
    logger.info("Operator unpublished list %s: %s", locked.pk, reason)
    return locked


@transaction.atomic
def delete_list(code: str, *, reason: str) -> None:
    """Delete a list with its links, short URLs and memberships, as its owner could."""
    locked = _lock_by_code(code)
    list_id = locked.pk
    locked.delete()
    logger.info("Operator deleted list %s: %s", list_id, reason)


@transaction.atomic
def make_lists_private_owned_by(user) -> int:
    """Unpublish every public or unlisted list the user owns (suspending an account)."""
    ids = list(
        SharedList.objects.select_for_update()
        .filter(owner=user)
        .exclude(visibility=Visibility.PRIVATE.value)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    for shared_list in SharedList.objects.filter(pk__in=ids):
        shared_list.visibility = Visibility.PRIVATE.value
        shared_list.save(update_fields=["visibility", "updated_at"])
    return len(ids)


def find_links(host: str) -> list[dict]:
    """Live links to `host` or any of its subdomains, with their lists: for sweeping a
    phishing domain (then block it with BLOCKED_DESTINATION_HOSTS)."""
    host = host.strip().lower().rstrip(".")
    found = []
    candidates = (
        SharedLink.objects.filter(deleted_at__isnull=True, destination_url__icontains=host)
        .select_related("shared_list")
        .order_by("shared_list__public_code", "position")
    )
    for link in candidates:
        hostname = (urlsplit(link.destination_url).hostname or "").lower()
        if hostname == host or hostname.endswith("." + host):
            found.append(
                {
                    "list": link.shared_list.public_code,
                    "title": link.shared_list.title,
                    "visibility": link.shared_list.visibility,
                    "owner": link.shared_list.owner_id,
                    "url": link.destination_url,
                }
            )
    return found


def _lock_by_code(code: str) -> SharedList:
    locked = SharedList.objects.select_for_update().filter(public_code=code).first()
    if locked is None:
        raise errors.NotVisible(f"There is no list with the code {code}.")
    return locked
