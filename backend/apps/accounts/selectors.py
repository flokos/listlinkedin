"""Reads on accounts that other apps may use. They get users through here, never by querying
the accounts tables themselves."""

from allauth.account.models import EmailAddress

from .models import User


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
