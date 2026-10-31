"""Business rules for lists and links that do not depend on HTTP or the database."""

import re
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit

import idna
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.text import slugify

LIST_LIFETIME = timedelta(days=30)
MAX_LINKS_PER_LIST = 100
MAX_URL_LENGTH = 2048
MAX_DESCRIPTION_LENGTH = 1000
MAX_SLUG_LENGTH = 80
# Second path segments the app uses under /l/{code}/ (V1's edit link is /l/{code}/manage).
RESERVED_SLUGS = frozenset({"manage", "history", "sync", "settings"})


def slug_for(title: str) -> str:
    """The cosmetic URL suffix for a list title. Never unique, never resolved."""
    slug = slugify(title)[:MAX_SLUG_LENGTH].strip("-") or "list"
    return f"{slug[: MAX_SLUG_LENGTH - 5]}-list" if slug in RESERVED_SLUGS else slug


def display_host(url: str) -> str:
    """A link's host for display: lowercase, without `www.`. Internationalized hosts stay in
    punycode, as stored, so look-alike hosts can't pass for familiar ones (frontend: the
    same rule in utils/url.ts)."""
    host = (urlsplit(url).hostname or "").removeprefix("www.")
    return host or url


_url_validator = URLValidator(schemes=["http", "https"])
_DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize_destination_url(raw_url: str) -> str:
    """Validate a destination URL and return its canonical form.

    Normalization only applies equivalences that never change the destination: surrounding
    whitespace is trimmed, the scheme is lowercased, the host is lowercased and converted to
    its ASCII (punycode) form, an empty path becomes "/" and the scheme's default port is
    dropped. The path, query (including parameter order) and fragment are kept byte-for-byte.
    """
    url = raw_url.strip()
    # Bytes, not characters: the (list, URL) unique index holds at most ~2.7 KB, and a
    # 2048-character URL of non-ASCII characters can be four times that size.
    if len(url.encode()) > MAX_URL_LENGTH:
        raise ValidationError(
            f"URL must be at most {MAX_URL_LENGTH} bytes (non-ASCII characters count more)."
        )

    try:
        parts = urlsplit(url)
        port = parts.port  # raises for non-numeric or out-of-range ports
        host = ascii_host(parts.hostname or "")
    except ValueError as exc:  # e.g. "http://[::1" or an invalid internationalized label
        raise ValidationError("Enter a valid URL.") from exc

    scheme = parts.scheme.lower()
    if scheme not in _DEFAULT_PORTS:
        raise ValidationError("Only http and https URLs are allowed.")
    if parts.username is not None or parts.password is not None:
        raise ValidationError("URLs with embedded credentials are not allowed.")
    if port == 0:
        raise ValidationError("Enter a valid URL.")

    _url_validator(url)  # rejects malformed hosts, whitespace, etc.
    if is_blocked_destination(url):
        raise ValidationError("Links to this host are not allowed.")

    netloc = f"[{host}]" if ":" in host else host  # IPv6 literals keep their brackets
    if port is not None and port != _DEFAULT_PORTS[scheme]:
        netloc = f"{netloc}:{port}"
    return urlunsplit((scheme, netloc, parts.path or "/", parts.query, parts.fragment))


def ascii_host(host: str) -> str:
    """Lowercase ASCII form of a host, so "Bücher.example" and "xn--bcher-kva.example" match.

    Uses IDNA2008 with UTS #46 non-transitional processing, which is what browsers do.
    Python's built-in "idna" codec implements IDNA2003, which maps e.g. "faß" to "fass": a
    different domain from the one visitors would reach. Raises ValueError for invalid hosts.
    """
    host = host.lower().rstrip(".")
    if host.isascii():
        return host
    try:
        return idna.encode(host, uts46=True, transitional=False).decode("ascii")
    except idna.IDNAError as exc:
        raise ValueError(f"Invalid internationalized host: {host!r}") from exc


def blocked_hosts() -> set[str]:
    """Hosts links may not point to: every name of this service plus the denylist.

    "This service" is every name Django answers to (ALLOWED_HOSTS) plus the public base URL,
    so aliases such as 127.0.0.1 cannot be used to build redirect loops or hidden chains.
    Raises ValueError if a configured host is invalid (checked once at startup).
    """
    own_hosts = [
        urlsplit(settings.PUBLIC_BASE_URL).hostname or "",
        *(h.lstrip(".") for h in settings.ALLOWED_HOSTS if h != "*"),
    ]
    return {ascii_host(h) for h in (*own_hosts, *settings.BLOCKED_DESTINATION_HOSTS) if h}


def is_blocked_destination(url: str) -> bool:
    """True if the URL's host, or a parent domain of it, is in `blocked_hosts()`."""
    try:
        host = ascii_host(urlsplit(url).hostname or "")
    except ValueError:
        return True  # unparseable hosts are never valid destinations
    return any(host == b or host.endswith(f".{b}") for b in blocked_hosts())


# Tags (docs/v2/04-DOMAIN-MODEL.md#value-objects): lowercase words joined by hyphens.
MAX_TAGS = 10
MAX_TAG_LENGTH = 32
_TAG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def normalize_tags(raw: list[str]) -> list[str]:
    """Tags as stored: trimmed, lowercased, spaces and underscores as hyphens, duplicates
    dropped (first kept). Raises ValidationError for an invalid tag or too many."""
    tags: list[str] = []
    for value in raw:
        tag = re.sub(r"[\s_]+", "-", value.strip().lower())
        if not tag:
            continue
        if len(tag) > MAX_TAG_LENGTH or not _TAG.fullmatch(tag):
            raise ValidationError(
                f"“{value}” isn't a tag: use letters, digits and hyphens, "
                f"at most {MAX_TAG_LENGTH} characters."
            )
        if tag not in tags:
            tags.append(tag)
    if len(tags) > MAX_TAGS:
        raise ValidationError(f"At most {MAX_TAGS} tags.")
    return tags
