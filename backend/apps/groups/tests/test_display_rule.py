"""The lists a group shows, in SQL, agree with `policy.shown_in_group` for every viewer, list
visibility and group visibility, and hidden lists leave no trace in counts or order
(docs/v2/12-AUTHORIZATION.md#which-lists-a-group-shows-to-a-viewer)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.groups import selectors
from apps.groups.models import Group, GroupList, GroupMembership
from apps.sharing.policy import Visibility, shown_in_group

from .conftest import as_, make_list, make_user, share

VIEWERS = ["anonymous", "signed in", "group viewer", "group editor", "list viewer", "list editor"]


@pytest.fixture
def world(db):
    """One group of each visibility, owned by `owner`, each holding one list of each
    visibility owned by `author`, and one user per kind of viewer."""
    owner, author = make_user("owner@example.com"), make_user("author@example.com")
    lists = {v: make_list(author, v.value, title=f"{v.value} list") for v in Visibility}
    users = {name: make_user(f"{name.replace(' ', '-')}@example.com") for name in VIEWERS[1:]}
    users["anonymous"] = None
    for shared_list in lists.values():
        share(shared_list, users["list viewer"], "viewer")
        share(shared_list, users["list editor"], "editor")
    groups = {}
    for v in Visibility:
        group = Group.objects.create(
            code=f"group-{v.value}", owner=owner, title=v.value, visibility=v.value
        )
        for position, shared_list in enumerate(lists.values()):
            GroupList.objects.create(group=group, shared_list=shared_list, position=position)
        GroupMembership.objects.create(group=group, user=users["group viewer"], role="viewer")
        GroupMembership.objects.create(group=group, user=users["group editor"], role="editor")
        groups[v] = group
    return groups, lists, users


@pytest.mark.parametrize("viewer", VIEWERS)
@pytest.mark.parametrize("group_visibility", list(Visibility))
def test_sql_and_policy_agree(world, viewer, group_visibility):
    groups, lists, users = world
    group = groups[group_visibility]
    user = users[viewer]
    has_list_role = viewer in ("list viewer", "list editor")
    expected = [
        lst.public_code
        for v, lst in lists.items()
        if shown_in_group(
            has_list_role=has_list_role, list_visibility=v, group_visibility=group_visibility
        )
    ]
    shown = selectors.entries_for(as_(user), group)
    assert [entry.shared_list.public_code for entry in shown] == expected


@pytest.mark.parametrize("viewer", VIEWERS)
def test_a_public_group_shows_only_public_lists_to_people_without_a_list_role(world, viewer):
    groups, lists, users = world
    titles = [
        e.shared_list.title
        for e in selectors.entries_for(as_(users[viewer]), groups[Visibility.PUBLIC])
    ]
    if viewer in ("list viewer", "list editor"):
        assert titles == ["private list", "unlisted list", "public list"]
    else:
        assert titles == ["public list"]  # no placeholder, no gap, nothing about the others


def test_my_groups_count_only_the_lists_shown_to_me(world):
    groups, lists, users = world
    counts = {g.visibility: g.list_count for g in selectors.groups_of(users["group viewer"])}
    assert counts == {"private": 2, "unlisted": 2, "public": 1}
    editor_counts = {g.visibility: g.list_count for g in selectors.groups_of(users["group editor"])}
    assert editor_counts == counts  # a group role grants nothing on the lists (G2)


def test_the_owner_of_a_group_sees_only_what_the_rule_shows_them(world):
    groups, lists, users = world
    owner = groups[Visibility.PRIVATE].owner
    assert {g.visibility: g.list_count for g in selectors.groups_of(owner)} == {
        "private": 2,
        "unlisted": 2,
        "public": 1,
    }


def test_expired_lists_and_lists_of_deleting_owners_are_never_shown(world):
    groups, lists, users = world
    group = groups[Visibility.PRIVATE]
    viewer = users["list editor"]
    lists[Visibility.PUBLIC].expires_at = timezone.now() - timedelta(seconds=1)
    lists[Visibility.PUBLIC].save()
    assert [e.shared_list.title for e in selectors.entries_for(as_(viewer), group)] == [
        "private list",
        "unlisted list",
    ]
    author = lists[Visibility.PRIVATE].owner
    author.deleted_at = timezone.now()
    author.save()
    assert not selectors.entries_for(as_(viewer), group).exists()


def test_viewing_a_group(world):
    groups, lists, users = world
    for visibility, group in groups.items():
        for viewer in ("anonymous", "signed in"):
            if visibility is Visibility.PRIVATE:
                with pytest.raises(Exception, match="Not found"):
                    selectors.get_group_for(as_(users[viewer]), group.code)
            else:
                assert selectors.get_group_for(as_(users[viewer]), group.code)[0] == group
        assert selectors.get_group_for(as_(users["group viewer"]), group.code)[0] == group


def test_unlisted_groups_of_other_people_are_never_enumerated(world):
    groups, lists, users = world
    assert not selectors.groups_of(users["signed in"]).exists()
    assert not selectors.groups_of(users["list editor"]).exists()  # list roles don't count


def test_groups_of_a_deleting_owner_are_hidden(world):
    groups, lists, users = world
    owner = groups[Visibility.PUBLIC].owner
    owner.deleted_at = timezone.now()
    owner.save()
    with pytest.raises(Exception, match="Not found"):
        selectors.get_group_for(as_(None), groups[Visibility.PUBLIC].code)
    assert not selectors.groups_of(users["group viewer"]).exists()
