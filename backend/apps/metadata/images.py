"""The one image pipeline for uploads and, later, fetched icons (docs/v2/adr/ADR-012).

Images are untrusted bytes. They are identified by content only (never by file name or
Content-Type), decoded under a pixel limit, shrunk into fixed bounds and **re-encoded** to
WebP. Re-encoding drops EXIF and GPS data and destroys anything smuggled in the file
(polyglots, appended scripts). SVG is never accepted: it is a document, not a picture.

Files are stored content-addressed (`{kind}/{hh}/{sha256}.webp` under MEDIA_ROOT), so they
are never overwritten and identical images are stored once. nginx serves them (/media/);
`cleanup_media` deletes the ones nothing refers to any more.
"""

import hashlib
import io
import os
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 16_000_000  # larger images are refused before they are decoded
# Pillow checks this when it reads the header: it warns above it, and raises above twice it.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

UPLOAD_FORMATS = ("PNG", "JPEG", "WEBP", "GIF")
FETCHED_FORMATS = (*UPLOAD_FORMATS, "ICO")  # favicons; uploads stay without ICO

UNSUPPORTED = "Upload a PNG, JPEG, WebP or GIF image."
TOO_LARGE_FILE = "Images can be at most 2 MB."
TOO_MANY_PIXELS = "This image is too large. Use one under 16 megapixels."


@dataclass(frozen=True)
class Kind:
    directory: str
    bound: int  # the longest side, in pixels


ICON = Kind("icons", 128)  # link icons
IMAGE = Kind("images", 512)  # list (and later group) images


class ImageRejected(ValueError):
    """The bytes aren't an image we accept. The message is safe to show to the user."""


def process(data: bytes, kind: Kind, *, formats=UPLOAD_FORMATS) -> bytes:
    """Decode `data` as one of `formats`, shrink it into `kind`'s bounds and return WebP."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageRejected(TOO_LARGE_FILE)
    with warnings.catch_warnings():
        # The warning is an error here, so anything above MAX_PIXELS is refused.
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with _open(data, formats) as probe:
                probe.verify()  # structure and checksums, without decoding the pixels
            with _open(data, formats) as image:  # verify() leaves the image unusable
                image.seek(0)  # animations: the first frame
                image.load()
                picture = ImageOps.exif_transpose(image).convert("RGBA")
        except Image.DecompressionBombError, Image.DecompressionBombWarning:
            raise ImageRejected(TOO_MANY_PIXELS) from None
        except UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError:
            # Truncated, corrupt, or another format: Pillow's decoders raise all of these.
            raise ImageRejected(UNSUPPORTED) from None
    picture.thumbnail((kind.bound, kind.bound), Image.Resampling.LANCZOS)  # never enlarges
    out = io.BytesIO()
    picture.save(out, format="WEBP", quality=85)  # no `exif=`: metadata is not carried over
    return out.getvalue()


def _open(data: bytes, formats) -> Image.Image:
    return Image.open(io.BytesIO(data), formats=list(formats))


def store(webp: bytes, kind: Kind) -> str:
    """Write the file under MEDIA_ROOT and return its relative path (what rows store).

    The name is the content's SHA-256, so an existing file is the same image: it is kept and
    its modification time refreshed, so `cleanup_media`'s grace period starts again.
    """
    digest = hashlib.sha256(webp).hexdigest()
    relative = f"{kind.directory}/{digest[:2]}/{digest}.webp"
    target = Path(settings.MEDIA_ROOT) / relative
    if target.exists():
        target.touch()
        return relative
    target.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temporary file and rename: readers never see a half-written image.
    fd, temporary = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(webp)
        os.chmod(temporary, 0o644)  # nginx reads it as another user
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return relative


def url_for(path: str | None) -> str | None:
    """The same-origin URL nginx serves a stored file at."""
    return f"{settings.MEDIA_URL}{path}" if path else None
