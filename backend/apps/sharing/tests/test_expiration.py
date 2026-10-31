"""V1's expiry tests, kept for lists with an expiry date since the legacy path was retired
(task 9.6).

V1 lists expired 30 days after creation. V2 lists are permanent unless their owner sets an
expiry (docs/v2/06-MIGRATION-PLAN.md#expiration-policy); from that instant they answer 410
everywhere, before `cleanup_expired` deletes them, exactly as V1's did.
"""

from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.sharing.models import SharedLink, SharedList
from apps.sharing.selectors import Principal
from apps.sharing.services import links as link_services
from apps.shortener.models import ShortRedirect
from conftest import make_list

pytestmark = pytest.mark.django_db


def in_30_days() -> datetime:
    return timezone.now() + timedelta(days=30)


@pytest.fixture
def expiring_list(owner) -> SharedList:
    return make_list(owner, expires_at=in_30_days())


def add_link(owner, shared_list, url="https://example.com"):
    return link_services.add_link(Principal(user=owner), shared_list.pk, destination_url=url)[0]


def test_new_lists_are_permanent_and_expiry_is_stored_in_utc(owner_client, expiring_list):
    created = owner_client.post("/api/v2/lists/", {"title": "t"}, format="json").json()

    assert created["expires_at"] is None
    assert expiring_list.created_at.utcoffset() == timedelta(0)
    assert expiring_list.expires_at.utcoffset() == timedelta(0)


def test_expiry_boundary_is_exact(expiring_list, monkeypatch):
    expires_at = expiring_list.expires_at

    monkeypatch.setattr(timezone, "now", lambda: expires_at - timedelta(microseconds=1))
    assert not expiring_list.is_expired
    monkeypatch.setattr(timezone, "now", lambda: expires_at)
    assert expiring_list.is_expired


def test_expiry_compares_aware_datetimes_across_timezones(expiring_list, monkeypatch):
    # The same instant expressed in UTC+05:00.
    plus_five = timezone.get_fixed_timezone(300)
    monkeypatch.setattr(timezone, "now", lambda: expiring_list.expires_at.astimezone(plus_five))
    assert expiring_list.is_expired


def test_editing_contents_never_extends_expiration(owner_client, expiring_list):
    original_expiry = expiring_list.expires_at
    base = f"/api/v2/lists/{expiring_list.public_code}/"

    owner_client.patch(base, {"title": "New"}, format="json")
    link = owner_client.post(
        f"{base}links/", {"destination_url": "https://example.com"}, format="json"
    ).json()
    owner_client.delete(f"{base}links/{link['id']}/")

    expiring_list.refresh_from_db()
    assert expiring_list.expires_at == original_expiry


def test_expired_list_is_inaccessible_before_cleanup(
    api_client, owner, owner_client, expiring_list, expire
):
    link = add_link(owner, expiring_list)
    expire(expiring_list)
    base = f"/api/v2/lists/{expiring_list.public_code}/"

    assert api_client.get(base).status_code == 410
    assert api_client.get(f"{base}links/").status_code == 410
    assert owner_client.patch(base, {"title": "x"}, format="json").status_code == 410
    assert owner_client.delete(f"{base}links/{link.pk}/").status_code == 410
    assert SharedList.objects.filter(pk=expiring_list.pk).exists()


def test_expiry_during_a_write_is_detected_under_lock(owner, expiring_list, monkeypatch):
    # Fetched while still active, then the clock passes the expiry before the write.
    monkeypatch.setattr(timezone, "now", lambda: expiring_list.expires_at + timedelta(seconds=1))

    with pytest.raises(Exception, match="expired"):
        add_link(owner, expiring_list)
    assert not SharedLink.objects.exists()


def run_cleanup() -> str:
    out = StringIO()
    call_command("cleanup_expired", stdout=out)
    return out.getvalue()


def test_cleanup_deletes_expired_lists_and_cascades(owner, expire):
    expired = make_list(owner, title="Old", expires_at=in_30_days())
    add_link(owner, expired, "https://example.com/1")
    add_link(owner, expired, "https://example.com/2")
    active = make_list(owner, title="Fresh")
    add_link(owner, active, "https://example.com/1")
    expire(expired)

    output = run_cleanup()

    assert "1 expired list(s), 2 link(s), 2 redirect(s)" in output
    assert list(SharedList.objects.values_list("pk", flat=True)) == [active.pk]
    assert SharedLink.objects.get().shared_list_id == active.pk
    assert ShortRedirect.objects.get().link.shared_list_id == active.pk


def test_cleanup_handles_multiple_batches(owner, expire):
    for i in range(5):
        expire(make_list(owner, title=f"Old {i}", expires_at=in_30_days()))

    call_command("cleanup_expired", batch_size=2, stdout=StringIO())

    assert not SharedList.objects.exists()


def test_cleanup_is_idempotent(owner, expire):
    expire(make_list(owner, title="Old", expires_at=in_30_days()))

    run_cleanup()
    second = run_cleanup()

    assert "Deleted 0 expired list(s)" in second


def test_cleanup_never_deletes_active_or_permanent_lists(owned_list, expiring_list):
    run_cleanup()
    assert SharedList.objects.filter(pk__in=[owned_list.pk, expiring_list.pk]).count() == 2


def test_expiry_given_with_an_offset_is_stored_as_the_same_utc_instant(owner_client):
    created = owner_client.post(
        "/api/v2/lists/",
        {"title": "t", "expires_at": "2026-11-26T22:00:00+02:00"},
        format="json",
    ).json()
    shared_list = SharedList.objects.get(public_code=created["code"])

    assert shared_list.expires_at == datetime(2026, 11, 26, 20, 0, tzinfo=UTC)
