"""The SSRF-safe fetcher (docs/v2/13-SECURITY.md#ssrf-safe-fetcher), against local servers
with a stub resolver (conftest.py). Each rule of the spec has a test here."""

import ipaddress

import pytest

from apps.metadata import fetcher
from apps.metadata.fetcher import FetchFailed, FetchRefused
from apps.metadata.tasks import TemporaryFailure

from .conftest import PUBLIC, gzipped

HTML = "<!doctype html><title>Hello</title>"


def test_fetches_a_page_over_http_and_https(web):
    web.page("/", HTML)
    for url in ("http://site.test/", "https://site.test/"):
        page = fetcher.fetch(url)
        assert (page.url, page.content_type, page.charset) == (url, "text/html", "utf-8")
        assert page.body == HTML.encode() and not page.truncated
    # Pinned: the name was looked up once per fetch, and only the checked address was dialed.
    assert web.lookups == ["site.test", "site.test"]
    assert web.dialed == [(PUBLIC, 80), (PUBLIC, 443)]


def test_requests_carry_no_cookies_referer_or_credentials(web):
    web.redirect("site.test", "/", "/next")
    web.add("site.test", "/next", status=302, headers={"Location": "/end", "Set-Cookie": "s=1"})
    web.page("/end", HTML)
    fetcher.fetch("https://site.test/")
    for host, path, headers in web.requests:
        assert host == "site.test"
        names = {name.lower() for name in headers}
        assert not names & {"cookie", "referer", "authorization"}, (path, names)
        assert headers["User-Agent"].startswith("listlinkedin-metadata/1.0 (+")


@pytest.mark.parametrize(
    "addresses",
    [
        ["127.0.0.1"],
        ["10.1.2.3"],
        ["172.16.0.9"],
        ["192.168.1.1"],
        ["100.64.0.1"],  # carrier-grade NAT
        ["169.254.169.254"],  # cloud metadata
        ["0.0.0.0"],
        ["224.0.0.1"],
        ["198.51.100.7"],  # documentation range: not global
        ["::1"],
        ["fd00::1"],
        ["fe80::1"],
        ["::ffff:127.0.0.1"],  # IPv4-mapped
        ["2002:7f00:1::"],  # 6to4 around 127.0.0.1
        ["2001:0:4136:e378:8000:63bf:f5ff:fffe"],  # Teredo around 10.0.0.1
        [PUBLIC, "10.0.0.1"],  # one private answer is enough to refuse
    ],
)
def test_refuses_names_that_resolve_to_non_public_addresses(web, addresses):
    web.dns["site.test"] = addresses
    with pytest.raises(FetchRefused, match="non-public"):
        fetcher.fetch("http://site.test/")
    assert web.dialed == []


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[::ffff:7f00:1]/",
    ],
)
def test_refuses_ip_literals_that_are_not_public(web, url):
    with pytest.raises(FetchRefused):
        fetcher.fetch(url)
    assert web.dialed == [] and web.lookups == []


@pytest.mark.parametrize(
    "url",
    [
        "http://site.test:8080/",  # other ports: no probing of internal services
        "https://site.test:8443/",
        "ftp://site.test/",
        "file:///etc/passwd",
        "http://user:pw@site.test/",
        "http://localhost/",  # this service's own names (ALLOWED_HOSTS) are blocked
    ],
)
def test_refuses_what_the_url_policy_refuses(web, url):
    with pytest.raises(FetchRefused):
        fetcher.fetch(url)
    assert web.dialed == []


def test_dns_rebinding_cant_redirect_the_connection(web, monkeypatch):
    """The name resolves to a public address when checked and to a private one afterwards.
    The fetcher never asks again: it connects to the address it checked."""
    answers = iter([[PUBLIC], ["127.0.0.1"]])

    def rebinding(host, port):
        web.lookups.append(host)
        return next(answers)

    monkeypatch.setattr(fetcher, "resolve", rebinding)
    web.page("/", HTML)
    assert fetcher.fetch("http://site.test/").body == HTML.encode()
    assert web.lookups == ["site.test"]
    assert web.dialed == [(PUBLIC, 80)]


def test_each_redirect_is_checked_again(web):
    web.redirect("site.test", "/", "https://www.site.test/landing")
    web.page("/landing", HTML, host="www.site.test")
    page = fetcher.fetch("http://site.test/")
    assert page.url == "https://www.site.test/landing"
    assert web.lookups == ["site.test", "www.site.test"]

    web.dns["other.test"] = ["10.0.0.5"]
    web.redirect("site.test", "/sneaky", "http://other.test/admin")
    with pytest.raises(FetchRefused):
        fetcher.fetch("http://site.test/sneaky")
    web.redirect("site.test", "/meta", "http://169.254.169.254/latest/")
    with pytest.raises(FetchRefused):
        fetcher.fetch("http://site.test/meta")
    web.redirect("site.test", "/port", "http://site.test:6379/")
    with pytest.raises(FetchRefused):
        fetcher.fetch("http://site.test/port")
    assert ("10.0.0.5", 80) not in web.dialed


def test_follows_at_most_three_redirects(web):
    for hop in range(3):
        web.redirect("site.test", f"/{hop}", f"/{hop + 1}")
    web.page("/3", HTML)
    web.page("/4", HTML)
    assert fetcher.fetch("http://site.test/0").url == "http://site.test/3"  # 3 redirects
    web.redirect("site.test", "/3", "/4")  # now 4
    with pytest.raises(FetchFailed, match="More than 3 redirects"):
        fetcher.fetch("http://site.test/0")


def test_a_certificate_for_another_name_is_refused(web):
    web.page("/", HTML, host="other.test")  # the test certificate doesn't cover other.test
    with pytest.raises(FetchFailed, match="TLS"):
        fetcher.fetch("https://other.test/")


@pytest.mark.parametrize(
    ("status", "error"),
    [(404, FetchFailed), (403, FetchFailed), (429, TemporaryFailure), (503, TemporaryFailure)],
)
def test_errors_from_the_site(web, status, error):
    web.add("site.test", "/", status=status, body=b"no")
    with pytest.raises(error):
        fetcher.fetch("http://site.test/")


def test_only_pages_and_raster_images_are_read(web):
    web.add("site.test", "/doc.pdf", body=b"%PDF", headers={"Content-Type": "application/pdf"})
    web.add("site.test", "/logo.svg", body=b"<svg/>", headers={"Content-Type": "image/svg+xml"})
    web.add("site.test", "/logo.png", body=b"png", headers={"Content-Type": "image/png"})
    with pytest.raises(FetchFailed, match="application/pdf"):
        fetcher.fetch("http://site.test/doc.pdf")
    with pytest.raises(FetchFailed, match="svg"):
        fetcher.fetch("http://site.test/logo.svg", fetcher.IMAGE)
    with pytest.raises(FetchFailed, match="image/png"):
        fetcher.fetch("http://site.test/logo.png")  # an image where a page was expected
    assert fetcher.fetch("http://site.test/logo.png", fetcher.IMAGE).body == b"png"


def test_pages_stop_at_the_limit_and_images_over_it_are_refused(web):
    big = b"<title>Big</title>" + b"x" * (fetcher.MAX_PAGE_BYTES + 5000)
    web.add("site.test", "/big", body=big, headers={"Content-Type": "text/html"})
    page = fetcher.fetch("http://site.test/big")
    assert page.truncated and len(page.body) == fetcher.MAX_PAGE_BYTES
    assert page.body.startswith(b"<title>Big</title>")

    huge = b"\x89PNG" + b"0" * fetcher.MAX_IMAGE_BYTES
    web.add("site.test", "/huge.png", body=huge, headers={"Content-Type": "image/png"})
    with pytest.raises(FetchFailed, match="Larger than"):
        fetcher.fetch("http://site.test/huge.png", fetcher.IMAGE)


def test_size_is_counted_after_decompression(web):
    """A compression bomb: a few KB on the wire, megabytes once decompressed."""
    bomb = gzipped(b"0" * (20 * 1024 * 1024))
    assert len(bomb) < 30_000
    web.add(
        "site.test",
        "/bomb.png",
        body=bomb,
        headers={"Content-Type": "image/png", "Content-Encoding": "gzip"},
    )
    with pytest.raises(FetchFailed, match="Larger than"):
        fetcher.fetch("http://site.test/bomb.png", fetcher.IMAGE)
    html = b"<title>Zipped</title>"
    web.add(
        "site.test",
        "/zipped",
        body=gzipped(html),
        headers={"Content-Type": "text/html", "Content-Encoding": "gzip"},
    )
    assert fetcher.fetch("http://site.test/zipped").body == html


def test_slow_sites_time_out(web, monkeypatch):
    monkeypatch.setattr(fetcher, "READ_TIMEOUT", 0.5)
    web.page("/slow", HTML, delay=1.5)
    with pytest.raises(TemporaryFailure):
        fetcher.fetch("http://site.test/slow")

    # A trickle that never trips the per-read timeout still ends at the overall deadline.
    monkeypatch.setattr(fetcher, "TOTAL_TIMEOUT", 1.0)
    web.page("/trickle", "<title>t</title>" + "x" * 20_000, trickle=0.1)
    with pytest.raises(TemporaryFailure, match="longer than"):
        fetcher.fetch("http://site.test/trickle")


def test_unknown_names_fail_for_good(web):
    with pytest.raises(FetchFailed, match="doesn't exist"):
        fetcher.fetch("http://missing.test/")


def test_one_request_per_host_per_interval(web, monkeypatch):
    monkeypatch.setattr(fetcher, "PER_HOST_INTERVAL", 0.3)
    sleeps = []
    monkeypatch.setattr(fetcher, "_sleep", sleeps.append)
    web.page("/", HTML)
    fetcher.fetch("http://site.test/")
    fetcher.fetch("http://site.test/")
    assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.3


@pytest.mark.parametrize(
    ("address", "public"),
    [
        ("8.8.8.8", True),
        ("2606:4700:4700::1111", True),
        ("::ffff:8.8.8.8", True),  # mapped, but to a public address
        ("::ffff:192.168.0.1", False),
        ("2002:c0a8:0101::", False),  # 6to4 around 192.168.1.1
        ("64:ff9b::7f00:1", False),  # NAT64 to 127.0.0.1 (Python calls the prefix global)
        ("64:ff9b::808:808", True),  # NAT64 to 8.8.8.8
        ("ff02::1", False),
    ],
)
def test_is_public(address, public):
    assert fetcher.is_public(ipaddress.ip_address(address)) is public


def test_deployments_can_block_more_networks_but_never_fewer(web, settings):
    web.page("/", HTML)
    settings.FETCH_BLOCKED_NETWORKS = ["93.184.215.0/24"]  # PUBLIC is in it
    with pytest.raises(FetchRefused, match="non-public"):
        fetcher.fetch("http://site.test/")
    assert web.dialed == []

    # Listing a built-in range again changes nothing, and nothing can remove one.
    settings.FETCH_BLOCKED_NETWORKS = ["169.254.0.0/16"]
    assert fetcher.is_public(ipaddress.ip_address("169.254.169.254")) is False
    settings.FETCH_BLOCKED_NETWORKS = []
    assert fetcher.is_public(ipaddress.ip_address("169.254.169.254")) is False
    assert fetcher.fetch("http://site.test/").body == HTML.encode()


def test_an_invalid_extra_network_stops_the_app_at_startup(settings):
    from django.apps import apps
    from django.core.exceptions import ImproperlyConfigured

    settings.FETCH_BLOCKED_NETWORKS = ["10.0.0.0/33"]
    with pytest.raises(ImproperlyConfigured, match="FETCH_BLOCKED_NETWORKS"):
        apps.get_app_config("metadata").ready()
    settings.FETCH_BLOCKED_NETWORKS = ["192.168.1.1/24"]  # host bits set: a likely typo
    with pytest.raises(ImproperlyConfigured):
        apps.get_app_config("metadata").ready()
