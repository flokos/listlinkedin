"""The permission policy, as a table (docs/v2/12-AUTHORIZATION.md). No database."""

import ast
import uuid
from pathlib import Path

import pytest

from apps.sharing.policy import (
    Action,
    Actor,
    ListFacts,
    Role,
    Visibility,
    can,
    can_set_visibility,
    permissions,
)

OWNER, OTHER = uuid.uuid4(), uuid.uuid4()
LIST_ID = uuid.uuid4()


def facts(visibility=Visibility.PRIVATE, *, owner=OWNER, role=None, fork=False, branch=False):
    return ListFacts(
        id=LIST_ID,
        owner_id=owner,
        visibility=visibility,
        allow_fork=fork,
        allow_branch=branch,
        member_role=role,
    )


ANON = Actor()
SIGNED_IN = Actor(user_id=OTHER)
OWNER_ACTOR = Actor(user_id=OWNER)
TOKEN = Actor(legacy_list_id=LIST_ID)


@pytest.mark.parametrize(
    ("actor", "role", "visibility", "expected"),
    [
        (ANON, None, Visibility.PRIVATE, False),
        (ANON, None, Visibility.UNLISTED, True),
        (ANON, None, Visibility.PUBLIC, True),
        (SIGNED_IN, None, Visibility.PRIVATE, False),
        (SIGNED_IN, Role.VIEWER, Visibility.PRIVATE, True),
        (SIGNED_IN, Role.EDITOR, Visibility.PRIVATE, True),
        (OWNER_ACTOR, None, Visibility.PRIVATE, True),
    ],
)
def test_view(actor, role, visibility, expected):
    assert can(actor, Action.VIEW, facts(visibility, role=role)) is expected


@pytest.mark.parametrize(
    ("actor", "role", "edit", "owner_only", "delete"),
    [
        (ANON, None, False, False, False),
        (SIGNED_IN, None, False, False, False),
        (SIGNED_IN, Role.VIEWER, False, False, False),
        (SIGNED_IN, Role.EDITOR, True, False, False),
        (OWNER_ACTOR, None, True, True, True),
    ],
)
def test_edit_settings_delete_by_role(actor, role, edit, owner_only, delete):
    f = facts(Visibility.UNLISTED, role=role)
    assert can(actor, Action.EDIT, f) is edit
    assert can(actor, Action.VIEW_HISTORY, f) is edit
    assert can(actor, Action.SETTINGS, f) is owner_only
    assert can(actor, Action.MEMBERS, f) is owner_only
    assert can(actor, Action.DELETE, f) is delete


def test_anonymous_role_is_ignored():
    # A membership role means nothing without a signed-in user.
    assert not can(ANON, Action.EDIT, facts(role=Role.EDITOR))


def test_legacy_token_has_v1_rights_on_its_own_list_only():
    legacy = facts(Visibility.UNLISTED, owner=None)
    assert can(TOKEN, Action.EDIT, legacy)
    assert can(TOKEN, Action.DELETE, legacy)
    assert can(TOKEN, Action.ROTATE_TOKEN, legacy)
    assert not can(TOKEN, Action.SETTINGS, legacy)
    assert not can(TOKEN, Action.MEMBERS, legacy)
    assert not can(TOKEN, Action.CLAIM, legacy)  # claiming also needs an account
    assert can(Actor(user_id=OTHER, legacy_list_id=LIST_ID), Action.CLAIM, legacy)

    other_list = ListFacts(id=uuid.uuid4(), owner_id=None, visibility=Visibility.UNLISTED)
    assert not can(TOKEN, Action.EDIT, other_list)
    # Once claimed (an owner exists), the token is worthless.
    assert not can(TOKEN, Action.EDIT, facts(Visibility.UNLISTED))


@pytest.mark.parametrize("action", [Action.FORK, Action.BRANCH])
def test_fork_and_branch_need_an_account_view_access_and_permission(action):
    allowed = facts(Visibility.PUBLIC, fork=True, branch=True)
    assert can(SIGNED_IN, action, allowed)
    assert not can(ANON, action, allowed)
    assert not can(SIGNED_IN, action, facts(Visibility.PUBLIC))
    assert not can(SIGNED_IN, action, facts(Visibility.PRIVATE, fork=True, branch=True))
    assert can(OWNER_ACTOR, action, facts(Visibility.PRIVATE))


def test_making_a_list_public_needs_the_owner_with_a_verified_email():
    f = facts(Visibility.PRIVATE)
    assert can_set_visibility(OWNER_ACTOR, f, Visibility.UNLISTED)
    assert not can_set_visibility(OWNER_ACTOR, f, Visibility.PUBLIC)
    verified = Actor(user_id=OWNER, email_verified=True)
    assert can_set_visibility(verified, f, Visibility.PUBLIC)
    assert not can_set_visibility(
        Actor(user_id=OTHER, email_verified=True), facts(role=Role.EDITOR), Visibility.UNLISTED
    )


def test_permissions_list_what_the_ui_may_offer():
    assert permissions(ANON, facts(Visibility.UNLISTED)) == ["view"]
    assert "settings" in permissions(OWNER_ACTOR, facts())
    assert "leave" in permissions(SIGNED_IN, facts(role=Role.VIEWER))


def test_policy_module_does_not_depend_on_django():
    source = (Path(__file__).parents[1] / "policy.py").read_text()
    modules = {
        (node.module if isinstance(node, ast.ImportFrom) else alias.name).split(".")[0]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert not modules & {"django", "rest_framework"}, modules
