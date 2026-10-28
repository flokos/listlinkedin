"""Tests backing the claims in docs/security.md that are not covered elsewhere."""

import json
import logging
import os
import secrets
import subprocess
import sys
import threading
from datetime import timedelta
from io import StringIO

import pytest
from django.conf import settings
from django.core.cache import caches
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.management import call_command
from django.db import OperationalError, connection, connections
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.sharing import services
from apps.sharing.domain import normalize_destination_url
from apps.sharing.models import SharedLink, SharedList
from conftest import bearer

pytestmark = pytest.mark.django_db


def test_owner_token_and_hash_appear_only_in_creation_response(api_client):
    created = api_client.post("/api/v1/lists/", {"title": "t"}, format="json")
    token = created.json()["owner_token"]
    shared_list = SharedList.objects.get(pk=created.json()["id"])
    base = f"/api/v1/lists/{shared_list.public_code}/"
    owner = bearer(token)

    link = api_client.post(
        f"{base}links/", {"destination_url": "https://example.com"}, format="json", **owner
    )
    link_url = f"{base}links/{link.json()['id']}/"
    responses = [
        api_client.get(base),
        api_client.patch(base, {"title": "new"}, format="json", **owner),
        link,
        api_client.get(f"{base}links/"),
        api_client.patch(link_url, {"title": "x"}, format="json", **owner),
        api_client.patch(base, {"title": "x"}, format="json", **bearer("wrong")),  # error body
    ]

    for response in responses:
        body = response.content.decode()
        assert token not in body
        assert shared_list.owner_token_hash not in body
        assert "owner_token" not in body


def test_owner_token_is_never_logged(api_client, caplog):
    caplog.set_level(logging.DEBUG)
    token = api_client.post("/api/v1/lists/", {"title": "t"}, format="json").json()["owner_token"]
    code = SharedList.objects.get().public_code

    api_client.patch(f"/api/v1/lists/{code}/", {"title": "x"}, format="json", **bearer(token))
    api_client.patch(f"/api/v1/lists/{code}/", {"title": "x"}, format="json")  # 401 is logged
    api_client.patch(f"/api/v1/lists/{code}/", {"title": "x"}, format="json", **bearer(token + "x"))

    assert caplog.records  # requests were actually logged
    assert token not in caplog.text


def test_link_fields_cannot_be_mass_assigned(api_client, owned_list):
    shared_list, token = owned_list
    other_list, _ = services.create_list(title="Other")
    forged = {
        "destination_url": "https://example.com",
        "id": "00000000-0000-4000-8000-000000000000",
        "shared_list": str(other_list.pk),
        "short_url": "https://evil.example/r/x",
        "created_at": "2000-01-01T00:00:00Z",
    }
    base = f"/api/v1/lists/{shared_list.public_code}/links/"

    body = api_client.post(base, forged, format="json", **bearer(token)).json()
    api_client.patch(f"{base}{body['id']}/", forged, format="json", **bearer(token))

    link = SharedLink.objects.get(pk=body["id"])
    assert str(link.pk) != forged["id"]
    assert link.shared_list_id == shared_list.pk
    assert body["short_url"] != forged["short_url"]
    assert not body["created_at"].startswith("2000")


def test_owner_writes_are_throttled_but_reads_are_not(api_client, owned_list, monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"list_manage": "2/hour"})
    shared_list, token = owned_list
    url = f"/api/v1/lists/{shared_list.public_code}/"

    writes = [
        api_client.patch(url, {"title": "x"}, format="json", **bearer(token)).status_code
        for _ in range(3)
    ]
    reads = [api_client.get(url).status_code for _ in range(5)]

    assert writes == [200, 200, 429]
    assert set(reads) == {200}


def test_failed_token_attempts_are_throttled(api_client, owned_list, monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"list_manage": "2/hour"})
    shared_list, _ = owned_list
    url = f"/api/v1/lists/{shared_list.public_code}/"

    statuses = [
        api_client.patch(url, {"title": "x"}, format="json", **bearer(f"guess-{i}")).status_code
        for i in range(3)
    ]
    assert statuses == [403, 403, 429]


def test_spoofed_forwarded_for_does_not_bypass_rate_limit(api_client, monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"list_create": "1/hour"})

    first = api_client.post(
        "/api/v1/lists/", {"title": "t"}, format="json", HTTP_X_FORWARDED_FOR="1.1.1.1"
    )
    second = api_client.post(
        "/api/v1/lists/", {"title": "t"}, format="json", HTTP_X_FORWARDED_FOR="2.2.2.2"
    )

    assert (first.status_code, second.status_code) == (201, 429)


@pytest.mark.parametrize("code", ["%2F%2Fevil.example", "..%2F..%2Fx", "x?next=https://evil"])
def test_list_short_url_never_redirects_off_site(api_client, code):
    response = api_client.get(f"/l/{code}")
    if response.status_code == 302:
        assert response["Location"].startswith("/api/v1/lists/")
    else:
        assert response.status_code == 404


def test_openapi_marks_only_owner_operations_as_authenticated(api_client):
    schema = json.loads(api_client.get("/api/schema/", {"format": "json"}).content)
    operations = {
        (method.upper(), path): op
        for path, ops in schema["paths"].items()
        for method, op in ops.items()
    }

    for (method, path), op in operations.items():
        if path.startswith("/api/v2/"):
            continue  # session sign-in, checked in apps/accounts/tests/test_api.py
        is_owner_only = method in ("PATCH", "DELETE") or (
            method == "POST" and path != "/api/v1/lists/"
        )
        expected = [{"OwnerToken": []}] if is_owner_only else None
        assert op.get("security") == expected, (method, path)

    components = schema["components"]["schemas"]
    with_token = [n for n, s in components.items() if "owner_token" in s.get("properties", {})]
    assert sorted(with_token) == ["ListCreated", "OwnerToken"]  # creation + rotation only
    assert schema["components"]["securitySchemes"]["OwnerToken"]["scheme"] == "bearer"


def test_production_settings_pass_deploy_checks():
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.production",
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(50),
    }
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_rate_limit_counters_are_shared_across_processes(api_client, monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"list_create": "1/hour"})
    api_client.post("/api/v1/lists/", {"title": "t"}, format="json")

    # A brand-new cache connection, as another Gunicorn worker or instance would open.
    other_worker_cache = caches.create_connection("default")

    assert other_worker_cache.get("throttle_list_create_127.0.0.1")


def test_owner_can_rotate_token_and_old_one_is_revoked(api_client, owned_list):
    shared_list, old_token = owned_list
    url = f"/api/v1/lists/{shared_list.public_code}/"

    assert api_client.post(f"{url}rotate-token/").status_code == 401
    response = api_client.post(f"{url}rotate-token/", **bearer(old_token))

    assert response.status_code == 200
    new_token = response.json()["owner_token"]
    assert new_token != old_token
    stale = api_client.patch(url, {"title": "x"}, format="json", **bearer(old_token))
    fresh = api_client.patch(url, {"title": "x"}, format="json", **bearer(new_token))
    assert (stale.status_code, fresh.status_code) == (403, 200)


@pytest.mark.parametrize(
    "url",
    ["http://localhost:8000/r/AAAAAAAAAAAAAAAA", "http://LOCALHOST./l/x", "http://a.localhost/"],
)
def test_links_to_this_service_are_rejected(api_client, owned_list, url):
    # PUBLIC_BASE_URL is http://localhost:5173 in development: loops and chains are refused.
    shared_list, token = owned_list
    response = api_client.post(
        f"/api/v1/lists/{shared_list.public_code}/links/",
        {"destination_url": url},
        format="json",
        **bearer(token),
    )
    assert response.status_code == 400


def test_denylisted_hosts_are_rejected_and_disable_existing_links(api_client, owned_list, settings):
    shared_list, token = owned_list
    link = services.add_link(shared_list, destination_url="https://login.phish.example/x")
    short_path = f"/r/{link.redirects.get().code}"
    assert api_client.get(short_path).status_code == 302

    settings.BLOCKED_DESTINATION_HOSTS = ["phish.example"]

    assert api_client.get(short_path).status_code == 410
    response = api_client.post(
        f"/api/v1/lists/{shared_list.public_code}/links/",
        {"destination_url": "https://phish.example/other"},
        format="json",
        **bearer(token),
    )
    assert response.status_code == 400
    assert services.add_link(shared_list, destination_url="https://notphish.example/").pk


def test_capability_urls_are_not_leaked_or_indexed(api_client, owned_list):
    shared_list, _ = owned_list

    for path in (f"/api/v1/lists/{shared_list.public_code}/", f"/l/{shared_list.public_code}"):
        response = api_client.get(path)
        assert response["Referrer-Policy"] == "no-referrer"
        assert response["X-Robots-Tag"] == "noindex, nofollow"


@pytest.mark.django_db(transaction=True)
def test_concurrent_requests_cannot_exceed_rate_limit(monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"list_create": "5/hour"})
    statuses: list[int] = []
    barrier = threading.Barrier(20)

    def create() -> None:
        client = APIClient()
        barrier.wait()
        try:
            statuses.append(
                client.post("/api/v1/lists/", {"title": "t"}, format="json").status_code
            )
        finally:
            connection.close()

    threads = [threading.Thread(target=create) for _ in range(20)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        caches["default"].clear()  # the cache table is not flushed between transactional tests

    assert sorted(statuses) == [201] * 5 + [429] * 15
    assert SharedList.objects.count() == 5


def test_throttle_histories_are_not_culled_by_cache_size(db):
    cache = caches["default"]
    # Django culls the alphabetically-first keys, so this one would be among the first to go.
    # (Letters, not IPs: the database collation ignores dots when ordering keys.)
    survivor = "throttle_list_create_a"
    cache.set(survivor, [1.0], 3600)
    for i in range(400):  # more than Django's default MAX_ENTRIES (300)
        cache.set(f"throttle_list_create_z{i:03d}", [1.0], 3600)

    assert cache.get(survivor) == [1.0]


def test_write_with_authorization_from_before_a_rotation_is_rejected(owned_list):
    authorized_before, _ = owned_list  # what the view checked the old token against
    services.rotate_owner_token(SharedList.objects.get(pk=authorized_before.pk))

    with pytest.raises(PermissionDenied):
        services.update_list(authorized_before, title="stale write")
    with pytest.raises(PermissionDenied):
        services.add_link(authorized_before, destination_url="https://example.com/")

    assert SharedList.objects.get(pk=authorized_before.pk).title == "Team links"
    assert not SharedLink.objects.exists()


def test_unparseable_destination_is_a_400_not_a_500(api_client, owned_list):
    shared_list, token = owned_list
    response = api_client.post(
        f"/api/v1/lists/{shared_list.public_code}/links/",
        {"destination_url": "http://[::1"},
        format="json",
        **bearer(token),
    )
    assert response.status_code == 400
    assert "destination_url" in response.json()


def test_equivalent_urls_count_as_duplicates(api_client, owned_list):
    shared_list, token = owned_list
    statuses = [
        api_client.post(
            f"/api/v1/lists/{shared_list.public_code}/links/",
            {"destination_url": url},
            format="json",
            **bearer(token),
        ).status_code
        for url in ("https://example.com", "https://example.com/", "https://EXAMPLE.com:443/")
    ]
    assert statuses == [201, 400, 400]


@pytest.mark.parametrize("header", ["Bearer", "Bearer a b", "Basic dXNlcjpwYXNz", "garbage"])
def test_malformed_authorization_does_not_break_public_reads(api_client, owned_list, header):
    shared_list, _ = owned_list
    url = f"/api/v1/lists/{shared_list.public_code}/"

    assert api_client.get(url, HTTP_AUTHORIZATION=header).status_code == 200
    assert api_client.get(f"{url}links/", HTTP_AUTHORIZATION=header).status_code == 200
    write = api_client.patch(url, {"title": "x"}, format="json", HTTP_AUTHORIZATION=header)
    assert write.status_code == 401


def test_cleanup_prunes_expired_rate_limit_entries(monkeypatch):
    cache = caches["default"]
    cache.set("throttle_short", [1.0], 60)
    cache.set("throttle_long", [1.0], 3 * 3600)
    later = timezone.now() + timedelta(hours=2)
    monkeypatch.setattr(timezone, "now", lambda: later)

    out = StringIO()
    call_command("cleanup_expired", stdout=out)
    monkeypatch.undo()

    assert "Pruned 1 expired rate-limit entries." in out.getvalue()
    assert cache.get("throttle_short") is None  # row physically removed
    assert cache.get("throttle_long") == [1.0]


@pytest.mark.parametrize("base_url", ["go.example.com", "ftp://go.example.com", "https://"])
def test_invalid_public_base_url_refuses_to_start(base_url):
    result = subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=settings.BASE_DIR,
        env={**os.environ, "PUBLIC_BASE_URL": base_url},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "PUBLIC_BASE_URL must be an absolute http(s) URL" in result.stderr


def test_unicode_and_punycode_hosts_are_the_same_destination(api_client, owned_list):
    shared_list, token = owned_list
    statuses = [
        api_client.post(
            f"/api/v1/lists/{shared_list.public_code}/links/",
            {"destination_url": url},
            format="json",
            **bearer(token),
        ).status_code
        for url in ("https://bücher.example/", "https://xn--bcher-kva.example/")
    ]
    assert statuses == [201, 400]


@pytest.mark.parametrize(
    ("denylisted", "url"),
    [
        ("bücher.example", "https://xn--bcher-kva.example/"),
        ("xn--bcher-kva.example", "https://www.bücher.example/"),
    ],
)
def test_denylist_matches_both_host_spellings(settings, denylisted, url):
    settings.BLOCKED_DESTINATION_HOSTS = [denylisted]
    with pytest.raises(DjangoValidationError):
        normalize_destination_url(url)


def test_every_allowed_host_counts_as_this_service(settings):
    settings.ALLOWED_HOSTS = [".corp.example", "*"]  # "*" must not block everything

    for url in ("https://corp.example/r/x", "https://go.corp.example/l/x"):
        with pytest.raises(DjangoValidationError):
            normalize_destination_url(url)
    assert normalize_destination_url("https://example.org/") == "https://example.org/"


def test_short_urls_tolerate_a_trailing_slash(api_client, owned_list):
    shared_list, _ = owned_list
    link = services.add_link(shared_list, destination_url="https://example.com/a")
    code = link.redirects.get().code

    assert api_client.get(f"/r/{code}/")["Location"] == "https://example.com/a"
    assert api_client.get(f"/l/{shared_list.public_code}/").status_code == 302
    # Canonical URLs handed out by the API stay slash-less.
    body = api_client.get(f"/api/v1/lists/{shared_list.public_code}/").json()
    assert body["public_url"].endswith(f"/l/{shared_list.public_code}")


def test_healthz_reports_ok_for_any_host(api_client):
    response = api_client.get("/healthz", HTTP_HOST="not-an-allowed-host.example")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_reports_database_outage(api_client, monkeypatch):
    class BrokenConnection:
        def cursor(self):
            raise OperationalError("database is down")

    monkeypatch.setattr("config.middleware.connection", BrokenConnection())

    response = api_client.get("/healthz")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_healthz_bypasses_https_redirect_in_production():
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.production",
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(50),
        "DJANGO_ALLOWED_HOSTS": "go.example.com",
    }
    script = (
        "import django; django.setup()\n"
        "from django.test import Client\n"
        "c = Client()\n"
        "health = c.get('/healthz').status_code\n"
        "api = c.get('/api/v1/lists/x/', HTTP_HOST='go.example.com').status_code\n"
        "print(health, api)"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout.split() == ["200", "301"], result.stderr


def test_long_multibyte_url_is_a_400_not_a_500(api_client, owned_list):
    # ~7.9 KB of UTF-8 in under 2048 characters used to overflow the unique index.
    shared_list, token = owned_list
    response = api_client.post(
        f"/api/v1/lists/{shared_list.public_code}/links/",
        {"destination_url": "https://example.com/" + "😀" * 1900},
        format="json",
        **bearer(token),
    )
    assert response.status_code == 400
    assert "bytes" in response.json()["destination_url"][0]


def test_largest_allowed_multibyte_url_fits_the_index(api_client, owned_list):
    shared_list, token = owned_list
    url = "https://example.com/" + "😀" * ((2048 - len("https://example.com/")) // 4)
    response = api_client.post(
        f"/api/v1/lists/{shared_list.public_code}/links/",
        {"destination_url": url},
        format="json",
        **bearer(token),
    )
    assert response.status_code == 201


def test_ss_and_sharp_s_domains_stay_different(api_client, owned_list):
    shared_list, token = owned_list
    base = f"/api/v1/lists/{shared_list.public_code}/links/"
    owner = {"format": "json", **bearer(token)}
    sharp = api_client.post(base, {"destination_url": "https://faß.example/"}, **owner)
    plain = api_client.post(base, {"destination_url": "https://fass.example/"}, **owner)

    assert (sharp.status_code, plain.status_code) == (201, 201)  # two real domains
    code = SharedLink.objects.get(pk=sharp.json()["id"]).redirects.get().code
    assert api_client.get(f"/r/{code}")["Location"] == "https://xn--fa-hia.example/"


@pytest.mark.parametrize("bad_host", ["ü" * 70 + ".example", "a‍b.example"])
def test_invalid_denylist_entry_refuses_to_start(bad_host):
    result = subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=settings.BASE_DIR,
        env={**os.environ, "BLOCKED_DESTINATION_HOSTS": f"ok.example,{bad_host}"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "BLOCKED_DESTINATION_HOSTS" in result.stderr


def test_overlapping_cleanup_run_is_skipped(db):
    other_session = connections.create_connection("default")
    try:
        with other_session.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(hashtextextended('cleanup_expired', 0))")
        out = StringIO()
        call_command("cleanup_expired", stdout=out)
        assert out.getvalue().strip() == "Another cleanup run is in progress; skipping."
    finally:
        other_session.close()  # releases the session lock

    out = StringIO()
    call_command("cleanup_expired", stdout=out)
    assert "Deleted" in out.getvalue()


def test_empty_link_title_is_stored_as_null(api_client, owned_list):
    shared_list, token = owned_list
    response = api_client.post(
        f"/api/v1/lists/{shared_list.public_code}/links/",
        {"destination_url": "https://example.com/", "title": ""},
        format="json",
        **bearer(token),
    )
    assert response.json()["title"] is None
    assert SharedLink.objects.get(pk=response.json()["id"]).title is None
