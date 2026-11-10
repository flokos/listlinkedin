"""Reads on accounts that other apps may use. They get users through here, never by querying
the accounts tables themselves."""

from allauth.account.models import EmailAddress
from django.contrib.auth import HASH_SESSION_KEY
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from .models import ConnectedBrowser, User


def connected_browsers(user: User) -> list[ConnectedBrowser]:
    """The browsers connected to the account that still work, newest first (ADR-020).

    A connection works while its session exists, hasn't expired, and was signed in after the
    account's sessions were last ended: a password change ends them without touching a row,
    as it does for every session. Two queries, however many there are.
    """
    browsers = list(
        ConnectedBrowser.objects.filter(user=user, session_key__isnull=False).order_by(
            "-connected_at", "-pk"
        )
    )
    if not browsers:
        return []
    sessions = Session.objects.filter(
        session_key__in=[browser.session_key for browser in browsers],
        expire_date__gt=timezone.now(),
    )
    # As django.contrib.auth.get_user checks a session: the current hash, or one made with
    # a SECRET_KEY_FALLBACKS key.
    hashes = [user.get_session_auth_hash(), *user.get_session_auth_fallback_hash()]
    alive = {
        session.session_key
        for session in sessions
        if any(
            constant_time_compare(session.get_decoded().get(HASH_SESSION_KEY, ""), valid)
            for valid in hashes
        )
    }
    return [browser for browser in browsers if browser.session_key in alive]


def user_to_share_with(email: str) -> User | None:
    """The account an owner means when they add `email` to a list, or None.

    Only a *verified* address counts: anyone can sign up with someone else's address, and
    an unverified one must never receive what was meant for its real owner.
    """
    address = (
        # An account being deleted is gone for everyone else (ADR-016).
        EmailAddress.objects.filter(
            email__iexact=email.strip(), verified=True, user__deleted_at__isnull=True
        )
        .select_related("user")
        .first()
    )
    return address.user if address is not None else None
