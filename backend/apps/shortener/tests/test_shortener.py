import re

import pytest
from django.db import IntegrityError, transaction

from apps.sharing import services as sharing_services
from apps.sharing.models import SharedList
from apps.shortener import generators
from apps.shortener import services as shortener_services
from apps.shortener.models import ShortRedirect


def test_generated_codes_are_16_char_base64url():
    codes = {generators.generate_short_code() for _ in range(1000)}

    assert len(codes) == 1000
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{16}", code) for code in codes)


@pytest.fixture
def link(owned_list):
    shared_list, _ = owned_list
    return sharing_services.add_link(shared_list, destination_url="https://example.com/a")


def short_path(link) -> str:
    return f"/r/{ShortRedirect.objects.get(link=link).code}"


@pytest.mark.django_db
def test_valid_code_redirects_with_302_and_safe_headers(api_client, link):
    response = api_client.get(short_path(link))

    assert response.status_code == 302
    assert response["Location"] == "https://example.com/a"
    assert response["Cache-Control"] == "no-store"
    assert response["Referrer-Policy"] == "no-referrer"


@pytest.mark.django_db
def test_unknown_code_is_404(api_client):
    assert api_client.get("/r/AAAAAAAAAAAAAAAA").status_code == 404


@pytest.mark.django_db
def test_expired_list_makes_redirect_410(api_client, link, expire):
    path = short_path(link)
    expire(link.shared_list)
    assert api_client.get(path).status_code == 410


@pytest.mark.django_db
def test_inactive_redirect_is_rejected(api_client, link):
    ShortRedirect.objects.filter(link=link).update(is_active=False)
    assert api_client.get(short_path(link)).status_code == 410


@pytest.mark.django_db
def test_deleted_link_stops_redirecting(api_client, link):
    path = short_path(link)

    sharing_services.delete_link(link.shared_list, link.pk)

    assert api_client.get(path).status_code == 404
    # V2 keeps the code with the tombstone (V1 deleted it), so a restore can revive it.
    assert ShortRedirect.objects.filter(link=link).exists()


@pytest.mark.django_db
def test_destination_change_preserves_code(api_client, link):
    path = short_path(link)

    sharing_services.update_link(
        link.shared_list, link.pk, destination_url="https://example.com/new"
    )

    assert short_path(link) == path
    assert api_client.get(path)["Location"] == "https://example.com/new"


@pytest.mark.django_db
def test_database_enforces_code_uniqueness(link):
    existing = ShortRedirect.objects.get(link=link).code
    with pytest.raises(IntegrityError), transaction.atomic():
        ShortRedirect.objects.create(code=existing, link=link)
    other_list, _ = sharing_services.create_list(title="Other")
    with pytest.raises(IntegrityError), transaction.atomic():
        SharedList.objects.filter(pk=other_list.pk).update(public_code=link.shared_list.public_code)


@pytest.mark.django_db
def test_redirect_code_collision_is_retried(link, monkeypatch):
    taken = ShortRedirect.objects.get(link=link).code
    codes = iter([taken, taken, "FreshCode0000000"])
    monkeypatch.setattr(generators, "generate_short_code", lambda: next(codes))

    other = sharing_services.add_link(link.shared_list, destination_url="https://example.com/b")

    assert ShortRedirect.objects.get(link=other).code == "FreshCode0000000"


@pytest.mark.django_db
def test_list_code_collision_is_retried(owned_list, monkeypatch):
    shared_list, _ = owned_list
    codes = iter([shared_list.public_code, "AnotherCode00000"])
    monkeypatch.setattr(generators, "generate_short_code", lambda: next(codes))

    new_list, _ = sharing_services.create_list(title="Second")

    assert new_list.public_code == "AnotherCode00000"


@pytest.mark.django_db
def test_persistent_collisions_give_up_after_bounded_attempts(link, monkeypatch):
    taken = ShortRedirect.objects.get(link=link).code
    monkeypatch.setattr(generators, "generate_short_code", lambda: taken)

    with pytest.raises(RuntimeError):
        shortener_services.create_redirect(link)
    assert ShortRedirect.objects.count() == 1
