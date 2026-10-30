"""Logs every authentication event (ASVS V16.3.1, docs/v2/21-SECURITY-REVIEW.md#logging).

Accounts appear by id only: never an email address, password or key (docs/v2/13-SECURITY.md).
A failed sign-in names nobody, since the address typed may belong to someone else; nginx's
log has the request (same request id) and the client address.
"""

import logging

from allauth.account.signals import (
    email_confirmed,
    password_changed,
    password_reset,
    user_signed_up,
)
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

logger = logging.getLogger("apps.accounts.auth")


def _id(user) -> str:
    return str(user.pk) if user is not None else "-"


@receiver(user_logged_in)
def signed_in(sender, request, user, **kwargs):
    logger.info("Signed in: user %s", _id(user))


@receiver(user_logged_out)
def signed_out(sender, request, user, **kwargs):
    logger.info("Signed out: user %s", _id(user))


@receiver(user_login_failed)
def sign_in_failed(sender, credentials, request=None, **kwargs):
    logger.warning("Sign-in failed")


@receiver(user_signed_up)
def signed_up(sender, request, user, **kwargs):
    logger.info("Signed up: user %s", _id(user))


@receiver(email_confirmed)
def email_verified(sender, request, email_address, **kwargs):
    logger.info("Email address verified: user %s", _id(email_address.user))


@receiver(password_changed)
def changed_password(sender, request, user, **kwargs):
    logger.info("Password changed: user %s", _id(user))


@receiver(password_reset)
def reset_password(sender, request, user, **kwargs):
    logger.info("Password reset: user %s", _id(user))
