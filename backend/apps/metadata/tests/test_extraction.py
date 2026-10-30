"""A link's metadata from its page (apps.metadata.extraction), and the hard time limit on tasks
(apps.metadata.tasks)."""

import io
import threading
from pathlib import Path

import pytest
from django.conf import settings
from PIL import Image

from apps.metadata import extraction, fetcher, tasks
from apps.metadata.tasks import TemporaryFailure


def image_bytes(fmt="PNG", size=(300, 200)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (200, 30, 90)).save(out, format=fmt)
    return out.getvalue()


def stored(path: str) -> Image.Image:
    return Image.open(Path(settings.MEDIA_ROOT) / path)


def test_extracts_texts_icon_and_preview_image(web):
    web.page(
        "/",
        """<title>Docker Docs</title>
        <meta name="description" content="Guides and references.">
        <meta property="og:site_name" content="Docker">
        <meta property="og:image" content="https://images.test/preview.png">
        <link rel="icon" href="/broken.png"><link rel="icon" href="/icon.png" sizes="32x32">""",
    )
    web.add("site.test", "/broken.png", body=b"nope", headers={"Content-Type": "image/png"})
    web.add("site.test", "/icon.png", body=image_bytes(), headers={"Content-Type": "image/png"})
    web.add(
        "images.test",
        "/preview.png",
        body=image_bytes(size=(1200, 630)),
        headers={"Content-Type": "image/png"},
    )

    found = extraction.extract("https://site.test/")

    assert found["title"] == "Docker Docs"
    assert found["description"] == "Guides and references."
    assert found["site_name"] == "Docker"
    assert found["url"] == "https://site.test/"
    # Re-encoded through the upload pipeline: WebP, within each kind's bounds.
    assert found["icon"].startswith("icons/") and found["icon"].endswith(".webp")
    assert max(stored(found["icon"]).size) == 128
    assert found["image"].startswith("images/")
    assert stored(found["image"]).size == (512, 269)


def test_falls_back_to_favicon_ico(web):
    web.page("/", "<title>No icon links</title>")
    web.add(
        "site.test",
        "/favicon.ico",
        body=image_bytes("ICO", (48, 48)),
        headers={"Content-Type": "image/x-icon"},
    )
    found = extraction.extract("http://site.test/")
    assert found["icon"] is not None and found["image"] is None


def test_missing_or_refused_images_are_left_out(web):
    web.dns["evil.test"] = ["10.0.0.1"]
    web.page(
        "/",
        """<title>T</title><meta property="og:image" content="http://evil.test/x.png">
        <link rel="icon" href="/nothing.png">""",
    )
    found = extraction.extract("http://site.test/")
    assert found == {
        "title": "T",
        "description": None,
        "site_name": None,
        "icon": None,
        "image": None,
        "url": "http://site.test/",
    }
    assert not any(address == "10.0.0.1" for address, _ in web.dialed)


def test_the_page_itself_failing_is_raised(web):
    web.add("site.test", "/", status=503)
    with pytest.raises(TemporaryFailure):
        extraction.extract("http://site.test/")
    with pytest.raises(fetcher.FetchRefused):
        extraction.extract("http://10.0.0.1/")


def test_images_stop_once_the_budget_is_spent(web, monkeypatch):
    monkeypatch.setattr(extraction, "IMAGE_BUDGET", 0.0)
    web.page("/", '<title>T</title><link rel="icon" href="/icon.png">')
    web.add("site.test", "/icon.png", body=image_bytes(), headers={"Content-Type": "image/png"})
    assert extraction.extract("http://site.test/")["icon"] is None
    assert [path for _, path, _ in web.requests] == ["/"]


def test_a_task_that_hangs_ends_the_worker_process(monkeypatch):
    exits = []
    monkeypatch.setattr(tasks, "exit_process", exits.append)

    with tasks.hard_time_limit(0.05, "hung"):
        threading.Event().wait(0.5)  # "hangs" past the limit
    assert exits == [tasks.EXIT_HUNG]

    exits.clear()
    with tasks.hard_time_limit(0.2, "quick"):
        pass  # done in time: the timer is cancelled
    threading.Event().wait(0.4)
    assert exits == []


def test_tasks_are_declared_with_the_limit():
    from .sample_tasks import echo

    assert echo.module_path == "apps.metadata.tests.sample_tasks.echo"  # how the worker finds it
    assert echo.call("x") == "x"
