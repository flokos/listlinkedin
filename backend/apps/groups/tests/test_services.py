"""Group services: who may change what, the lists in a group, members, account erasure, and
row locks under concurrency."""

import threading
from datetime import timedelta

import pytest
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.services import purge_account
from apps.common import errors
from apps.groups import selectors, services
from apps.groups.models import Group, GroupList, GroupMembership
from apps.groups.services import CANNOT_ADD, MAX_LISTS_PER_GROUP
from apps.sharing.models import SharedList
from apps.sharing.policy import Role, Visibility
from apps.sharing.selectors import get_list_for
from apps.sharing.services import lists as list_services

from .conftest import as_, make_legacy_list, make_list, make_user, share


def codes(principal, group) -> list[str]:
    return [e.shared_list.public_code for e in selectors.entries_for(principal, group)]


def test_creating_a_group_needs_an_account(alice):
    with pytest.raises(errors.AuthenticationRequired):
        services.create_group(as_(None), title="Tools")
    group = services.create_group(as_(alice), title="Team tools!")
    assert (group.owner, group.visibility, group.slug) == (alice, "private", "team-tools")
    assert len(group.code) == 16


def test_group_codes_are_unique_and_retried_on_collision(alice, monkeypatch):
    first = services.create_group(as_(alice), title="One")
    generated = iter([first.code, "another-code-123"])
    monkeypatch.setattr("apps.shortener.generators.generate_short_code", lambda: next(generated))
    assert services.create_group(as_(alice), title="Two").code == "another-code-123"


def test_public_groups_need_a_verified_email(db):
    unverified = make_user("new@example.com", verified=False)
    with pytest.raises(errors.Forbidden):
        services.create_group(as_(unverified), title="Tools", visibility=Visibility.PUBLIC)
    group = services.create_group(as_(unverified), title="Tools")
    with pytest.raises(errors.Forbidden):
        services.update_group(as_(unverified), group.pk, {"visibility": Visibility.PUBLIC})
    services.update_group(as_(unverified), group.pk, {"visibility": Visibility.UNLISTED})
    group.refresh_from_db()
    assert group.visibility == "unlisted"


def test_editors_change_content_and_only_the_owner_changes_visibility(alice, bob, carol):
    group = services.create_group(as_(alice), title="Tools")
    GroupMembership.objects.create(group=group, user=bob, role="editor")
    GroupMembership.objects.create(group=group, user=carol, role="viewer")

    updated = services.update_group(as_(bob), group.pk, {"title": "Better tools"})
    assert (updated.title, updated.slug) == ("Better tools", "better-tools")
    with pytest.raises(errors.Forbidden):
        services.update_group(as_(bob), group.pk, {"visibility": Visibility.UNLISTED})
    with pytest.raises(errors.Forbidden):
        services.update_group(as_(carol), group.pk, {"description": "Mine now"})
    with pytest.raises(errors.NotVisible):  # private: outsiders can't tell it exists
        services.update_group(as_(make_user("dan@example.com")), group.pk, {"title": "x"})
    with pytest.raises(errors.Forbidden):
        services.delete_group(as_(bob), group.pk)


def test_deleting_a_group_leaves_its_lists_alone(alice):
    group = services.create_group(as_(alice), title="Tools")
    shared_list = make_list(alice)
    services.add_list(as_(alice), group.pk, shared_list.public_code)
    services.delete_group(as_(alice), group.pk)
    assert not Group.objects.exists() and not GroupList.objects.exists()
    assert SharedList.objects.filter(pk=shared_list.pk).exists()


# Adding lists.


def test_lists_are_appended_in_order(alice):
    group = services.create_group(as_(alice), title="Tools")
    lists = [make_list(alice) for _ in range(3)]
    for shared_list in lists:
        services.add_list(as_(alice), group.pk, shared_list.public_code)
    assert codes(as_(alice), group) == [lst.public_code for lst in lists]
    assert list(GroupList.objects.order_by("position").values_list("position", flat=True)) == [
        0,
        1,
        2,
    ]
    assert GroupList.objects.first().added_by == alice


def test_a_list_appears_at_most_once(alice):
    group = services.create_group(as_(alice), title="Tools")
    shared_list = make_list(alice)
    services.add_list(as_(alice), group.pk, shared_list.public_code)
    with pytest.raises(errors.Conflict) as caught:
        services.add_list(as_(alice), group.pk, shared_list.public_code)
    assert caught.value.code == "duplicate_list"


@pytest.mark.parametrize(
    ("visibility", "role", "outcome"),
    [
        ("private", None, errors.NotVisible),  # can't see it, can't tell it exists
        ("unlisted", None, errors.Forbidden),  # has the URL, but may not share it
        ("public", None, None),  # anyone may share a public list
        ("private", "viewer", errors.Forbidden),
        ("unlisted", "viewer", errors.Forbidden),
        ("private", "editor", None),
        ("unlisted", "editor", None),
    ],
)
def test_you_can_only_add_lists_you_could_share(alice, bob, visibility, role, outcome):
    group = services.create_group(as_(alice), title="Tools")
    shared_list = make_list(bob, visibility)
    if role:
        share(shared_list, alice, role)
    if outcome is None:
        services.add_list(as_(alice), group.pk, shared_list.public_code)
        assert GroupList.objects.filter(group=group, shared_list=shared_list).exists()
    else:
        with pytest.raises(outcome):
            services.add_list(as_(alice), group.pk, shared_list.public_code)
        assert not GroupList.objects.exists()


def test_group_viewers_cannot_add_and_unknown_codes_are_not_found(alice, bob):
    group = services.create_group(as_(alice), title="Tools")
    GroupMembership.objects.create(group=group, user=bob, role="viewer")
    with pytest.raises(errors.Forbidden):
        services.add_list(as_(bob), group.pk, make_list(bob).public_code)
    with pytest.raises(errors.NotVisible):
        services.add_list(as_(alice), group.pk, "no-such-code-000")


def test_a_refusal_on_the_group_comes_before_one_on_the_list(alice, bob):
    """Whichever row is locked first (ids decide), the group answers first, so a group viewer
    can't probe which lists are private."""
    for _ in range(4):  # enough draws to lock in both orders
        group = services.create_group(as_(alice), title="Tools")
        with pytest.raises(errors.NotVisible):  # bob can't see the private group
            services.add_list(as_(bob), group.pk, make_list(alice).public_code)
        GroupMembership.objects.create(group=group, user=bob, role="viewer")
        with pytest.raises(errors.Forbidden):
            services.add_list(as_(bob), group.pk, make_list(alice).public_code)


def test_legacy_lists_and_expired_lists_cannot_be_added(alice):
    group = services.create_group(as_(alice), title="Tools")
    with pytest.raises(errors.Forbidden):  # nobody has a role on an unclaimed list
        services.add_list(as_(alice), group.pk, make_legacy_list().public_code)
    expired = make_list(alice, expires_at=timezone.now() - timedelta(seconds=1))
    with pytest.raises(errors.Expired):
        services.add_list(as_(alice), group.pk, expired.public_code)


def test_a_group_holds_at_most_the_cap(alice):
    group = services.create_group(as_(alice), title="Tools")
    GroupList.objects.bulk_create(
        GroupList(group=group, shared_list=make_list(alice), position=n)
        for n in range(MAX_LISTS_PER_GROUP)
    )
    with pytest.raises(ValidationError):
        services.add_list(as_(alice), group.pk, make_list(alice).public_code)


# Removing and reordering.


def test_removing_a_list_closes_the_gap(alice):
    group = services.create_group(as_(alice), title="Tools")
    lists = [make_list(alice) for _ in range(3)]
    for shared_list in lists:
        services.add_list(as_(alice), group.pk, shared_list.public_code)
    services.remove_list(as_(alice), group.pk, lists[0].public_code)
    assert codes(as_(alice), group) == [lists[1].public_code, lists[2].public_code]
    assert sorted(GroupList.objects.values_list("position", flat=True)) == [0, 1]
    assert SharedList.objects.filter(pk=lists[0].pk).exists()


def test_a_deleted_list_leaves_a_gap_the_next_write_closes(alice):
    group = services.create_group(as_(alice), title="Tools")
    lists = [make_list(alice) for _ in range(3)]
    for shared_list in lists:
        services.add_list(as_(alice), group.pk, shared_list.public_code)
    lists[1].delete()
    assert codes(as_(alice), group) == [lists[0].public_code, lists[2].public_code]
    services.add_list(as_(alice), group.pk, make_list(alice).public_code)
    assert sorted(GroupList.objects.values_list("position", flat=True)) == [0, 1, 2]


def test_entries_you_are_not_shown_cannot_be_removed_or_moved(alice, bob):
    """bob edits the group but has no role on alice's private list in it: to him it isn't
    there, so removing or moving it answers like an unknown list."""
    group = services.create_group(as_(alice), title="Tools")
    GroupMembership.objects.create(group=group, user=bob, role="editor")
    private = make_list(alice)
    services.add_list(as_(alice), group.pk, private.public_code)
    for attempt in (
        lambda: services.remove_list(as_(bob), group.pk, private.public_code),
        lambda: services.move_list(as_(bob), group.pk, private.public_code, 0),
    ):
        with pytest.raises(errors.NotVisible):
            attempt()
    assert GroupList.objects.count() == 1


def test_moving_keeps_hidden_entries_in_place(alice, bob):
    """bob sees a, c and e; b and d (alice's private lists) stay exactly where they are."""
    group = services.create_group(as_(alice), title="Tools")
    GroupMembership.objects.create(group=group, user=bob, role="editor")
    a, c, e = (make_list(alice, "public", title=t) for t in "ace")
    b, d = (make_list(alice, title=t) for t in "bd")
    for shared_list in (a, b, c, d, e):
        services.add_list(as_(alice), group.pk, shared_list.public_code)

    services.move_list(as_(bob), group.pk, e.public_code, 0)

    assert [x.title for x in (e.shared_list for e in selectors.entries_for(as_(bob), group))] == [
        "e",
        "a",
        "c",
    ]
    assert [x.shared_list.title for x in selectors.entries_for(as_(alice), group)] == [
        "e",
        "b",
        "a",
        "d",
        "c",
    ]
    services.move_list(as_(bob), group.pk, e.public_code, 99)  # clamped to the end
    assert [x.shared_list.title for x in selectors.entries_for(as_(bob), group)] == ["a", "c", "e"]


def test_viewers_cannot_reorder_or_remove(alice, bob):
    group = services.create_group(as_(alice), title="Tools", visibility=Visibility.UNLISTED)
    shared_list = make_list(alice, "public")
    services.add_list(as_(alice), group.pk, shared_list.public_code)
    for principal in (as_(bob), as_(None)):
        with pytest.raises((errors.Forbidden, errors.AuthenticationRequired)):
            services.move_list(principal, group.pk, shared_list.public_code, 0)
        with pytest.raises((errors.Forbidden, errors.AuthenticationRequired)):
            services.remove_list(principal, group.pk, shared_list.public_code)


# Members.


def test_the_owner_adds_people_who_then_see_the_group(alice, bob):
    group = services.create_group(as_(alice), title="Tools")
    with pytest.raises(errors.NotVisible):
        selectors.get_group_for(as_(bob), group.code)
    services.add_member(as_(alice), group.pk, email="BOB@example.com", role=Role.EDITOR)
    _, access = selectors.get_group_for(as_(bob), group.code)
    assert access.facts.member_role is Role.EDITOR
    assert [g.code for g in selectors.groups_of(bob)] == [group.code]
    assert [g.code for g in selectors.groups_of(bob, role=Role.VIEWER)] == []


def test_adding_people_follows_the_list_rules(alice, bob):
    group = services.create_group(as_(alice), title="Tools")
    make_user("unverified@example.com", verified=False)
    for email in ("nobody@example.com", "unverified@example.com"):
        with pytest.raises(ValidationError) as caught:
            services.add_member(as_(alice), group.pk, email=email, role=Role.VIEWER)
        assert caught.value.detail["email"] == [CANNOT_ADD]
    with pytest.raises(ValidationError):
        services.add_member(as_(alice), group.pk, email="alice@example.com", role=Role.VIEWER)
    services.add_member(as_(alice), group.pk, email="bob@example.com", role=Role.VIEWER)
    with pytest.raises(ValidationError):
        services.add_member(as_(alice), group.pk, email="bob@example.com", role=Role.EDITOR)
    with pytest.raises(errors.Forbidden):  # members don't add people
        services.add_member(as_(bob), group.pk, email="alice@example.com", role=Role.VIEWER)

    unverified_owner = make_user("owner@example.com", verified=False)
    other = services.create_group(as_(unverified_owner), title="Mine")
    with pytest.raises(errors.Forbidden) as caught:
        services.add_member(as_(unverified_owner), other.pk, email="bob@example.com", role="viewer")
    assert caught.value.code == "email_unverified"


def test_roles_change_members_leave_and_owners_cannot(alice, bob, carol):
    group = services.create_group(as_(alice), title="Tools")
    services.add_member(as_(alice), group.pk, email="bob@example.com", role=Role.VIEWER)
    services.add_member(as_(alice), group.pk, email="carol@example.com", role=Role.VIEWER)
    services.change_role(as_(alice), group.pk, bob.pk, Role.EDITOR)
    assert GroupMembership.objects.get(user=bob).role == "editor"
    with pytest.raises(errors.Forbidden):
        services.change_role(as_(bob), group.pk, carol.pk, Role.EDITOR)
    with pytest.raises(errors.Forbidden):
        services.remove_member(as_(bob), group.pk, carol.pk)
    _, access = selectors.get_group_for(as_(bob), group.code)
    assert [m.user for m in selectors.members_of(group, access)] == [bob, carol]
    _, viewer_access = selectors.get_group_for(as_(carol), group.code)
    with pytest.raises(errors.Forbidden):
        selectors.members_of(group, viewer_access)

    services.remove_member(as_(carol), group.pk, carol.pk)  # leaving
    services.remove_member(as_(alice), group.pk, bob.pk)
    assert not GroupMembership.objects.exists()
    with pytest.raises(errors.Forbidden):
        services.remove_member(as_(alice), group.pk, alice.pk)


def test_a_group_role_grants_nothing_on_its_lists(alice, bob):
    group = services.create_group(as_(alice), title="Tools")
    private = make_list(alice)
    services.add_list(as_(alice), group.pk, private.public_code)
    services.add_member(as_(alice), group.pk, email="bob@example.com", role=Role.EDITOR)
    assert codes(as_(bob), group) == []
    with pytest.raises(errors.NotVisible):
        get_list_for(as_(bob), private.public_code)


# Account erasure.


def test_erasing_an_account_deletes_its_groups_and_memberships(alice, bob):
    mine = services.create_group(as_(alice), title="Mine")
    theirs = services.create_group(as_(bob), title="Theirs")
    services.add_member(as_(bob), theirs.pk, email="alice@example.com", role=Role.EDITOR)
    bobs_list = make_list(bob, "public")
    services.add_list(as_(bob), theirs.pk, bobs_list.public_code)
    services.add_list(as_(alice), theirs.pk, make_list(alice, "public").public_code)
    alice.deleted_at = timezone.now() - timedelta(days=31)
    alice.save()

    assert purge_account(alice.pk)

    assert not Group.objects.filter(pk=mine.pk).exists()
    assert not GroupMembership.objects.filter(user=alice).exists()
    # Her list left bob's group with her account; bob's own list stays.
    assert codes(as_(bob), theirs) == [bobs_list.public_code]


# Concurrency (real PostgreSQL row locks).


def _in_thread(target, results, key):
    def run():
        try:
            results[key] = target()
        except Exception as exc:  # noqa: BLE001 - the test reports whatever happened
            results[key] = exc
        finally:
            connection.close()

    return threading.Thread(target=run)


@pytest.mark.django_db(transaction=True)
def test_concurrent_adds_get_distinct_positions_and_respect_the_cap():
    owner = make_user("owner@example.com")
    group = services.create_group(as_(owner), title="Tools")
    GroupList.objects.bulk_create(
        GroupList(group=group, shared_list=make_list(owner), position=n)
        for n in range(MAX_LISTS_PER_GROUP - 3)
    )
    candidates = [make_list(owner) for _ in range(5)]
    results: dict = {}
    threads = [
        _in_thread(lambda c=c: services.add_list(as_(owner), group.pk, c.public_code), results, i)
        for i, c in enumerate(candidates)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    added = [r for r in results.values() if isinstance(r, GroupList)]
    refused = [r for r in results.values() if isinstance(r, ValidationError)]
    assert (len(added), len(refused)) == (3, 2)
    positions = sorted(GroupList.objects.filter(group=group).values_list("position", flat=True))
    assert positions == list(range(MAX_LISTS_PER_GROUP))


@pytest.mark.django_db(transaction=True)
def test_an_editor_removed_mid_add_cannot_commit_after_the_removal():
    owner, editor = make_user("owner@example.com"), make_user("editor@example.com")
    group = services.create_group(as_(owner), title="Tools")
    GroupMembership.objects.create(group=group, user=editor, role="editor")
    shared_list = make_list(editor, "public")
    removal_locked, results = threading.Event(), {}

    def add():
        removal_locked.wait()
        return services.add_list(as_(editor), group.pk, shared_list.public_code)

    writer = _in_thread(add, results, "add")
    writer.start()
    with transaction.atomic():
        services.remove_member(as_(owner), group.pk, editor.pk)
        removal_locked.set()
        writer.join(timeout=1)
        assert writer.is_alive(), "the add must wait for the removal's lock"
    writer.join(timeout=10)

    assert isinstance(results["add"], errors.NotVisible)  # private: he can't even see it now
    assert not GroupList.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_a_list_made_private_mid_add_is_not_added():
    """Adding locks the list too, so it serializes with a change of its visibility."""
    owner, author = make_user("owner@example.com"), make_user("author@example.com")
    group = services.create_group(as_(owner), title="Tools")
    shared_list = make_list(author, "public")
    change_locked, results = threading.Event(), {}

    def add():
        change_locked.wait()
        return services.add_list(as_(owner), group.pk, shared_list.public_code)

    writer = _in_thread(add, results, "add")
    writer.start()
    with transaction.atomic():
        list_services.update_list(as_(author), shared_list.pk, {"visibility": Visibility.PRIVATE})
        change_locked.set()
        writer.join(timeout=1)
        assert writer.is_alive(), "the add must wait for the list's lock"
    writer.join(timeout=10)

    assert isinstance(results["add"], errors.NotVisible)
    assert not GroupList.objects.exists()
