import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower

EMAIL_CI_CONSTRAINT = "accounts_user_email_ci_uniq"


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

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name=EMAIL_CI_CONSTRAINT),
        ]

    def __str__(self) -> str:
        return self.email
