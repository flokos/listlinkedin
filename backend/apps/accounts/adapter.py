"""allauth's account adapter, refusing suspended accounts (docs/v2/13-SECURITY.md#moderation).

The backends (apps.accounts.backends) refuse them too, but allauth's sign-in deliberately
recovers a user its backend refused and then only checks `is_active`. Refusing here makes a
suspended account's sign-in answer exactly like a wrong password. Password sign-in is the
only way in: signing in on email confirmation, after a reset, or by code is off.
"""

from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    def authenticate(self, request, **credentials):
        user = super().authenticate(request, **credentials)
        if user is not None and getattr(user, "suspended_at", None) is not None:
            return None
        return user
