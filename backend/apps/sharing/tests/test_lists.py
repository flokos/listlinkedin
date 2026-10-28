import uuid

import pytest
from rest_framework.throttling import ScopedRateThrottle

from apps.sharing import services
from apps.sharing.models import SharedList
from apps.sharing.tokens import hash_owner_token
from conftest import bearer

pytestmark = pytest.mark.django_db


def test_create_list_returns_identity_and_owner_token_once(api_client, settings):
    response = api_client.post("/api/v1/lists/", {"title": "Friday"}, format="json")

    assert response.status_code == 201
    body = response.json()
    shared_list = SharedList.objects.get(pk=body["id"])
    assert uuid.UUID(body["id"]).version == 4
    assert len(body["public_code"]) == 16
    assert body["public_url"] == f"{settings.PUBLIC_BASE_URL}/l/{body['public_code']}"
    # Only the digest is stored, never the plaintext token.
    assert shared_list.owner_token_hash == hash_owner_token(body["owner_token"])
    assert body["owner_token"] not in shared_list.owner_token_hash


def test_create_list_requires_title(api_client):
    assert api_client.post("/api/v1/lists/", {}, format="json").status_code == 400
    too_long = {"title": "x" * 256}
    assert api_client.post("/api/v1/lists/", too_long, format="json").status_code == 400


def test_create_list_ignores_client_supplied_identity(api_client):
    forged = {
        "title": "t",
        "id": str(uuid.uuid4()),
        "public_code": "AAAAAAAAAAAAAAAA",
        "expires_at": "2099-01-01T00:00:00Z",
    }
    body = api_client.post("/api/v1/lists/", forged, format="json").json()

    assert body["id"] != forged["id"]
    assert body["public_code"] != forged["public_code"]
    assert not body["expires_at"].startswith("2099")


def test_anonymous_read_never_exposes_secrets(api_client, owned_list):
    shared_list, _ = owned_list

    response = api_client.get(f"/api/v1/lists/{shared_list.public_code}/")

    assert response.status_code == 200
    assert response.json()["title"] == "Team links"
    assert "owner_token" not in response.json()
    assert "owner_token_hash" not in response.json()


def test_unknown_list_is_404(api_client, db):
    assert api_client.get("/api/v1/lists/doesnotexist0000/").status_code == 404


def test_update_requires_owner_token(api_client, owned_list):
    shared_list, _ = owned_list
    url = f"/api/v1/lists/{shared_list.public_code}/"

    assert api_client.patch(url, {"title": "x"}, format="json").status_code == 401
    wrong = api_client.patch(url, {"title": "x"}, format="json", **bearer("wrong-token"))
    assert wrong.status_code == 403
    shared_list.refresh_from_db()
    assert shared_list.title == "Team links"


def test_token_of_another_list_is_rejected(api_client, owned_list):
    shared_list, _ = owned_list
    _, other_token = services.create_list(title="Other")

    response = api_client.patch(
        f"/api/v1/lists/{shared_list.public_code}/",
        {"title": "hijack"},
        format="json",
        **bearer(other_token),
    )
    assert response.status_code == 403


def test_owner_can_update_title_but_not_immutable_fields(api_client, owned_list):
    shared_list, token = owned_list
    original = SharedList.objects.get(pk=shared_list.pk)

    response = api_client.patch(
        f"/api/v1/lists/{shared_list.public_code}/",
        {
            "title": "Renamed",
            "id": str(uuid.uuid4()),
            "public_code": "BBBBBBBBBBBBBBBB",
            "owner_token_hash": "0" * 64,
            "created_at": "2000-01-01T00:00:00Z",
            "expires_at": "2099-01-01T00:00:00Z",
        },
        format="json",
        **bearer(token),
    )

    assert response.status_code == 200
    updated = SharedList.objects.get(pk=shared_list.pk)
    assert updated.title == "Renamed"
    for field in ("public_code", "owner_token_hash", "created_at", "expires_at"):
        assert getattr(updated, field) == getattr(original, field)


def test_owner_can_delete_list(api_client, owned_list):
    shared_list, token = owned_list
    url = f"/api/v1/lists/{shared_list.public_code}/"

    assert api_client.delete(url).status_code == 401
    assert api_client.delete(url, **bearer(token)).status_code == 204
    assert not SharedList.objects.filter(pk=shared_list.pk).exists()
    assert api_client.get(url).status_code == 404
    # The token's hash was deleted with the list, so the token is now useless.
    assert not SharedList.objects.filter(owner_token_hash=hash_owner_token(token)).exists()
    stale = api_client.patch(url, {"title": "x"}, format="json", **bearer(token))
    assert stale.status_code == 404


def test_list_short_url_redirects_to_api_representation(api_client, owned_list):
    shared_list, _ = owned_list

    response = api_client.get(f"/l/{shared_list.public_code}")

    assert response.status_code == 302
    assert response["Location"] == f"/api/v1/lists/{shared_list.public_code}/"


def test_list_creation_is_rate_limited(api_client, monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"list_create": "2/hour"})

    statuses = [
        api_client.post("/api/v1/lists/", {"title": "t"}, format="json").status_code
        for _ in range(3)
    ]
    assert statuses == [201, 201, 429]


def test_oversized_request_body_is_rejected(api_client, settings):
    payload = {"title": "x" * (settings.DATA_UPLOAD_MAX_MEMORY_SIZE + 1)}
    assert api_client.post("/api/v1/lists/", payload, format="json").status_code == 413
