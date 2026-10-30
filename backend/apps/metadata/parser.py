"""Reading a fetched page's metadata (docs/v2/13-SECURITY.md#ssrf-safe-fetcher, step 8).

The standard library's HTML parser runs over the capped bytes the fetcher returns: no
scripts, no network, no DOM. Only what describes the page is kept: the title, the
description, Open Graph's title, description, image and site name, and the icons it links.
Values are cleaned (whitespace collapsed, control characters dropped) and truncated to the
lengths links store. The HTML itself is never stored.
"""

import codecs
import re
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from apps.sharing.domain import MAX_DESCRIPTION_LENGTH

MAX_TITLE_LENGTH = 255  # SharedLink.title
MAX_SITE_NAME_LENGTH = 100
MAX_URL_LENGTH = 2048
MAX_ICONS = 5
_META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([a-zA-Z0-9_\-]+)""", re.I)
_SPACE = re.compile(r"\s+")


@dataclass
class PageMetadata:
    title: str | None = None
    description: str | None = None
    site_name: str | None = None
    image_url: str | None = None  # og:image, absolute http(s)
    icon_urls: list[str] = field(default_factory=list)  # best first, then /favicon.ico


def parse(body: bytes, url: str, charset: str | None = None) -> PageMetadata:
    """The metadata of the page at `url` (its final URL, for relative links)."""
    reader = _Reader()
    reader.feed(_decode(body, charset))
    reader.close()
    base = _http_url(urljoin(url, reader.base)) if reader.base else url
    meta = reader.meta

    def text(*names: str, limit: int) -> str | None:
        for name in names:
            value = _clean(meta.get(name) if name != "<title>" else reader.title, limit)
            if value:
                return value
        return None

    image = meta.get("og:image:secure_url") or meta.get("og:image")
    return PageMetadata(
        title=text("og:title", "<title>", "twitter:title", limit=MAX_TITLE_LENGTH),
        description=text(
            "og:description", "description", "twitter:description", limit=MAX_DESCRIPTION_LENGTH
        ),
        site_name=text("og:site_name", "application-name", limit=MAX_SITE_NAME_LENGTH),
        image_url=_http_url(urljoin(base, image.strip())) if image else None,
        icon_urls=_icons(reader.icons, base, url),
    )


class _Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.icons: list[tuple[int, int, str]] = []  # (preference, size, href)
        self.base: str | None = None
        self.title: str | None = None
        self._in_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").strip().lower()
            if key and "content" in a and key not in self.meta:  # the first one wins
                self.meta[key] = a["content"]
        elif tag == "link" and a.get("href"):
            rels = a.get("rel", "").lower().split()
            if "icon" in rels or "apple-touch-icon" in rels:
                if "svg" in a.get("type", "").lower() or a["href"].lower().endswith(".svg"):
                    return  # SVG is never fetched
                preference = 0 if "apple-touch-icon" in rels else 1
                self.icons.append((preference, -_size(a.get("sizes", "")), a["href"]))
        elif tag == "base" and a.get("href") and self.base is None:
            self.base = a["href"]
        elif tag == "title" and self.title is None:
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title" and self._in_title:
            self._in_title = False
            self.title = "".join(self._title_parts)

    def handle_data(self, data):
        if self._in_title:
            self._title_parts.append(data)


def _size(sizes: str) -> int:
    """The largest side in a `sizes` attribute ("32x32 64x64"), 0 if none ("any" included)."""
    best = 0
    for size in sizes.lower().split():
        width, _, height = size.partition("x")
        if width.isdigit() and height.isdigit():
            best = max(best, int(width), int(height))
    return best


def _icons(icons, base: str, url: str) -> list[str]:
    ordered = [href for _, _, href in sorted(icons, key=lambda icon: icon[:2])]
    parts = urlsplit(url)
    candidates = [urljoin(base, href.strip()) for href in ordered]
    candidates.append(f"{parts.scheme}://{parts.netloc}/favicon.ico")
    seen = []
    for candidate in candidates:
        candidate = _http_url(candidate)
        if candidate and candidate not in seen:
            seen.append(candidate)
    return seen[:MAX_ICONS]


def _http_url(url: str) -> str | None:
    """`url` if it is an absolute http(s) URL of a sane length (no data:, javascript:…)."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.netloc or len(url) > MAX_URL_LENGTH:
        return None
    return url


def _decode(body: bytes, charset: str | None) -> str:
    """The header's charset, else a <meta charset> near the start, else UTF-8."""
    for candidate in (charset, _meta_charset(body), "utf-8"):
        if candidate:
            try:
                codecs.lookup(candidate)
            except LookupError:
                continue
            return body.decode(candidate, errors="replace")
    return body.decode("utf-8", errors="replace")


def _meta_charset(body: bytes) -> str | None:
    match = _META_CHARSET.search(body[:2048])
    return match.group(1).decode("ascii") if match else None


def _clean(value: str | None, limit: int) -> str | None:
    """Whitespace collapsed, control and format characters removed, cut to `limit`."""
    if not value:
        return None
    kept = "".join(
        " " if ch.isspace() else ch
        for ch in value
        if ch.isspace() or unicodedata.category(ch) not in ("Cc", "Cf", "Cs", "Co", "Cn")
    )
    text = _SPACE.sub(" ", kept).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text or None
