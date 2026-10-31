from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.sharing.models import SharedList
from apps.sharing.policy import Visibility
from apps.sharing.selectors import Principal
from apps.sharing.services import lists as list_services


@pytest.fixture(autouse=True)
def fast_password_hashing(settings):
    """Production hashing is slow on purpose; tests create many users."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Uploaded images go to a fresh directory per test, never to the real media volume."""
    settings.MEDIA_ROOT = str(tmp_path / "media")
    return tmp_path / "media"


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def owner(db) -> User:
    return User.objects.create_user("owner@example.com", "pw-correct-horse-1", display_name="Owner")


@pytest.fixture
def owner_client(owner) -> APIClient:
    client = APIClient()
    client.force_authenticate(owner)
    return client


def make_list(owner, title: str = "Team links", **fields) -> SharedList:
    """An account's list, unlisted unless `fields` say otherwise."""
    shared_list = list_services.create_list(Principal(user=owner), title=title)[0]
    SharedList.objects.filter(pk=shared_list.pk).update(
        **{"visibility": Visibility.UNLISTED.value, **fields}
    )
    shared_list.refresh_from_db()
    return shared_list


@pytest.fixture
def owned_list(owner) -> SharedList:
    """An unlisted list owned by `owner`: what V1's tests run on since the legacy (owner
    token) path was retired in task 9.6."""
    return make_list(owner)


@pytest.fixture
def expire():
    """Move a list's expiration into the past, as if 30 days had elapsed."""

    def _expire(shared_list: SharedList) -> None:
        SharedList.objects.filter(pk=shared_list.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

    return _expire
