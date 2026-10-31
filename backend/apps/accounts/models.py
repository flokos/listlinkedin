import uuid
from datetime import datetime, timedelta

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils.crypto import salted_hmac

EMAIL_CI_CONSTRAINT = "accounts_user_email_ci_uniq"

# Deleting an account takes effect at once for everyone else, but the data is only erased
# after this grace period, during which signing in can restore it (docs/v2/adr/ADR-016).
DELETION_GRACE = timedelta(days=30)
SESSION_HASH_SALT = "django.contrib.auth.models.AbstractBaseUser.get_session_auth_hash"


class UserManager(BaseUserManager):
    """Users sign in with their email address; there is no username."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.update(is_staff=True, is_superuser=True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """An account. It signs in with its email address; `display_name` is what others see.

    This is AUTH_USER_MODEL from the first auth migration on, so it never has to be swapped
    later (docs/v2/adr/ADR-007). Other apps refer to users by id only.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    # Stored lowercased by the manager and by allauth, so `unique` is effectively
    # case-insensitive; the functional constraint below also covers other write paths.
    email = models.EmailField("email address", unique=True)
    display_name = models.CharField(max_length=80, blank=True)
    # Set when the user deletes the account. Until DELETION_GRACE has passed it can be
    # restored; then `purge_deleted_accounts` erases the personal data and keeps an anonymous
    # row (is_active False), so the revisions it wrote still have an author to point to.
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    # When every session of the account was last ended (deleting the account does this).
    # Part of the session hash, and never cleared: restoring doesn't revive old sessions.
    sessions_revoked_at = models.DateTimeField(null=True, blank=True, editable=False)
    # Set by the operator (`suspend_account`): the account can't sign in, and its sessions
    # have ended. Its lists and groups stay unless the operator unpublishes them too.
    # Separate from is_active, which marks an erased account (purge_account).
    suspended_at = models.DateTimeField(null=True, blank=True, editable=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name=EMAIL_CI_CONSTRAINT),
        ]

    def __str__(self) -> str:
        return self.email

    @property
    def deletion_scheduled_for(self) -> datetime | None:
        """When the account's data will be erased, or None if it isn't being deleted."""
        return self.deleted_at + DELETION_GRACE if self.deleted_at else None

    def _get_session_auth_hash(self, secret=None):
        """Sessions are bound to the password (Django's default) and, once all of them have
        been ended, to that time: deleting the account signs out every device at once.
        Accounts whose sessions were never revoked keep Django's value."""
        if self.sessions_revoked_at is None:
            return super()._get_session_auth_hash(secret)
        value = f"{self.password}|revoked:{self.sessions_revoked_at.isoformat()}"
        return salted_hmac(SESSION_HASH_SALT, value, secret=secret, algorithm="sha256").hexdigest()
