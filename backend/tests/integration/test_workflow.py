"""End-to-end workflow against PostgreSQL through the public HTTP API. V1's lifecycle, run as
an account since the legacy path was retired (task 9.6)."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.sharing.models import SharedLink, SharedList
from apps.shortener.models import ShortRedirect


@pytest.mark.django_db
def test_complete_list_lifecycle(api_client, owner_client, expire, settings):
    # Create a list, unlisted so anyone with its address can read it.
    created = owner_client.post(
        "/api/v2/lists/", {"title": "Friday", "visibility": "unlisted"}, format="json"
    ).json()
    code = created["code"]
    base = f"/api/v2/lists/{code}/"

    # Add links.
    first = owner_client.post(
        f"{base}links/",
        {"title": "One", "destination_url": "https://example.com/1"},
        format="json",
    ).json()
    owner_client.post(f"{base}links/", {"destination_url": "https://example.com/2"}, format="json")

    # Retrieve anonymously; identity unchanged.
    listed = api_client.get(base).json()
    assert (listed["id"], listed["code"]) == (created["id"], code)
    links = api_client.get(f"{base}links/").json()
    assert links["count"] == 2

    # Resolve the short URL.
    short_path = first["short_url"].removeprefix(settings.PUBLIC_BASE_URL)
    assert api_client.get(short_path)["Location"] == "https://example.com/1"

    # Update destination; the short URL stays the same and follows the new destination.
    updated = owner_client.patch(
        f"{base}links/{first['id']}/",
        {"destination_url": "https://example.com/new"},
        format="json",
    ).json()
    assert updated["short_url"] == first["short_url"]
    assert api_client.get(short_path)["Location"] == "https://example.com/new"

    # Delete the link; its short URL stops working.
    assert owner_client.delete(f"{base}links/{first['id']}/").status_code == 204
    assert api_client.get(short_path).status_code == 404

    # List identity is still unchanged after all edits.
    assert api_client.get(base).json()["id"] == created["id"]

    # Expire the list -> 410 everywhere, before any cleanup.
    expire(SharedList.objects.get(public_code=code))
    assert api_client.get(base).status_code == 410
    assert api_client.get(f"{base}links/").status_code == 410

    # Cleanup physically deletes everything; afterwards the list is 404.
    call_command("cleanup_expired", stdout=StringIO())
    assert not SharedList.objects.exists()
    assert not SharedLink.objects.exists()
    assert not ShortRedirect.objects.exists()
    assert api_client.get(base).status_code == 404
