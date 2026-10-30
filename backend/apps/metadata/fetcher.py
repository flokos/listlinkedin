"""The only code that fetches user-supplied URLs (docs/v2/13-SECURITY.md#ssrf-safe-fetcher).

A link's URL is untrusted: fetching it naively would let anyone make the server request
internal addresses (the database, cloud metadata at 169.254.169.254, intranet pages). So this
follows OWASP's guidance for arbitrary external destinations:

1. The URL is normalized and checked against the host policy again; http and https on ports
   80 and 443 only.
2. The host is resolved once, and **every** address must be public. One private address
   rejects the URL: an attacker controls their DNS answers.
3. The connection goes to the address that was checked (pinned). The original host name is
   used only for the Host header, TLS SNI and certificate verification, so the HTTP client
   never resolves the name again (that second lookup is the DNS-rebinding gap).
4. Redirects are followed by hand, at most 3, each hop checked from step 1.
5. Limits: connect 3 s, each read 5 s, 10 s in all; pages 512 KB and images 1 MB, counted
   after decompression. Only HTML pages and raster images; never SVG.
6. No cookies, credentials or Referer; a fixed User-Agent; one request per host per second.

Failures raise `FetchRefused` (the policy said no: never retried), `FetchFailed` (the site said
no or sent something unusable: not retried) or `TemporaryFailure` (timeouts, connection
errors, 429 and 5xx: retried by the task, apps.metadata.tasks).
"""

import ipaddress
import socket
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import urllib3
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.sharing.domain import normalize_destination_url

from .tasks import TemporaryFailure

CONNECT_TIMEOUT = 3.0
READ_TIMEOUT = 5.0
TOTAL_TIMEOUT = 10.0
MAX_REDIRECTS = 3
MAX_PAGE_BYTES = 512 * 1024
MAX_IMAGE_BYTES = 1024 * 1024
ALLOWED_PORTS = (80, 443)
PER_HOST_INTERVAL = 1.0  # seconds between requests to one host, per worker process

PAGE_TYPES = frozenset({"text/html", "application/xhtml+xml"})
IMAGE_TYPES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/x-icon",
        "image/vnd.microsoft.icon",
        "image/ico",
    }
)
_REDIRECTS = frozenset({301, 302, 303, 307, 308})
_CHUNK = 16 * 1024

# Never fetched, whatever `is_global` says (it already excludes all of these; listed so the
# rule doesn't depend on one library flag). A fixed floor in code, not a setting: a typo or a
# missing variable must never unblock cloud metadata or loopback. Deployments add their own
# ranges with FETCH_BLOCKED_NETWORKS (`denied_networks()`), never remove these.
BUILT_IN_DENIED_NETWORKS = tuple(
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",  # link-local, including cloud metadata (169.254.169.254)
        "172.16.0.0/12",
        "192.168.0.0/16",
        "224.0.0.0/4",  # multicast
        "240.0.0.0/4",
        "::/128",
        "::1/128",
        "fc00::/7",  # unique local
        "fe80::/10",  # link-local
        "ff00::/8",  # multicast
    )
)


class FetchRefused(Exception):
    """The URL may not be fetched: a private address, another port, a blocked host…"""


class FetchFailed(Exception):
    """The site answered with an error or something we don't accept (not worth retrying)."""


@dataclass(frozen=True)
class Fetched:
    url: str  # the final URL, after redirects
    content_type: str  # lowercased, without parameters
    charset: str | None
    body: bytes  # decompressed, at most the limit
    truncated: bool  # a page longer than the limit (images over it are refused instead)


@dataclass(frozen=True)
class Accept:
    types: frozenset
    max_bytes: int
    truncate: bool  # stop at the limit and keep what was read, or refuse the whole thing


PAGE = Accept(PAGE_TYPES, MAX_PAGE_BYTES, truncate=True)
IMAGE = Accept(IMAGE_TYPES, MAX_IMAGE_BYTES, truncate=False)


def system_resolver(host: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        if exc.errno in (socket.EAI_NONAME, getattr(socket, "EAI_NODATA", None)):
            raise FetchFailed(f"{host} doesn't exist.") from exc
        raise TemporaryFailure(f"Couldn't resolve {host}: {exc}") from exc
    return list(dict.fromkeys(info[4][0] for info in infos))


# Replaced in tests: a stub resolver, and a dial hook that sends the validated (public)
# address to the local test server. Production never changes them.
resolve: Callable[[str, int], list[str]] = system_resolver
dial: Callable[[str, int], tuple[str, int]] = lambda address, port: (address, port)  # noqa: E731
ca_certs: str | None = None  # None: the system's trusted CAs

_last_request: dict[str, float] = {}
_sleep = time.sleep


def fetch(url: str, accept: Accept = PAGE) -> Fetched:
    """Fetch `url` under every rule above and return the body, or raise."""
    deadline = time.monotonic() + TOTAL_TIMEOUT
    for _ in range(MAX_REDIRECTS + 1):
        target = check_url(url)
        address = public_address(target.hostname, target.port)
        pool = _pool(target, address)
        try:
            response = _request(pool, target, accept, deadline)
            if response.status not in _REDIRECTS:
                return _accept(target.url, response, accept, deadline)
            location = response.headers.get("Location")
        finally:
            pool.close()  # one connection per hop, never reused
        if not location:
            raise FetchFailed("A redirect without a Location.")
        url = urljoin(target.url, location)
    raise FetchFailed(f"More than {MAX_REDIRECTS} redirects.")


@dataclass(frozen=True)
class Target:
    url: str  # normalized, without the fragment
    scheme: str
    hostname: str  # ASCII (punycode), lowercase
    port: int
    netloc: str  # for the Host header
    path: str  # path and query, as sent in the request line


def check_url(url: str) -> Target:
    """Step 1: the URL as it would be stored, plus the fetch-only rules."""
    try:
        normalized = normalize_destination_url(url)  # schemes, host policy, credentials…
    except ValidationError as exc:
        raise FetchRefused(f"Not a URL we fetch: {exc.messages[0]}") from None
    parts = urlsplit(normalized)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    if port not in ALLOWED_PORTS:
        raise FetchRefused("Only ports 80 and 443 are fetched.")
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    return Target(
        url=urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, "")),
        scheme=parts.scheme,
        hostname=parts.hostname,
        port=port,
        netloc=parts.netloc,
        path=path,
    )


def public_address(hostname: str, port: int) -> str:
    """Step 2: resolve once; every address must be public. Returns the one to connect to."""
    if (target := test_hosts().get(hostname)) is not None:  # e2e fixture sites only
        return system_resolver(target, port)[0]
    try:
        addresses = [ipaddress.ip_address(hostname)]  # an IP literal: nothing to resolve
    except ValueError:
        addresses = [ipaddress.ip_address(a.split("%")[0]) for a in resolve(hostname, port)]
    if not addresses:
        raise FetchFailed(f"{hostname} has no addresses.")
    for address in addresses:
        if not is_public(address):
            raise FetchRefused(f"{hostname} resolves to a non-public address.")
    # IPv4 first: containers often have no IPv6 route.
    addresses.sort(key=lambda a: a.version)
    return str(addresses[0])


def test_hosts() -> dict[str, str]:
    """settings.FETCH_TEST_HOSTS as {name: compose service}. Raises ValueError for an entry
    that isn't `name=service` with a `.test` name (checked at startup, apps.metadata.apps)."""
    hosts = {}
    for entry in settings.FETCH_TEST_HOSTS:
        name, _, target = entry.partition("=")
        name, target = name.strip().lower(), target.strip()
        if not target or not name.endswith(".test"):
            raise ValueError(f"{entry!r}: use name=service, with a name ending in .test")
        hosts[name] = target
    return hosts


def is_public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(address, ipaddress.IPv6Address):
        # IPv6 forms that carry an IPv4 address are judged by that address.
        embedded = (
            address.ipv4_mapped
            or address.sixtofour
            or _teredo_client(address)
            or _nat64_target(address)
        )
        if embedded is not None:
            return is_public(embedded)
    if any(address in network for network in denied_networks()):
        return False
    return address.is_global and not address.is_multicast


def denied_networks() -> tuple:
    """The built-in ranges plus settings.FETCH_BLOCKED_NETWORKS. Raises ValueError for an
    invalid entry (checked at startup, apps.metadata.apps)."""
    extra = tuple(ipaddress.ip_network(n) for n in settings.FETCH_BLOCKED_NETWORKS)
    return BUILT_IN_DENIED_NETWORKS + extra


def _teredo_client(address: ipaddress.IPv6Address):
    return address.teredo[1] if address.teredo else None


_NAT64 = ipaddress.ip_network("64:ff9b::/96")  # RFC 6052's well-known prefix


def _nat64_target(address: ipaddress.IPv6Address):
    """The IPv4 address a NAT64 gateway would reach. Python counts the prefix as global, but
    `64:ff9b::7f00:1` is 127.0.0.1 on the far side of the gateway."""
    if address in _NAT64:
        return ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
    return None


def _pool(target: Target, address: str):
    """Step 3: connections go to `address`, never to the name."""
    host, port = dial(address, target.port)
    timeout = urllib3.Timeout(connect=CONNECT_TIMEOUT, read=READ_TIMEOUT)
    common = {"timeout": timeout, "retries": False, "maxsize": 1, "block": False}
    if target.scheme == "https":
        pool = urllib3.HTTPSConnectionPool(
            host,
            port,
            server_hostname=target.hostname,  # SNI
            assert_hostname=target.hostname,  # the certificate must be for the name
            cert_reqs=ssl.CERT_REQUIRED,
            ca_certs=ca_certs,
            **common,
        )
    else:
        pool = urllib3.HTTPConnectionPool(host, port, **common)
    return pool


def _request(pool, target: Target, accept: Accept, deadline: float):
    _wait_for_host(target.hostname, deadline)
    headers = {
        "Host": target.netloc,
        "User-Agent": user_agent(),
        "Accept": ", ".join(sorted(accept.types)) + ", */*;q=0.1",
        "Accept-Encoding": "gzip, deflate",
        # No Cookie, Authorization or Referer, ever.
    }
    try:
        return pool.urlopen(
            "GET",
            target.path,
            headers=headers,
            redirect=False,
            preload_content=False,
            decode_content=True,
            assert_same_host=False,
        )
    except urllib3.exceptions.SSLError as exc:
        raise FetchFailed(f"TLS failed for {target.hostname}: {exc}") from None
    except urllib3.exceptions.MaxRetryError as exc:  # wraps the cause, even with retries off
        if isinstance(exc.reason, urllib3.exceptions.SSLError):
            raise FetchFailed(f"TLS failed for {target.hostname}: {exc.reason}") from None
        raise TemporaryFailure(f"Couldn't reach {target.hostname}: {exc.reason}") from None
    except (urllib3.exceptions.TimeoutError, urllib3.exceptions.HTTPError, OSError) as exc:
        raise TemporaryFailure(f"Couldn't reach {target.hostname}: {exc}") from None


def _accept(url: str, response, accept: Accept, deadline: float) -> Fetched:
    try:
        if response.status == 429 or response.status >= 500:
            raise TemporaryFailure(f"The site answered {response.status}.")
        if response.status != 200:
            raise FetchFailed(f"The site answered {response.status}.")
        media_type, charset = _content_type(response.headers.get("Content-Type", ""))
        if media_type not in accept.types:
            raise FetchFailed(f"Not a type we read: {media_type or 'none'}.")
        body, truncated = _read(response, accept, deadline)
        return Fetched(url, media_type, charset, body, truncated)
    finally:
        response.release_conn()


def _read(response, accept: Accept, deadline: float) -> tuple[bytes, bool]:
    """Read the decompressed body up to the limit, within the overall deadline. The size is
    counted after decompression, so a small compressed bomb can't get past the limit."""
    chunks, size = [], 0
    try:
        while True:
            if time.monotonic() > deadline:
                raise TemporaryFailure(f"Took longer than {TOTAL_TIMEOUT:.0f} s.")
            chunk = response.read(_CHUNK, decode_content=True)
            if not chunk:
                return b"".join(chunks), False
            size += len(chunk)
            if size > accept.max_bytes:
                if not accept.truncate:
                    raise FetchFailed(f"Larger than {accept.max_bytes} bytes.")
                chunks.append(chunk[: len(chunk) - (size - accept.max_bytes)])
                return b"".join(chunks), True
            chunks.append(chunk)
    except urllib3.exceptions.DecodeError as exc:
        raise FetchFailed(f"Couldn't decompress the answer: {exc}") from None
    except (urllib3.exceptions.TimeoutError, urllib3.exceptions.HTTPError, OSError) as exc:
        raise TemporaryFailure(f"The answer stopped: {exc}") from None


def _content_type(header: str) -> tuple[str, str | None]:
    media_type, _, params = header.partition(";")
    charset = None
    for param in params.split(";"):
        name, _, value = param.strip().partition("=")
        if name.lower() == "charset" and value:
            charset = value.strip().strip('"').lower()
    return media_type.strip().lower(), charset


def _wait_for_host(hostname: str, deadline: float) -> None:
    """At most one request per host per PER_HOST_INTERVAL from this process."""
    wait = _last_request.get(hostname, 0.0) + PER_HOST_INTERVAL - time.monotonic()
    if wait > 0:
        if time.monotonic() + wait > deadline:
            raise TemporaryFailure(f"Too many requests to {hostname} just now.")
        _sleep(wait)
    _last_request[hostname] = time.monotonic()


def user_agent() -> str:
    return f"listlinkedin-metadata/1.0 (+{settings.PUBLIC_BASE_URL})"
