"""List images and link icons (task 2.3; docs/v2/09-API-DESIGN.md#uploads, ADR-012)."""

import io
import os
import time

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.metadata import images
from apps.sharing import services as legacy_services
from apps.sharing.models import ListMembership, SharedLink, SharedList
from apps.sharing.policy import Visibility
from apps.sharing.selectors import Principal
from apps.sharing.services import links as link_services
from apps.sharing.services import lists as list_services

URL = "/api/v2/lists/"


@pytest.fixture
def alice(db):
    return User.objects.create_user("alice@example.com", "pw-correct-horse-1")


@pytest.fixture
def bob(db):
    return User.objects.create_user("bob@example.com", "pw-correct-horse-1")


def client_for(user=None) -> APIClient:
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


def png(size=(1024, 768)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (20, 120, 220)).save(out, format="PNG")
    return out.getvalue()


def upload(client, path, data: bytes, name="picture.png", **extra):
    file = SimpleUploadedFile(name, data, content_type="image/png")
    return client.put(path, {"file": file}, format="multipart", **extra)


def image_path(shared_list) -> str:
    return f"{URL}{shared_list.public_code}/image/"


def icon_path(shared_list, link) -> str:
    return f"{URL}{shared_list.public_code}/links/{link.pk}/icon/"


def new_list(owner, **settings) -> SharedList:
    shared_list, _ = list_services.create_list(Principal(user=owner), title="Tools", **settings)
    return shared_list


def stored_files(media_root) -> list:
    return [p for p in media_root.rglob("*") if p.is_file()] if media_root.exists() else []


def test_the_owner_sets_and_removes_the_list_image(alice, media_root):
    shared_list = new_list(alice)
    client = client_for(alice)
    response = upload(client, image_path(shared_list), png())

    assert response.status_code == 200
    image_url = response.json()["image_url"]
    assert image_url.startswith("/media/images/") and image_url.endswith(".webp")
    with Image.open(media_root / image_url.removeprefix("/media/")) as stored:
        assert (stored.format, stored.size) == ("WEBP", (512, 384))
    assert client.get(f"{URL}{shared_list.public_code}/").json()["image_url"] == image_url

    assert client.delete(image_path(shared_list)).status_code == 204
    assert client.get(f"{URL}{shared_list.public_code}/").json()["image_url"] is None


def test_who_may_upload(alice, bob, media_root):
    shared_list = new_list(alice, visibility=Visibility.UNLISTED)
    assert upload(client_for(), image_path(shared_list), png()).status_code == 401
    assert upload(client_for(bob), image_path(shared_list), png()).status_code == 403
    ListMembership.objects.create(shared_list=shared_list, user=bob, role="viewer")
    assert upload(client_for(bob), image_path(shared_list), png()).status_code == 403
    assert client_for(bob).delete(image_path(shared_list)).status_code == 403
    assert stored_files(media_root) == []  # refused uploads store nothing
    ListMembership.objects.filter(user=bob).update(role="editor")
    assert upload(client_for(bob), image_path(shared_list), png()).status_code == 200
    private = new_list(alice)
    assert upload(client_for(bob), image_path(private), png()).status_code == 404


def test_an_edit_link_cannot_upload(db, media_root):
    shared_list, token = legacy_services.create_list(title="Legacy")
    link = legacy_services.add_link(shared_list, destination_url="https://example.com/a")
    bearer = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
    for path in (image_path(shared_list), icon_path(shared_list, link)):
        assert upload(APIClient(), path, png(), **bearer).status_code == 403
    assert stored_files(media_root) == []


def test_files_that_are_not_images_are_refused(alice, media_root):
    shared_list = new_list(alice)
    client = client_for(alice)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    response = upload(client, image_path(shared_list), svg, name="logo.png")
    assert response.status_code == 400
    assert response.json()["file"] == ["Upload a PNG, JPEG, WebP or GIF image."]
    assert client.put(image_path(shared_list), {}, format="multipart").status_code == 400
    json_body = client.put(image_path(shared_list), {"file": "x"}, format="json")
    assert json_body.status_code == 415  # uploads are multipart only
    assert stored_files(media_root) == []
    assert SharedList.objects.get(pk=shared_list.pk).image is None


def test_size_limits_are_per_route(alice):
    shared_list = new_list(alice)
    client = client_for(alice)
    # Just over 2 MB passes the request limit on an upload route, and the pipeline refuses it.
    just_over = upload(client, image_path(shared_list), b"\0" * (images.MAX_UPLOAD_BYTES + 1))
    assert just_over.status_code == 400 and just_over.json()["file"] == [
        "Images can be at most 2 MB."
    ]
    assert upload(client, image_path(shared_list), b"\0" * 3_000_000).status_code == 413
    # Everywhere else, V1's 16 KB limit stays.
    big = {"title": "x" * 20_000}
    assert client.patch(f"{URL}{shared_list.public_code}/", big, format="json").status_code == 413


def test_uploads_need_the_csrf_token_with_a_session(alice):
    shared_list = new_list(alice)
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(alice)
    assert upload(client, image_path(shared_list), png()).status_code == 403


def test_link_icons(alice, media_root):
    shared_list = new_list(alice, visibility=Visibility.UNLISTED)  # readable on v1 too
    other = new_list(alice)
    link = link_services.add_link_on(shared_list, destination_url="https://example.com/a")
    foreign = link_services.add_link_on(other, destination_url="https://example.com/b")
    client = client_for(alice)

    response = upload(client, icon_path(shared_list, link), png(size=(64, 300)))
    assert response.status_code == 200
    icon_url = response.json()["icon_url"]
    assert icon_url.startswith("/media/icons/")
    with Image.open(media_root / icon_url.removeprefix("/media/")) as stored:
        assert stored.size == (27, 128)
    listed = client.get(f"{URL}{shared_list.public_code}/links/").json()["results"]
    assert listed[0]["icon_url"] == icon_url
    v1 = client.get(f"/api/v1/lists/{shared_list.public_code}/links/").json()["results"]
    assert "icon_url" not in v1[0]  # the V1 representation is unchanged

    assert (
        upload(
            client, f"{URL}{shared_list.public_code}/links/{foreign.pk}/icon/", png()
        ).status_code
        == 404
    )
    assert client.delete(icon_path(shared_list, link)).status_code == 204
    assert SharedLink.objects.get(pk=link.pk).icon is None
    link_services.delete_link_on(shared_list, link.pk)
    assert upload(client, icon_path(shared_list, link), png()).status_code == 404


def test_identical_uploads_share_one_file(alice, media_root):
    first, second = new_list(alice), new_list(alice)
    client = client_for(alice)
    a = upload(client, image_path(first), png()).json()["image_url"]
    b = upload(client, image_path(second), png()).json()["image_url"]
    assert a == b and len(stored_files(media_root)) == 1


def test_permission_is_rechecked_after_the_image_is_processed(alice, bob, monkeypatch):
    """An editor removed while their upload was being decoded can't attach it afterwards."""
    shared_list = new_list(alice)
    ListMembership.objects.create(shared_list=shared_list, user=bob, role="editor")
    real_process = images.process

    def process_then_lose_access(data, kind, **kwargs):
        ListMembership.objects.filter(user=bob).delete()
        return real_process(data, kind, **kwargs)

    monkeypatch.setattr(images, "process", process_then_lose_access)
    assert upload(client_for(bob), image_path(shared_list), png()).status_code == 404
    assert SharedList.objects.get(pk=shared_list.pk).image is None


def test_cleanup_media_deletes_only_old_unreferenced_files(alice, media_root):
    shared_list = new_list(alice)
    link = link_services.add_link_on(shared_list, destination_url="https://example.com/a")
    kept_image = images.store(images.process(png(), images.IMAGE), images.IMAGE)
    tombstone_icon = images.store(images.process(png((40, 40)), images.ICON), images.ICON)
    unused_old = images.store(images.process(png((50, 50)), images.ICON), images.ICON)
    unused_new = images.store(images.process(png((60, 60)), images.ICON), images.ICON)
    SharedList.objects.filter(pk=shared_list.pk).update(image=kept_image)
    SharedLink.objects.filter(pk=link.pk).update(icon=tombstone_icon)
    link_services.delete_link_on(shared_list, link.pk)  # a tombstone keeps its icon
    leftover = media_root / "icons" / "ab" / "half-written.tmp"
    leftover.parent.mkdir(parents=True, exist_ok=True)
    leftover.write_bytes(b"partial")
    eight_days_ago = time.time() - 8 * 24 * 60 * 60
    for path in (kept_image, tombstone_icon, unused_old, "icons/ab/half-written.tmp"):
        os.utime(media_root / path, (eight_days_ago, eight_days_ago))

    call_command("cleanup_media", stdout=io.StringIO())

    remaining = {p.relative_to(media_root).as_posix() for p in stored_files(media_root)}
    assert remaining == {kept_image, tombstone_icon, unused_new}


def test_cleanup_media_without_a_media_directory(db, media_root):
    out = io.StringIO()
    call_command("cleanup_media", stdout=out)
    assert "Deleted 0" in out.getvalue()
