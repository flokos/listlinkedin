import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.db import IntegrityError
from django.db.migrations.loader import MigrationLoader

from apps.accounts.models import User


def test_custom_user_is_created_by_the_first_accounts_migration():
    # Django requires the AUTH_USER_MODEL to be created in its app's first migration;
    # swapping it after auth tables exist is a manual, error-prone job (ADR-007).
    assert settings.AUTH_USER_MODEL == "accounts.User"
    assert get_user_model() is User

    loader = MigrationLoader(None, ignore_no_migrations=True)  # files only, no database
    first = loader.get_migration("accounts", "0001_initial")
    created = [op.name for op in first.operations if op.__class__.__name__ == "CreateModel"]
    assert created == ["User"]


@pytest.mark.django_db
def test_users_sign_in_with_a_lowercased_email_and_have_no_username():
    user = User.objects.create_user("Ada@Example.COM", "correct-horse-battery-42")

    assert user.email == "ada@example.com"
    assert user.check_password("correct-horse-battery-42")
    assert not user.is_staff and not user.is_superuser
    assert len(str(user.pk)) == 36  # UUID, like every other primary key
    with pytest.raises(FieldDoesNotExist):
        User._meta.get_field("username")


@pytest.mark.django_db
def test_email_addresses_are_unique_regardless_of_case():
    User.objects.create_user("ada@example.com", "pw-correct-horse-1")

    # Even a write that skips the manager's normalization is refused by the database.
    with pytest.raises(IntegrityError):
        User.objects.create(email="ADA@example.com")


@pytest.mark.django_db
def test_superusers_get_staff_and_superuser_flags():
    admin = User.objects.create_superuser("root@example.com", "pw-correct-horse-2")
    assert admin.is_staff and admin.is_superuser
