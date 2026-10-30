"""/api/v2/groups/ over HTTP (docs/v2/09-API-DESIGN.md#groups), including the leak tests:
a group never reveals a list its viewer may not see, in any field of any response
(docs/v2/15-TEST-STRATEGY.md)."""

import io
import os
import time

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client
from PIL import Image
from rest_framework.test import APIClient

from apps.groups import services
from apps.groups.models import Group, GroupList, GroupMembership
from apps.metadata import images
from apps.sharing.policy import Visibility
from apps.sharing.services import links as link_services
from apps.sharing.services import media as media_services
from config.middleware import UPLOAD_PATH

from .conftest import as_, make_list, make_user, share

URL = "/api/v2/groups/"
NOT_FOUND = {"detail": "Not found.", "code": "not_found"}


def client_for(user=None) -> APIClient:
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


def create(user, **data) -> dict:
    response = client_for(user).post(URL, {"title": "Team tools", **data}, format="json")
    assert response.status_code == 201, response.content
    return response.json()


def add(user, code, list_code):
    return client_for(user).post(f"{URL}{code}/lists/", {"list": list_code}, format="json")


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (800, 600), (200, 40, 40)).save(out, format="PNG")
    return out.getvalue()


# The group itself.


def test_creating_and_reading_a_group(alice):
    group = create(alice, description="Things we use")
    assert group == {
        "id": group["id"],
        "code": group["code"],
        "slug": "team-tools",
        "url": f"{settings.PUBLIC_BASE_URL}/g/{group['code']}/team-tools",
        "title": "Team tools",
        "description": "Things we use",
        "image_url": None,
        "visibility": "private",
        "tags": [],  # since 8.1
        "owner": {"display_name": "alice"},
        "created_at": group["created_at"],
        "updated_at": group["updated_at"],
        "list_count": 0,
        "my_role": "owner",
        "permissions": [
            "view",
            "edit",
            "add_list",
            "view_members",
            "settings",
            "members",
            "delete",
        ],
    }
    assert client_for(alice).get(f"{URL}{group['code']}/").json() == group


def test_groups_need_an_account(db):
    assert client_for().post(URL, {"title": "x"}, format="json").status_code == 401
    assert client_for().get(URL).status_code == 401


def test_a_private_group_answers_like_an_unknown_one(alice, bob):
    code = create(alice)["code"]
    for path in (f"{URL}{code}/", f"{URL}{code}/lists/"):
        for client in (client_for(), client_for(bob)):
            response = client.get(path)
            assert (response.status_code, response.json()) == (404, NOT_FOUND)
    unknown = client_for(bob).get(f"{URL}no-such-group-00/")
    assert (unknown.status_code, unknown.json()) == (404, NOT_FOUND)


def test_unlisted_and_public_groups_can_be_viewed_by_anyone_with_the_code(alice):
    unlisted = create(alice, visibility="unlisted")
    public = create(alice, visibility="public")
    for group in (unlisted, public):
        body = client_for().get(f"{URL}{group['code']}/").json()
        # Visitors may report a group to the operator (since 9.0).
        assert body["permissions"] == ["view", "report"] and body["my_role"] is None
    # Owner names: on public groups only, for people without a role.
    assert client_for().get(f"{URL}{unlisted['code']}/").json()["owner"] is None
    assert client_for().get(f"{URL}{public['code']}/").json()["owner"] == {"display_name": "alice"}


def test_public_groups_need_a_verified_email(db):
    user = make_user("new@example.com", verified=False)
    response = client_for(user).post(URL, {"title": "x", "visibility": "public"}, format="json")
    assert response.status_code == 400
    assert "visibility" in response.json()


def test_my_groups_with_roles(alice, bob):
    mine = create(alice)["code"]
    theirs = create(bob)["code"]
    GroupMembership.objects.create(group=Group.objects.get(code=theirs), user=alice, role="viewer")
    listed = client_for(alice).get(URL).json()["results"]
    assert {g["code"]: g["my_role"] for g in listed} == {mine: "owner", theirs: "viewer"}
    owned = client_for(alice).get(URL, {"role": "owner"}).json()["results"]
    assert [g["code"] for g in owned] == [mine]
    assert client_for(alice).get(URL, {"role": "boss"}).status_code == 400


def test_editing_and_deleting(alice, bob):
    code = create(alice)["code"]
    group = Group.objects.get(code=code)
    GroupMembership.objects.create(group=group, user=bob, role="editor")
    response = client_for(bob).patch(f"{URL}{code}/", {"title": "Renamed"}, format="json")
    assert (response.status_code, response.json()["slug"]) == (200, "renamed")
    response = client_for(bob).patch(f"{URL}{code}/", {"visibility": "unlisted"}, format="json")
    assert response.status_code == 403
    assert client_for(bob).delete(f"{URL}{code}/").status_code == 403
    assert client_for(alice).delete(f"{URL}{code}/").status_code == 204
    assert not Group.objects.exists()


def test_writes_need_the_csrf_token(alice):
    browser = Client(enforce_csrf_checks=True)
    browser.force_login(alice)
    response = browser.post(URL, {"title": "x"}, content_type="application/json")
    assert response.status_code == 403
    assert not Group.objects.exists()


# The lists in a group.


def test_adding_listing_reordering_and_removing_lists(alice):
    code = create(alice)["code"]
    first, second = make_list(alice, title="First"), make_list(alice, "public", title="Second")
    response = add(alice, code, first.public_code)
    assert response.status_code == 201, response.content
    item = response.json()
    assert (item["code"], item["title"], item["my_role"], item["shown_to_all"]) == (
        first.public_code,
        "First",
        "owner",
        False,  # private: other group members don't see it
    )
    assert "position" not in item  # stored positions never leave the server
    add(alice, code, second.public_code)
    lists = client_for(alice).get(f"{URL}{code}/lists/").json()
    assert [lst["title"] for lst in lists] == ["First", "Second"]
    assert [lst["shown_to_all"] for lst in lists] == [False, True]

    response = client_for(alice).post(
        f"{URL}{code}/reorder/", {"list": second.public_code, "to_index": 0}, format="json"
    )
    assert [lst["title"] for lst in response.json()] == ["Second", "First"]

    assert client_for(alice).delete(f"{URL}{code}/lists/{second.public_code}/").status_code == 204
    assert [lst["title"] for lst in client_for(alice).get(f"{URL}{code}/lists/").json()] == [
        "First"
    ]
    assert client_for(alice).get(f"{URL}{code}/").json()["list_count"] == 1


def test_adding_errors(alice, bob):
    code = create(alice)["code"]
    own = make_list(alice)
    add(alice, code, own.public_code)
    duplicate = add(alice, code, own.public_code)
    assert (duplicate.status_code, duplicate.json()["code"]) == (409, "duplicate_list")
    unlisted = add(alice, code, make_list(bob, "unlisted").public_code)
    assert (unlisted.status_code, unlisted.json()["code"]) == (403, "cannot_share_list")
    private = add(alice, code, make_list(bob).public_code)
    assert (private.status_code, private.json()) == (404, NOT_FOUND)
    assert add(alice, code, "no-such-list-000").status_code == 404
    assert client_for(alice).post(f"{URL}{code}/lists/", {}, format="json").status_code == 400


VIEWERS = ["anonymous", "signed in", "group viewer", "group editor", "list viewer"]


@pytest.fixture
def leak_world(db):
    """A group of each visibility holding a private, an unlisted and a public list by
    someone else, and one user per kind of viewer."""
    owner, author = make_user("owner@example.com"), make_user("author@example.com")
    users = {v: make_user(f"{v.replace(' ', '-')}@example.com") for v in VIEWERS[1:]}
    users["anonymous"] = None
    lists = {v: make_list(author, v.value, title=f"SECRET-{v.value}") for v in Visibility}
    for shared_list in lists.values():
        share(shared_list, users["list viewer"], "viewer")
    groups = {}
    for v in Visibility:
        group = services.create_group(as_(owner), title=f"Group {v.value}")
        Group.objects.filter(pk=group.pk).update(visibility=v.value)
        for n, shared_list in enumerate(lists.values()):
            GroupList.objects.create(group=group, shared_list=shared_list, position=n * 3)
        for role in ("viewer", "editor"):
            GroupMembership.objects.create(group=group, user=users[f"group {role}"], role=role)
        groups[v] = Group.objects.get(pk=group.pk)
    return groups, lists, users


def expected_titles(viewer: str, group_visibility: Visibility) -> list[str]:
    if viewer == "list viewer":
        return ["SECRET-private", "SECRET-unlisted", "SECRET-public"]
    if group_visibility is Visibility.PUBLIC:
        return ["SECRET-public"]
    return ["SECRET-unlisted", "SECRET-public"]


@pytest.mark.parametrize("viewer", VIEWERS)
@pytest.mark.parametrize("group_visibility", list(Visibility))
def test_hidden_lists_leave_no_trace(leak_world, viewer, group_visibility):
    groups, lists, users = leak_world
    group, client = groups[group_visibility], client_for(users[viewer])
    detail = client.get(f"{URL}{group.code}/")
    if group_visibility is Visibility.PRIVATE and viewer not in ("group viewer", "group editor"):
        assert (detail.status_code, detail.json()) == (404, NOT_FOUND)
        assert client.get(f"{URL}{group.code}/lists/").json() == NOT_FOUND
        return
    entries = client.get(f"{URL}{group.code}/lists/")
    titles = expected_titles(viewer, group_visibility)
    assert [lst["title"] for lst in entries.json()] == titles
    assert detail.json()["list_count"] == len(titles)
    hidden = {lst for lst in lists.values() if lst.title not in titles}
    bodies = detail.content.decode() + entries.content.decode()
    if users[viewer] is not None:
        bodies += client.get(URL).content.decode()  # "my groups" counts too
    for shared_list in hidden:
        assert shared_list.title not in bodies
        assert shared_list.public_code not in bodies
        assert str(shared_list.pk) not in bodies


def test_a_group_editor_cannot_touch_lists_hidden_from_them(leak_world):
    groups, lists, users = leak_world
    group, editor = groups[Visibility.PUBLIC], client_for(users["group editor"])
    private = lists[Visibility.PRIVATE]
    for response in (
        editor.delete(f"{URL}{group.code}/lists/{private.public_code}/"),
        editor.post(
            f"{URL}{group.code}/reorder/",
            {"list": private.public_code, "to_index": 0},
            format="json",
        ),
    ):
        assert response.status_code == 404
        assert response.json()["detail"] == services.NOT_IN_GROUP
    assert GroupList.objects.filter(group=group).count() == 3


def test_my_groups_count_only_what_i_am_shown(leak_world):
    groups, lists, users = leak_world
    listed = client_for(users["group viewer"]).get(URL).json()["results"]
    assert {g["visibility"]: g["list_count"] for g in listed} == {
        "private": 2,
        "unlisted": 2,
        "public": 1,
    }


# Image.


def test_the_group_image(alice, bob, media_root):
    code = create(alice, visibility="unlisted")["code"]
    path = f"{URL}{code}/image/"
    assert UPLOAD_PATH.match(path)  # allowed a larger body by the middleware (and nginx)

    def put(user):
        file = SimpleUploadedFile("picture.png", png(), content_type="image/png")
        return client_for(user).put(path, {"file": file}, format="multipart")

    assert put(None).status_code == 401
    assert put(bob).status_code == 403  # can view the unlisted group, can't edit it
    response = put(alice)
    assert response.status_code == 200, response.content
    image_url = response.json()["image_url"]
    assert image_url.startswith("/media/images/") and image_url.endswith(".webp")
    assert (media_root / image_url.removeprefix("/media/")).is_file()
    assert client_for(alice).delete(path).status_code == 204
    assert Group.objects.get(code=code).image is None


def test_a_non_image_is_refused(alice):
    code = create(alice)["code"]
    file = SimpleUploadedFile("x.png", b"<svg/>", content_type="image/png")
    response = client_for(alice).put(f"{URL}{code}/image/", {"file": file}, format="multipart")
    assert response.status_code == 400 and "file" in response.json()


def test_cleanup_media_keeps_group_images_and_icons_in_revisions(alice, media_root):
    group_image = images.store(images.process(png(), images.IMAGE), images.IMAGE)
    Group.objects.filter(pk=services.create_group(as_(alice), title="x").pk).update(
        image=group_image
    )
    shared_list = make_list(alice)
    link, _ = link_services.add_link(
        as_(alice), shared_list.pk, destination_url="https://example.com/a"
    )
    small = io.BytesIO()
    Image.new("RGB", (40, 40), (1, 2, 3)).save(small, format="PNG")
    media_services.set_link_icon(as_(alice), shared_list.pk, link.pk, small.getvalue())
    old_icon = type(link).objects.get(pk=link.pk).icon
    media_services.set_link_icon(as_(alice), shared_list.pk, link.pk, None)  # only history has it
    unused = images.store(images.process(png(), images.ICON), images.ICON)
    week_ago = time.time() - 8 * 24 * 60 * 60
    for path in (group_image, old_icon, unused):
        os.utime(media_root / path, (week_ago, week_ago))

    call_command("cleanup_media", stdout=io.StringIO())

    assert (media_root / group_image).is_file()
    assert (media_root / old_icon).is_file()  # restoring that revision brings it back
    assert not (media_root / unused).exists()


# Members.


def test_members_over_http(alice, bob, carol):
    code = create(alice)["code"]
    members = f"{URL}{code}/members/"
    response = client_for(alice).post(
        members, {"email": "bob@example.com", "role": "editor"}, format="json"
    )
    assert response.status_code == 201, response.content
    assert response.json()["email_hint"] == "b…@example.com"
    client_for(alice).post(members, {"email": "carol@example.com", "role": "viewer"}, format="json")

    listed = client_for(bob).get(members)
    assert [m["display_name"] for m in listed.json()["results"]] == ["bob", "carol"]
    assert "bob@example.com" not in listed.content.decode()
    assert client_for(carol).get(members).status_code == 403  # viewers can't see members

    path = f"{members}{carol.pk}/"
    assert client_for(bob).patch(path, {"role": "editor"}, format="json").status_code == 403
    assert client_for(alice).patch(path, {"role": "editor"}, format="json").status_code == 200
    assert client_for(carol).delete(path).status_code == 204  # leaving
    assert client_for(alice).delete(f"{members}{alice.pk}/").status_code == 403
    assert client_for().get(members).status_code == 401


def test_a_groups_lists_take_a_fixed_number_of_queries(alice, django_assert_max_num_queries):
    code = create(alice)["code"]
    group = Group.objects.get(code=code)
    for n in range(12):
        shared_list = make_list(alice, "public" if n % 2 else "private")
        GroupList.objects.create(group=group, shared_list=shared_list, position=n)
    with django_assert_max_num_queries(6):
        response = client_for(alice).get(f"{URL}{code}/lists/")
    assert len(response.json()) == 12
