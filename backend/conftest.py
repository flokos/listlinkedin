from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.sharing import services
from apps.sharing.models import SharedList


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def owned_list(db):
    """A freshly created list and its plaintext owner token."""
    return services.create_list(title="Team links")


@pytest.fixture
def expire():
    """Move a list's expiration into the past, as if 30 days had elapsed."""

    def _expire(shared_list: SharedList) -> None:
        SharedList.objects.filter(pk=shared_list.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

    return _expire


def bearer(token: str) -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}
