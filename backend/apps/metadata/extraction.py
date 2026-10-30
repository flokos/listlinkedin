"""A link's metadata, from its page (docs/v2/adr/ADR-008-background-metadata-extraction.md).

`extract(url)` fetches the page through the SSRF-safe fetcher, reads its metadata, then
fetches its icon and its preview image (`og:image`) and passes them through the same image
pipeline as uploads (decoded under limits and re-encoded, apps.metadata.images). The result
is plain data for `SharedLink.metadata` (stored by task 7.3, which never touches the link's
own fields). The preview image is stored but not shown yet: page pictures are postponed (Q16,
D28).
"""

import logging
import time

from . import fetcher, images, parser
from .tasks import TemporaryFailure

logger = logging.getLogger(__name__)

MAX_ICON_ATTEMPTS = 3
# Images are extras: none is started once the whole extraction has taken this long.
IMAGE_BUDGET = 30.0  # seconds


def extract(url: str) -> dict:
    """The metadata of the page at `url`:

    `{"title", "description", "site_name", "icon", "image", "url"}`: texts or None, `icon`
    and `image` as media paths or None, `url` the final URL after redirects.

    Raises what `fetcher.fetch` raises for the page itself (`FetchRefused`, `FetchFailed`,
    `TemporaryFailure`). An icon or image that can't be had is simply left out.
    """
    started = time.monotonic()
    page = fetcher.fetch(url, fetcher.PAGE)
    found = parser.parse(page.body, page.url, page.charset)

    def in_budget() -> bool:
        return time.monotonic() - started < IMAGE_BUDGET

    icon = _first_image(found.icon_urls[:MAX_ICON_ATTEMPTS], images.ICON, in_budget)
    image = _first_image([found.image_url], images.IMAGE, in_budget) if found.image_url else None
    return {
        "title": found.title,
        "description": found.description,
        "site_name": found.site_name,
        "icon": icon,
        "image": image,
        "url": page.url,
    }


def _first_image(urls: list[str], kind: images.Kind, in_budget) -> str | None:
    """The media path of the first of `urls` that is an image we accept, or None."""
    for url in urls:
        if not in_budget():
            return None
        try:
            fetched = fetcher.fetch(url, fetcher.IMAGE)
            webp = images.process(fetched.body, kind, formats=images.FETCHED_FORMATS)
        except (
            fetcher.FetchRefused,
            fetcher.FetchFailed,
            TemporaryFailure,
            images.ImageRejected,
        ) as exc:
            logger.info("No %s from %s: %s", kind.directory, url, exc)
            continue
        return images.store(webp, kind)
    return None
