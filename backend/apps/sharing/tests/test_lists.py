"""V1's list tests, kept against /api/v2/ since the legacy path was retired (task 9.6).

V1 created lists anonymously and managed them with an owner token. Both are gone: the same
rules (identity the client can't choose, title limits, who may change or delete a list,
secrets never exposed, rate limits) now hold for account-owned lists. The tests of the owner
token itself are replaced by acceptance tests that the V1 API and bearer tokens are gone
(docs/v2/15-TEST-STRATEGY.md#v1-regression-checklist).
"""

import uuid

import pytest
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import User
from apps.sharing.models import SharedList
from conftest import make_list

pytestmark = pytest.mark.django_db

URL = "/api/v2/lists/"


def test_create_list_returns_its_identity(owner_client, settings):
    response = owner_client.post(URL, {"title": "Friday"}, format="json")

    assert response.status_code == 201
    body = response.json()
    shared_list = SharedList.objects.get(public_code=body["code"])
    assert uuid.UUID(body["id"]).version == 4
    assert str(shared_list.pk) == body["id"]
    assert len(body["code"]) == 16
    assert body["url"] == f"{settings.PUBLIC_BASE_URL}/l/{body['code']}/friday"
    assert "owner_token" not in body


def test_create_list_requires_title(owner_client):
    assert owner_client.post(URL, {}, format="json").status_code == 400
    too_long = {"title": "x" * 256}
    assert owner_client.post(URL, too_long, format="json").status_code == 400


def test_create_list_ignores_client_supplied_identity(owner_client):
    forged = {
        "title": "t",
        "id": str(uuid.uuid4()),
        "code": "AAAAAAAAAAAAAAAA",
        "public_code": "AAAAAAAAAAAAAAAA",
        "created_at": "2000-01-01T00:00:00Z",
    }
    body = owner_client.post(URL, forged, format="json").json()

    assert body["id"] != forged["id"]
    assert body["code"] != forged["code"]
    assert not body["created_at"].startswith("2000")


def test_anonymous_read_never_exposes_secrets(api_client, owned_list, owner):
    response = api_client.get(f"{URL}{owned_list.public_code}/")

    assert response.status_code == 200
    assert response.json()["title"] == "Team links"
    assert owner.email not in response.content.decode()
    assert "owner_token" not in response.json()


def test_unknown_list_is_404(api_client, db):
    assert api_client.get(f"{URL}doesnotexist0000/").status_code == 404


def test_update_requires_the_owner(api_client, owned_list):
    url = f"{URL}{owned_list.public_code}/"
    stranger = APIClient()
    stranger.force_authenticate(User.objects.create_user("eve@example.com", "pw-correct-horse-9"))

    assert api_client.patch(url, {"title": "x"}, format="json").status_code == 401
    assert stranger.patch(url, {"title": "x"}, format="json").status_code == 403
    owned_list.refresh_from_db()
    assert owned_list.title == "Team links"


def test_owning_one_list_grants_nothing_on_another(owned_list):
    other_owner = User.objects.create_user("other@example.com", "pw-correct-horse-8")
    make_list(other_owner, title="Other")
    client = APIClient()
    client.force_authenticate(other_owner)

    response = client.patch(f"{URL}{owned_list.public_code}/", {"title": "hijack"}, format="json")
    assert response.status_code == 403


def test_owner_can_update_title_but_not_immutable_fields(owner_client, owned_list):
    original = SharedList.objects.get(pk=owned_list.pk)

    response = owner_client.patch(
        f"{URL}{owned_list.public_code}/",
        {
            "title": "Renamed",
            "id": str(uuid.uuid4()),
            "code": "BBBBBBBBBBBBBBBB",
            "public_code": "BBBBBBBBBBBBBBBB",
            "owner": None,
            "created_at": "2000-01-01T00:00:00Z",
        },
        format="json",
    )

    assert response.status_code == 200
    updated = SharedList.objects.get(pk=owned_list.pk)
    assert updated.title == "Renamed"
    for field in ("id", "public_code", "owner_id", "created_at"):
        assert getattr(updated, field) == getattr(original, field)


def test_owner_can_delete_list(api_client, owner_client, owned_list):
    url = f"{URL}{owned_list.public_code}/"

    assert api_client.delete(url).status_code == 401
    assert owner_client.delete(url).status_code == 204
    assert not SharedList.objects.filter(pk=owned_list.pk).exists()
    assert api_client.get(url).status_code == 404
    assert owner_client.patch(url, {"title": "x"}, format="json").status_code == 404


def test_list_short_url_redirects_to_api_representation(api_client, owned_list):
    response = api_client.get(f"/l/{owned_list.public_code}")

    assert response.status_code == 302
    assert response["Location"] == f"{URL}{owned_list.public_code}/"


def test_list_creation_is_rate_limited(owner_client, monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"list_create": "2/hour"})

    statuses = [owner_client.post(URL, {"title": "t"}, format="json").status_code for _ in range(3)]
    assert statuses == [201, 201, 429]


def test_oversized_request_body_is_rejected(owner_client, settings):
    payload = {"title": "x" * (settings.DATA_UPLOAD_MAX_MEMORY_SIZE + 1)}
    assert owner_client.post(URL, payload, format="json").status_code == 413


# Acceptance: the legacy path is gone (task 9.6). V1 created lists anonymously and returned an
# owner token; that token managed the list through /api/v1/ and /api/v2/.


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/v1/lists/"),
        ("get", "/api/v1/lists/{code}/"),
        ("patch", "/api/v1/lists/{code}/"),
        ("delete", "/api/v1/lists/{code}/"),
        ("get", "/api/v1/lists/{code}/links/"),
        ("post", "/api/v1/lists/{code}/rotate-token/"),
        ("post", "/api/v2/lists/{code}/rotate-token/"),
        ("post", "/api/v2/lists/{code}/claim/"),
    ],
)
def test_the_v1_api_and_the_token_endpoints_are_gone(api_client, owned_list, method, path):
    response = getattr(api_client, method)(path.format(code=owned_list.public_code))
    assert response.status_code == 404


def test_a_bearer_token_grants_nothing(api_client, owned_list):
    url = f"{URL}{owned_list.public_code}/"
    headers = {"HTTP_AUTHORIZATION": "Bearer some-old-owner-token"}

    assert api_client.patch(url, {"title": "x"}, format="json", **headers).status_code == 401
    assert api_client.delete(url, **headers).status_code == 401
    assert api_client.post(URL, {"title": "x"}, format="json", **headers).status_code == 401
    assert SharedList.objects.filter(pk=owned_list.pk, title="Team links").exists()


def test_every_list_has_an_owner_account(owner):
    """CHECK L2 is now NOT NULL on the owner (docs/v2/05-DATABASE-DESIGN.md)."""
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError), transaction.atomic():
        SharedList.objects.create(public_code="NoOwnerList00000", title="x")
