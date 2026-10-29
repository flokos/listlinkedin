"""The image pipeline (docs/v2/13-SECURITY.md#media, ADR-012): identification by content,
pixel limits, re-encoding to WebP, and content-addressed storage."""

import io
import struct
import zlib

import pytest
from PIL import Image, PngImagePlugin

from apps.metadata import images


def encode(fmt: str, size=(300, 200), color=(200, 30, 30, 255), **save) -> bytes:
    out = io.BytesIO()
    picture = Image.new("RGBA", size, color)
    if fmt in ("JPEG",):
        picture = picture.convert("RGB")
    picture.save(out, format=fmt, **save)
    return out.getvalue()


def decoded(webp: bytes) -> Image.Image:
    picture = Image.open(io.BytesIO(webp))
    assert picture.format == "WEBP"
    return picture


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP", "GIF"])
def test_accepted_formats_are_reencoded_to_webp_within_bounds(fmt):
    webp = images.process(encode(fmt, size=(1000, 500)), images.ICON)
    assert decoded(webp).size == (128, 64)  # aspect ratio kept
    assert decoded(images.process(encode(fmt, size=(1000, 500)), images.IMAGE)).size == (512, 256)


def test_small_images_are_not_enlarged():
    assert decoded(images.process(encode("PNG", size=(16, 16)), images.ICON)).size == (16, 16)


def test_svg_ico_and_other_files_are_refused_whatever_their_name():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    html = b"<!doctype html><script>alert(1)</script>"
    for data in (svg, html, b"", b"\x89PNG\r\n\x1a\n" + b"\0" * 40, encode("BMP")):
        with pytest.raises(images.ImageRejected, match="PNG, JPEG, WebP or GIF"):
            images.process(data, images.ICON)
    ico = encode("ICO", size=(32, 32))
    with pytest.raises(images.ImageRejected):
        images.process(ico, images.ICON)  # uploads: no ICO
    fetched = images.process(ico, images.ICON, formats=images.FETCHED_FORMATS)
    assert decoded(fetched).size == (32, 32)


def test_a_truncated_image_is_refused():
    with pytest.raises(images.ImageRejected):
        images.process(encode("PNG")[:-30], images.ICON)


def png_header_only(width: int, height: int) -> bytes:
    """A tiny PNG that claims huge dimensions: a decompression bomb's header."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"\0" * 64)
    return (
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")
    )


@pytest.mark.parametrize(("width", "height"), [(5000, 4000), (20000, 20000)])
def test_decompression_bombs_are_refused_before_decoding(width, height):
    # 20 MP is over the limit (Pillow warns); 400 MP is far over it (Pillow raises).
    with pytest.raises(images.ImageRejected, match="16 megapixels"):
        images.process(png_header_only(width, height), images.IMAGE)


def test_files_over_2_mb_are_refused():
    with pytest.raises(images.ImageRejected, match="2 MB"):
        images.process(b"\0" * (images.MAX_UPLOAD_BYTES + 1), images.ICON)


def test_a_polyglot_payload_does_not_survive():
    payload = "<script>alert('stored xss')</script>"
    text = PngImagePlugin.PngInfo()
    text.add_text("Comment", payload)  # inside the PNG, in a text chunk
    for polyglot in (
        encode("GIF") + payload.encode(),  # a valid GIF with HTML/JS appended
        encode("PNG", pnginfo=text),
    ):
        assert payload.encode() in polyglot
        webp = images.process(polyglot, images.ICON)
        assert b"<script" not in webp


def test_exif_orientation_is_applied_and_metadata_stripped():
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation: rotate 90° clockwise to display
    exif[0x8825] = {2: (37.0, 58.0, 0.0)}  # GPS latitude
    exif[0x010F] = "SecretCam"  # make
    jpeg = encode("JPEG", size=(200, 100), exif=exif)
    webp = images.process(jpeg, images.IMAGE)
    picture = decoded(webp)
    assert picture.size == (100, 200)  # turned upright
    assert not picture.getexif() and b"SecretCam" not in webp and b"Exif" not in webp


def test_animations_keep_their_first_frame():
    out = io.BytesIO()
    frames = [Image.new("RGB", (20, 20), c) for c in ((255, 0, 0), (0, 0, 255))]
    frames[0].save(out, format="GIF", save_all=True, append_images=frames[1:])
    picture = decoded(images.process(out.getvalue(), images.ICON))
    assert getattr(picture, "n_frames", 1) == 1
    red, _, blue = picture.convert("RGB").getpixel((5, 5))
    assert red > 240 and blue < 15  # red (WebP is lossy), not the blue second frame


def test_storage_is_content_addressed(media_root):
    webp = images.process(encode("PNG"), images.ICON)
    path = images.store(webp, images.ICON)
    digest = path.rsplit("/", 1)[1].removesuffix(".webp")
    assert path == f"icons/{digest[:2]}/{digest}.webp" and len(digest) == 64
    assert (media_root / path).read_bytes() == webp
    assert oct((media_root / path).stat().st_mode & 0o777) == "0o644"  # nginx can read it
    assert images.store(webp, images.ICON) == path  # the same image is stored once
    assert sorted(p.name for p in media_root.rglob("*") if p.is_file()) == [f"{digest}.webp"]
    assert images.url_for(path) == f"/media/{path}" and images.url_for(None) is None
