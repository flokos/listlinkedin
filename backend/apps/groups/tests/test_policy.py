"""The group permission matrix and the display rule, as pure functions
(docs/v2/12-AUTHORIZATION.md#group-permission-matrix)."""

import uuid

import pytest

from apps.sharing.policy import (
    Actor,
    GroupAction,
    GroupFacts,
    ListFacts,
    Role,
    Visibility,
    can_add_list,
    can_group,
    can_set_group_visibility,
    shown_in_group,
)

OWNER, OTHER = uuid.uuid4(), uuid.uuid4()
GROUP_ROLES = ["anonymous", "no role", "viewer", "editor", "owner"]

# Who may take each action, by role on the group (✓ in the matrix).
ALLOWED = {
    GroupAction.EDIT: {"editor", "owner"},
    GroupAction.ADD_LIST: {"editor", "owner"},
    GroupAction.VIEW_MEMBERS: {"editor", "owner"},
    GroupAction.SETTINGS: {"owner"},
    GroupAction.MEMBERS: {"owner"},
    GroupAction.DELETE: {"owner"},
    GroupAction.LEAVE: {"viewer", "editor"},
}


def actor_and_facts(group_role: str, visibility=Visibility.PRIVATE, verified=False):
    actor = Actor() if group_role == "anonymous" else Actor(user_id=OTHER, email_verified=verified)
    facts = GroupFacts(
        id=uuid.uuid4(),
        owner_id=OTHER if group_role == "owner" else OWNER,
        visibility=visibility,
        member_role=Role(group_role) if group_role in ("viewer", "editor") else None,
    )
    return actor, facts


@pytest.mark.parametrize("visibility", list(Visibility))
@pytest.mark.parametrize("group_role", GROUP_ROLES)
def test_viewing_follows_the_group_visibility(group_role, visibility):
    actor, facts = actor_and_facts(group_role, visibility)
    expected = visibility is not Visibility.PRIVATE or group_role in ("viewer", "editor", "owner")
    assert can_group(actor, GroupAction.VIEW, facts) is expected


@pytest.mark.parametrize("action", list(ALLOWED))
@pytest.mark.parametrize("visibility", list(Visibility))
@pytest.mark.parametrize("group_role", GROUP_ROLES)
def test_the_group_permission_matrix(group_role, visibility, action):
    actor, facts = actor_and_facts(group_role, visibility)
    assert can_group(actor, action, facts) is (group_role in ALLOWED[action])


def test_making_a_group_public_needs_a_verified_email():
    actor, facts = actor_and_facts("owner")
    assert not can_set_group_visibility(actor, facts, Visibility.PUBLIC)
    assert can_set_group_visibility(actor, facts, Visibility.UNLISTED)
    verified, facts = actor_and_facts("owner", verified=True)
    assert can_set_group_visibility(verified, facts, Visibility.PUBLIC)
    editor, facts = actor_and_facts("editor", verified=True)
    assert not can_set_group_visibility(editor, facts, Visibility.UNLISTED)


LIST_ROLES = ["no role", "viewer", "editor", "owner"]  # edit links retired in 9.6


def list_facts(list_role: str, visibility: Visibility) -> ListFacts:
    list_id = uuid.uuid4()
    return ListFacts(
        id=list_id,
        owner_id=OTHER if list_role == "owner" else OWNER,
        visibility=visibility,
        member_role=Role(list_role) if list_role in ("viewer", "editor") else None,
    )


@pytest.mark.parametrize("list_visibility", list(Visibility))
@pytest.mark.parametrize("list_role", LIST_ROLES)
@pytest.mark.parametrize("group_role", GROUP_ROLES)
def test_adding_a_list_needs_group_edit_and_the_right_to_share_the_list(
    group_role, list_role, list_visibility
):
    actor, group = actor_and_facts(group_role)
    facts = list_facts(list_role, list_visibility)
    expected = group_role in ("editor", "owner") and (
        list_role in ("editor", "owner") or list_visibility is Visibility.PUBLIC
    )
    assert can_add_list(actor, group, facts) is expected


# (list visibility, group visibility) pairs a group shows to a viewer with no role on the list.
SHOWN_WITHOUT_ROLE = {
    ("public", "private"),
    ("public", "unlisted"),
    ("public", "public"),
    ("unlisted", "private"),
    ("unlisted", "unlisted"),
}


@pytest.mark.parametrize("group_visibility", list(Visibility))
@pytest.mark.parametrize("list_visibility", list(Visibility))
@pytest.mark.parametrize("has_list_role", [False, True])
def test_which_lists_a_group_shows(has_list_role, list_visibility, group_visibility):
    expected = has_list_role or (list_visibility, group_visibility) in SHOWN_WITHOUT_ROLE
    shown = shown_in_group(
        has_list_role=has_list_role,
        list_visibility=list_visibility,
        group_visibility=group_visibility,
    )
    assert shown is expected


def test_a_public_group_never_shows_private_or_unlisted_lists_to_visitors():
    for list_visibility in (Visibility.PRIVATE, Visibility.UNLISTED):
        assert not shown_in_group(
            has_list_role=False, list_visibility=list_visibility, group_visibility=Visibility.PUBLIC
        )
