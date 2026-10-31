"""Tests backing the claims in docs/v1/security.md (V1's threat model) that still hold, and
docs/v2/13-SECURITY.md, not covered elsewhere.

Since the legacy path was retired (task 9.6) they run against /api/v2/ with account-owned
lists. V1's owner-token tests (the token shown once, never logged, rotated, checked under the
lock) are replaced by their account equivalents and by acceptance tests that no token
mechanism is left (docs/v2/15-TEST-STRATEGY.md#v1-regression-checklist).
"""

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
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import User
from apps.common import errors
from apps.sharing.domain import normalize_destination_url
from apps.sharing.models import ListMembership, SharedLink, SharedList
from apps.sharing.selectors import Principal
from apps.sharing.services import links as link_services
from apps.sharing.services import lists as list_services
from conftest import make_list

pytestmark = pytest.mark.django_db

DIRECTORY = "/api/v2/directory/lists/"  # anonymous and throttled per client IP


def links_url(shared_list) -> str:
    return f"/api/v2/lists/{shared_list.public_code}/links/"


def post_link(client, target_list, url: str, **data):
    return client.post(links_url(target_list), {"destination_url": url, **data}, format="json")


def stranger() -> APIClient:
    client = APIClient()
    client.force_authenticate(User.objects.create_user("eve@example.com", "pw-correct-horse-9"))
    return client


def test_no_response_exposes_the_owners_address(api_client, owner, owner_client, owned_list):
    base = f"/api/v2/lists/{owned_list.public_code}/"
    link = post_link(owner_client, owned_list, "https://example.com")
    responses = [
        api_client.get(base),
        owner_client.get(base),
        owner_client.patch(base, {"title": "new"}, format="json"),
        link,
        api_client.get(f"{base}links/"),
        owner_client.patch(f"{base}links/{link.json()['id']}/", {"title": "x"}, format="json"),
        stranger().patch(base, {"title": "x"}, format="json"),  # an error body
    ]

    for response in responses:
        body = response.content.decode()
        assert owner.email not in body
        assert "owner_token" not in body


def test_authorization_headers_are_never_logged(api_client, owned_list, caplog):
    caplog.set_level(logging.DEBUG)
    secret = "an-old-owner-token-" + secrets.token_urlsafe(16)
    url = f"/api/v2/lists/{owned_list.public_code}/"

    api_client.patch(url, {"title": "x"}, format="json", HTTP_AUTHORIZATION=f"Bearer {secret}")
    api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {secret}")

    assert caplog.records  # requests were actually logged
    assert secret not in caplog.text


def test_link_fields_cannot_be_mass_assigned(owner, owner_client, owned_list):
    other_list = make_list(owner, title="Other")
    forged = {
        "id": "00000000-0000-4000-8000-000000000000",
        "shared_list": str(other_list.pk),
        "short_url": "https://evil.example/r/x",
        "created_at": "2000-01-01T00:00:00Z",
    }

    body = post_link(owner_client, owned_list, "https://example.com", **forged).json()
    owner_client.patch(f"{links_url(owned_list)}{body['id']}/", forged, format="json")

    link = SharedLink.objects.get(pk=body["id"])
    assert str(link.pk) != forged["id"]
    assert link.shared_list_id == owned_list.pk
    assert body["short_url"] != forged["short_url"]
    assert not body["created_at"].startswith("2000")


def test_owner_writes_are_throttled_but_reads_are_not(
    api_client, owner_client, owned_list, monkeypatch
):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"list_manage": "2/hour"})
    url = f"/api/v2/lists/{owned_list.public_code}/"

    writes = [owner_client.patch(url, {"title": "x"}, format="json").status_code for _ in range(3)]
    reads = [api_client.get(url).status_code for _ in range(5)]

    assert writes == [200, 200, 429]
    assert set(reads) == {200}


def test_refused_write_attempts_are_throttled(owned_list, monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"list_manage": "2/hour"})
    url = f"/api/v2/lists/{owned_list.public_code}/"
    client = stranger()

    statuses = [client.patch(url, {"title": "x"}, format="json").status_code for _ in range(3)]
    assert statuses == [403, 403, 429]


def test_spoofed_forwarded_for_does_not_bypass_rate_limit(api_client, monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"directory": "1/hour"})

    first = api_client.get(DIRECTORY, HTTP_X_FORWARDED_FOR="1.1.1.1")
    second = api_client.get(DIRECTORY, HTTP_X_FORWARDED_FOR="2.2.2.2")

    assert (first.status_code, second.status_code) == (200, 429)


@pytest.mark.parametrize("code", ["%2F%2Fevil.example", "..%2F..%2Fx", "x?next=https://evil"])
def test_list_short_url_never_redirects_off_site(api_client, code):
    response = api_client.get(f"/l/{code}")
    if response.status_code == 302:
        assert response["Location"].startswith("/api/v2/lists/")
    else:
        assert response.status_code == 404


def test_openapi_declares_no_token_scheme_or_v1_paths(api_client):
    schema = json.loads(api_client.get("/api/schema/", {"format": "json"}).content)

    assert not [path for path in schema["paths"] if path.startswith("/api/v1/")]
    assert set(schema["components"]["securitySchemes"]) == {"SessionCookie"}
    components = schema["components"]["schemas"]
    assert not [n for n, s in components.items() if "owner_token" in s.get("properties", {})]


def test_rate_limit_counters_are_shared_across_processes(api_client, monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"directory": "1/hour"})
    api_client.get(DIRECTORY)

    # A brand-new cache connection, as another Gunicorn worker or instance would open.
    other_worker_cache = caches.create_connection("default")

    assert other_worker_cache.get("throttle_directory_127.0.0.1")


@pytest.mark.parametrize(
    "url",
    ["http://localhost:8000/r/AAAAAAAAAAAAAAAA", "http://LOCALHOST./l/x", "http://a.localhost/"],
)
def test_links_to_this_service_are_rejected(owner_client, owned_list, url):
    # PUBLIC_BASE_URL is http://localhost:5173 in development: loops and chains are refused.
    assert post_link(owner_client, owned_list, url).status_code == 400


def test_denylisted_hosts_are_rejected_and_disable_existing_links(
    api_client, owner, owner_client, owned_list, settings
):
    link = link_services.add_link(
        Principal(user=owner), owned_list.pk, destination_url="https://login.phish.example/x"
    )[0]
    short_path = f"/r/{link.redirects.get().code}"
    assert api_client.get(short_path).status_code == 302

    settings.BLOCKED_DESTINATION_HOSTS = ["phish.example"]

    assert api_client.get(short_path).status_code == 410
    assert post_link(owner_client, owned_list, "https://phish.example/other").status_code == 400
    assert post_link(owner_client, owned_list, "https://notphish.example/").status_code == 201


def test_capability_urls_are_not_leaked_or_indexed(api_client, owned_list):
    for path in (f"/api/v2/lists/{owned_list.public_code}/", f"/l/{owned_list.public_code}"):
        response = api_client.get(path)
        assert response["Referrer-Policy"] == "no-referrer"
        assert response["X-Robots-Tag"] == "noindex, nofollow"


@pytest.mark.django_db(transaction=True)
def test_concurrent_requests_cannot_exceed_rate_limit(monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"directory": "5/hour"})
    statuses: list[int] = []
    barrier = threading.Barrier(20)

    def search() -> None:
        client = APIClient()
        barrier.wait()
        try:
            statuses.append(client.get(DIRECTORY).status_code)
        finally:
            connection.close()

    threads = [threading.Thread(target=search) for _ in range(20)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        caches["default"].clear()  # the cache table is not flushed between transactional tests

    assert sorted(statuses) == [200] * 5 + [429] * 15


def test_write_authorized_before_a_removal_is_rejected_under_the_lock(owner, owned_list):
    """V1 checked a rotated token again under the list's lock; V2 does the same for a
    removed editor (docs/v2/12-AUTHORIZATION.md)."""
    editor = User.objects.create_user("ed@example.com", "pw-correct-horse-3")
    membership = ListMembership.objects.create(shared_list=owned_list, user=editor, role="editor")
    authorized_before = Principal(user=editor)  # what the view had checked
    membership.delete()

    with pytest.raises(errors.Forbidden):
        list_services.update_list(authorized_before, owned_list.pk, changes={"title": "stale"})
    with pytest.raises(errors.Forbidden):
        link_services.add_link(authorized_before, owned_list.pk, destination_url="https://e.com/")

    assert SharedList.objects.get(pk=owned_list.pk).title == "Team links"
    assert not SharedLink.objects.exists()


def test_unparseable_destination_is_a_400_not_a_500(owner_client, owned_list):
    response = post_link(owner_client, owned_list, "http://[::1")
    assert response.status_code == 400
    assert "destination_url" in response.json()


def test_equivalent_urls_count_as_duplicates(owner_client, owned_list):
    statuses = [
        post_link(owner_client, owned_list, url).status_code
        for url in ("https://example.com", "https://example.com/", "https://EXAMPLE.com:443/")
    ]
    assert statuses == [201, 400, 400]


@pytest.mark.parametrize("header", ["Bearer", "Bearer a b", "Basic dXNlcjpwYXNz", "garbage"])
def test_malformed_authorization_does_not_break_public_reads(api_client, owned_list, header):
    url = f"/api/v2/lists/{owned_list.public_code}/"

    assert api_client.get(url, HTTP_AUTHORIZATION=header).status_code == 200
    assert api_client.get(f"{url}links/", HTTP_AUTHORIZATION=header).status_code == 200
    write = api_client.patch(url, {"title": "x"}, format="json", HTTP_AUTHORIZATION=header)
    assert write.status_code == 401


def test_unicode_and_punycode_hosts_are_the_same_destination(owner_client, owned_list):
    statuses = [
        post_link(owner_client, owned_list, url).status_code
        for url in ("https://bücher.example/", "https://xn--bcher-kva.example/")
    ]
    assert statuses == [201, 400]


def test_short_urls_tolerate_a_trailing_slash(api_client, owner, owned_list):
    link = link_services.add_link(
        Principal(user=owner), owned_list.pk, destination_url="https://example.com/a"
    )[0]
    code = link.redirects.get().code

    assert api_client.get(f"/r/{code}/")["Location"] == "https://example.com/a"
    assert api_client.get(f"/l/{owned_list.public_code}/").status_code == 302
    # Canonical URLs handed out by the API carry no trailing slash.
    body = api_client.get(f"/api/v2/lists/{owned_list.public_code}/").json()
    assert not body["url"].endswith("/")


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
        "api = c.get('/api/v2/lists/x/', HTTP_HOST='go.example.com').status_code\n"
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


def test_long_multibyte_url_is_a_400_not_a_500(owner_client, owned_list):
    # ~7.9 KB of UTF-8 in under 2048 characters used to overflow the unique index.
    response = post_link(owner_client, owned_list, "https://example.com/" + "😀" * 1900)
    assert response.status_code == 400
    assert "bytes" in response.json()["destination_url"][0]


def test_largest_allowed_multibyte_url_fits_the_index(owner_client, owned_list):
    url = "https://example.com/" + "😀" * ((2048 - len("https://example.com/")) // 4)
    assert post_link(owner_client, owned_list, url).status_code == 201


def test_ss_and_sharp_s_domains_stay_different(api_client, owner_client, owned_list):
    sharp = post_link(owner_client, owned_list, "https://faß.example/")
    plain = post_link(owner_client, owned_list, "https://fass.example/")

    assert (sharp.status_code, plain.status_code) == (201, 201)  # two real domains
    code = SharedLink.objects.get(pk=sharp.json()["id"]).redirects.get().code
    assert api_client.get(f"/r/{code}")["Location"] == "https://xn--fa-hia.example/"


def test_empty_link_title_is_stored_as_null(owner_client, owned_list):
    response = post_link(owner_client, owned_list, "https://example.com/", title="")
    assert response.json()["title"] is None
    assert SharedLink.objects.get(pk=response.json()["id"]).title is None


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


def test_throttle_histories_are_not_culled_by_cache_size(db):
    cache = caches["default"]
    # Django culls the alphabetically-first keys, so this one would be among the first to go.
    # (Letters, not IPs: the database collation ignores dots when ordering keys.)
    survivor = "throttle_list_create_a"
    cache.set(survivor, [1.0], 3600)
    for i in range(400):  # more than Django's default MAX_ENTRIES (300)
        cache.set(f"throttle_list_create_z{i:03d}", [1.0], 3600)

    assert cache.get(survivor) == [1.0]


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
