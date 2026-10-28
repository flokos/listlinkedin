from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.sharing import services
from apps.sharing.models import SharedLink, SharedList
from apps.shortener.models import ShortRedirect
from conftest import bearer

pytestmark = pytest.mark.django_db


def test_list_expires_exactly_30_days_after_creation_in_utc(owned_list):
    shared_list, _ = owned_list

    assert shared_list.expires_at - shared_list.created_at == timedelta(days=30)
    assert shared_list.created_at.utcoffset() == timedelta(0)


def test_expiry_boundary_is_exact(owned_list, monkeypatch):
    shared_list, _ = owned_list
    expires_at = shared_list.expires_at

    monkeypatch.setattr(timezone, "now", lambda: expires_at - timedelta(microseconds=1))
    assert not shared_list.is_expired
    monkeypatch.setattr(timezone, "now", lambda: expires_at)
    assert shared_list.is_expired


def test_expiry_compares_aware_datetimes_across_timezones(owned_list, monkeypatch):
    shared_list, _ = owned_list
    # The same instant expressed in UTC+05:00.
    plus_five = timezone.get_fixed_timezone(300)
    monkeypatch.setattr(timezone, "now", lambda: shared_list.expires_at.astimezone(plus_five))
    assert shared_list.is_expired


def test_editing_contents_never_extends_expiration(api_client, owned_list):
    shared_list, token = owned_list
    original_expiry = shared_list.expires_at
    base = f"/api/v1/lists/{shared_list.public_code}/"

    api_client.patch(base, {"title": "New"}, format="json", **bearer(token))
    link = api_client.post(
        f"{base}links/", {"destination_url": "https://example.com"}, format="json", **bearer(token)
    ).json()
    api_client.delete(f"{base}links/{link['id']}/", **bearer(token))

    shared_list.refresh_from_db()
    assert shared_list.expires_at == original_expiry


def test_expired_list_is_inaccessible_before_cleanup(api_client, owned_list, expire):
    shared_list, token = owned_list
    link = services.add_link(shared_list, destination_url="https://example.com")
    expire(shared_list)
    base = f"/api/v1/lists/{shared_list.public_code}/"

    assert api_client.get(base).status_code == 410
    assert api_client.get(f"{base}links/").status_code == 410
    assert api_client.patch(base, {"title": "x"}, format="json", **bearer(token)).status_code == 410
    assert api_client.delete(base, **bearer(token)).status_code == 410
    assert api_client.delete(f"{base}links/{link.pk}/", **bearer(token)).status_code == 410
    assert SharedList.objects.filter(pk=shared_list.pk).exists()


def test_expiry_during_a_write_is_detected_under_lock(owned_list, monkeypatch):
    shared_list, _ = owned_list  # fetched while still active
    monkeypatch.setattr(timezone, "now", lambda: shared_list.expires_at + timedelta(seconds=1))

    with pytest.raises(Exception, match="expired"):
        services.add_link(shared_list, destination_url="https://example.com")
    assert not SharedLink.objects.exists()


def run_cleanup() -> str:
    out = StringIO()
    call_command("cleanup_expired", stdout=out)
    return out.getvalue()


def test_cleanup_deletes_expired_lists_and_cascades(expire):
    expired, _ = services.create_list(title="Old")
    services.add_link(expired, destination_url="https://example.com/1")
    services.add_link(expired, destination_url="https://example.com/2")
    active, _ = services.create_list(title="Fresh")
    services.add_link(active, destination_url="https://example.com/1")
    expire(expired)

    output = run_cleanup()

    assert "1 expired list(s), 2 link(s), 2 redirect(s)" in output
    assert list(SharedList.objects.values_list("pk", flat=True)) == [active.pk]
    assert SharedLink.objects.get().shared_list_id == active.pk
    assert ShortRedirect.objects.get().link.shared_list_id == active.pk


def test_cleanup_handles_multiple_batches(expire):
    for i in range(5):
        shared_list, _ = services.create_list(title=f"Old {i}")
        expire(shared_list)

    call_command("cleanup_expired", batch_size=2, stdout=StringIO())

    assert not SharedList.objects.exists()


def test_cleanup_is_idempotent(expire):
    shared_list, _ = services.create_list(title="Old")
    expire(shared_list)

    run_cleanup()
    second = run_cleanup()

    assert "Deleted 0 expired list(s)" in second


def test_cleanup_never_deletes_active_lists(owned_list):
    run_cleanup()
    assert SharedList.objects.filter(pk=owned_list[0].pk).exists()


def test_fixed_utc_timestamps_round_trip(monkeypatch):
    fixed = datetime(2026, 10, 27, 20, 0, tzinfo=UTC)
    monkeypatch.setattr(timezone, "now", lambda: fixed)

    shared_list, _ = services.create_list(title="t")
    shared_list.refresh_from_db()

    assert shared_list.created_at == fixed
    assert shared_list.expires_at == datetime(2026, 11, 26, 20, 0, tzinfo=UTC)
