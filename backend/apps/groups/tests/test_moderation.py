"""Moderation of groups (task 9.0, docs/v2/13-SECURITY.md#moderation): reports and the
operator's commands."""

import io

import pytest
from django.core.management import CommandError, call_command
from rest_framework.test import APIClient

from apps.groups import services
from apps.groups.models import Group, GroupMembership

from .conftest import as_, make_list, make_user

URL = "/api/v2/groups/"
MODERATION = "moderation@example.test"


@pytest.fixture(autouse=True)
def moderation_address(settings):
    settings.MODERATION_EMAIL = MODERATION


@pytest.fixture
def alice(db):
    return make_user("alice@example.com")


@pytest.fixture
def bob(db):
    return make_user("bob@example.com")


def client_for(user=None) -> APIClient:
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


def make_group(owner, visibility="public") -> Group:
    group = services.create_group(as_(owner), title="Team portal")
    Group.objects.filter(pk=group.pk).update(visibility=visibility)
    group.refresh_from_db()
    return group


def report(client: APIClient, code: str, data=None):
    data = data or {"reason": "spam", "details": "Ads everywhere"}
    return client.post(f"{URL}{code}/report/", data, format="json")


def test_anyone_who_can_see_a_group_may_report_it(alice, bob, mailoutbox):
    group = make_group(alice)
    assert report(client_for(), group.code).status_code == 202
    assert report(client_for(bob), group.code).status_code == 202
    first, second = mailoutbox
    assert first.subject == "[listlinkedin] Report: Spam, group “Team portal”"
    for expected in (
        f"Code: {group.code}",
        f"/g/{group.code}/team-portal",
        f"Owner: user {alice.pk}",
        "Details: Ads everywhere",
        f"python manage.py unpublish_group {group.code}",
    ):
        assert expected in first.body, expected
    assert f"Reported by: user {bob.pk}" in second.body
    assert client_for().get(f"{URL}{group.code}/").json()["permissions"] == ["view", "report"]


def test_owners_cannot_report_and_private_groups_stay_hidden(alice, bob, mailoutbox):
    public = make_group(alice)
    assert report(client_for(alice), public.code).status_code == 403
    assert "report" not in client_for(alice).get(f"{URL}{public.code}/").json()["permissions"]
    private = make_group(alice, "private")
    assert report(client_for(bob), private.code).status_code == 404
    GroupMembership.objects.create(group=private, user=bob, role="viewer")
    assert report(client_for(bob), private.code).status_code == 202
    assert len(mailoutbox) == 1


def run(*args) -> str:
    out = io.StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


def test_unpublish_group_makes_it_private(alice):
    group = make_group(alice)
    assert "is private now" in run("unpublish_group", group.code, "--reason", "spam")
    group.refresh_from_db()
    assert group.visibility == "private"
    assert client_for().get(f"{URL}{group.code}/").status_code == 404
    with pytest.raises(CommandError, match="no group"):
        run("unpublish_group", "no-such-group-00", "--reason", "spam")


def test_delete_group_keeps_its_lists(alice):
    group = make_group(alice)
    shared_list = make_list(alice, "public")
    services.add_list(as_(alice), group.pk, shared_list.public_code)
    with pytest.raises(CommandError, match="Add --yes"):
        run("delete_group", group.code, "--reason", "spam")
    assert "Its lists are untouched" in run("delete_group", group.code, "--reason", "spam", "--yes")
    assert not Group.objects.filter(pk=group.pk).exists()
    shared_list.refresh_from_db()  # still there
