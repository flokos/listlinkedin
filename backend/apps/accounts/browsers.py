"""Connected browsers: how the browser extension signs in (docs/v2/adr/ADR-020).

The user approves a browser on this site, which gives the page a one-time code. The extension
exchanges the code, together with the PKCE verifier only it knows, for a session token: the
token of an ordinary Django session (ADR-019) that lasts longer than a sign-in. So everything
that ends an account's sessions (a password change, deletion, suspension) ends these too.

These are the write operations; `selectors.connected_browsers` lists what is connected.
"""

import hashlib
import logging
import secrets
import smtplib
from base64 import urlsafe_b64encode
from datetime import datetime, timedelta
from importlib import import_module
from uuid import UUID

from allauth.headless import app_settings as headless_settings
from django.conf import settings
from django.contrib.auth import login
from django.contrib.sessions.backends.base import SessionBase, UpdateError
from django.contrib.sessions.models import Session
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from apps.common import errors

from . import selectors
from .models import ConnectedBrowser, User

logger = logging.getLogger(__name__)

# The page hands the code to the extension at once; two minutes cover a slow connection.
CODE_LIFETIME = timedelta(minutes=2)
# A connection ends when it wasn't used for this long, and at the latest this long after it
# was made (docs/v2/21-SECURITY-REVIEW.md#sessions).
IDLE_LIFETIME = timedelta(days=90)
MAX_LIFETIME = timedelta(days=365)
MAX_BROWSERS = 10
# In the session's data: which connection it belongs to, when it ends at the latest, and the
# day it was last seen (so `touch_browser` writes once a day, not on every request).
SESSION_MARK = "connected_browser"


class InvalidCode(errors.DomainError):
    """One answer for every way the exchange can fail, so it tells nothing about why."""

    code = "invalid_code"
    default_message = "This code isn't valid any more. Start again from the extension."


def challenge_for(verifier: str) -> str:
    """PKCE's S256 (RFC 7636): base64url(SHA-256(verifier)), without padding."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return urlsafe_b64encode(digest).rstrip(b"=").decode()


def _digest(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def approve_browser(user: User, *, name: str, challenge: str) -> str:
    """The signed-in user lets a browser connect. Returns the one-time code for the page to
    hand to the extension; only its hash is kept. The code is useless without the verifier
    behind `challenge`, which never leaves the extension that started this."""
    with transaction.atomic():
        locked = User.objects.select_for_update().get(pk=user.pk)  # one count at a time
        now = timezone.now()
        _drop_ended(locked, now)
        # Pending approvals count too: each one can become a connection.
        if ConnectedBrowser.objects.filter(user=locked).count() >= MAX_BROWSERS:
            raise errors.Conflict(
                f"You can connect at most {MAX_BROWSERS} browsers. Disconnect one first.",
                code="too_many_browsers",
            )
        code = secrets.token_urlsafe(32)
        browser = ConnectedBrowser.objects.create(
            user=locked,
            name=name,
            challenge=challenge,
            code_hash=_digest(code),
            code_expires_at=now + CODE_LIFETIME,
        )
    logger.info("Browser %s approved by user %s", browser.pk, locked.pk)
    return code


def connect_browser(*, code: str, verifier: str) -> tuple[ConnectedBrowser, str]:
    """Exchange an approval's code for a session token. Returns (browser, token).

    The code works once: the row is locked, and a second exchange finds it connected. The
    account must still be able to sign in (not deleted or suspended since the approval).
    """
    now = timezone.now()
    with transaction.atomic():
        browser = (
            ConnectedBrowser.objects.select_for_update(of=("self",))
            .select_related("user")
            .filter(code_hash=_digest(code))
            .first()
        )
        if (
            browser is None
            or browser.code_expires_at <= now
            or not constant_time_compare(challenge_for(verifier), browser.challenge)
            or not _can_sign_in(browser.user)
        ):
            raise InvalidCode()
        request = _signed_in_request(browser, now)
        browser.session_key = request.session.session_key
        browser.code_hash = browser.code_expires_at = None
        browser.challenge = ""
        browser.connected_at = browser.last_used_at = now
        browser.save(
            update_fields=[
                "session_key",
                "code_hash",
                "code_expires_at",
                "challenge",
                "connected_at",
                "last_used_at",
            ]
        )
        token = headless_settings.TOKEN_STRATEGY.create_session_token(request)
    logger.info("Browser %s connected for user %s", browser.pk, browser.user_id)
    _notify(browser)
    return browser, token


def _can_sign_in(user: User) -> bool:
    return user.is_active and user.deleted_at is None and user.suspended_at is None


def _signed_in_request(browser: ConnectedBrowser, now: datetime) -> HttpRequest:
    """A request carrying a new session signed in as the browser's user. allauth reads a
    token's session through such a request (core.internal.sessionkit); this makes one, with
    Django's own `login`, so the auth log and `last_login` record it like any sign-in."""
    request = HttpRequest()
    request.session = import_module(settings.SESSION_ENGINE).SessionStore()
    login(request, browser.user, backend=settings.AUTHENTICATION_BACKENDS[0])
    request.session[SESSION_MARK] = {
        "id": str(browser.pk),
        "until": (now + MAX_LIFETIME).isoformat(),
        "seen": now.date().isoformat(),
    }
    request.session.set_expiry(now + IDLE_LIFETIME)
    request.session.save()
    return request


def touch_browser(session: SessionBase) -> None:
    """Note that a connected browser was used: once a day, move its session's end to
    IDLE_LIFETIME from now (never past the connection's latest end) and record the time.
    Called for every request a session token authenticates; other sessions are left alone."""
    mark = session.get(SESSION_MARK)
    if not mark:
        return
    now = timezone.now()
    today = now.date().isoformat()
    if mark.get("seen") == today:
        return
    session[SESSION_MARK] = {**mark, "seen": today}
    session.set_expiry(min(now + IDLE_LIFETIME, datetime.fromisoformat(mark["until"])))
    try:
        session.save()
    except UpdateError:  # disconnected while this request was on its way
        return
    ConnectedBrowser.objects.filter(pk=mark["id"]).update(last_used_at=now)


@transaction.atomic
def disconnect_browser(user: User, browser_id: UUID) -> None:
    """End one of the account's connections: its token stops working at once."""
    browser = (
        ConnectedBrowser.objects.select_for_update()
        .filter(pk=browser_id, user=user, session_key__isnull=False)
        .first()
    )
    if browser is None:
        raise errors.NotVisible("This browser isn't connected.")
    Session.objects.filter(session_key=browser.session_key).delete()
    browser.delete()
    logger.info("Browser %s disconnected by user %s", browser_id, user.pk)


def disconnect_all(user: User) -> int:
    """End every connection of the account, pending approvals included. For whatever ends
    all of its sessions: deletion, suspension, a new password. Returns how many it ended."""
    browsers = ConnectedBrowser.objects.filter(user=user)
    keys = [key for key in browsers.values_list("session_key", flat=True) if key]
    Session.objects.filter(session_key__in=keys).delete()
    return browsers.delete()[0]


def _drop_ended(user: User, now: datetime) -> None:
    """Forget approvals nobody used and connections whose sessions no longer work."""
    ConnectedBrowser.objects.filter(user=user, code_expires_at__lte=now).delete()
    alive = [browser.pk for browser in selectors.connected_browsers(user)]
    ConnectedBrowser.objects.filter(user=user, session_key__isnull=False).exclude(
        pk__in=alive
    ).delete()


def _notify(browser: ConnectedBrowser) -> None:
    """Tell the account that a browser was connected, so a connection its owner didn't make
    doesn't go unnoticed. The connection stands even if the mail can't be sent."""
    account = f"{settings.PUBLIC_BASE_URL}/account"
    body = "\n".join(
        [
            "A browser was connected to your listlinkedin account:",
            "",
            f"  {browser.name}",
            "",
            "It stays signed in through the listlinkedin browser extension, and can do what",
            "you can do when you are signed in.",
            "",
            "If this was you, there is nothing to do.",
            "",
            "If it wasn't, disconnect it under “Connected browsers” and change your password:",
            f"  {account}",
            "",
        ]
    )
    subject = f"{settings.ACCOUNT_EMAIL_SUBJECT_PREFIX}A browser was connected to your account"
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [browser.user.email])
    except (smtplib.SMTPException, OSError) as exc:
        logger.error(
            "Connection notice for browser %s not sent: %s", browser.pk, type(exc).__name__
        )
