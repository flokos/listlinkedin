"""Suspending accounts (task 9.0, docs/v2/13-SECURITY.md#moderation): the operator's
`suspend_account` and `unsuspend_account`."""

import io

import pytest
from allauth.account.models import EmailAddress
from django.core.management import CommandError, call_command
from django.test import Client

from apps.accounts.models import User
from apps.groups import services as group_services
from apps.groups.models import Group
from apps.sharing.models import SharedList
from apps.sharing.selectors import Principal
from apps.sharing.services import lists as list_services

PASSWORD = "correct-horse-battery-staple-42"


@pytest.fixture
def ada(db) -> User:
    user = User.objects.create_user("ada@example.com", PASSWORD)
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    return user


def run(*args) -> str:
    out = io.StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


def signed_in(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


def test_a_suspended_account_is_signed_out_and_cannot_sign_in(ada):
    laptop = signed_in(ada)
    assert laptop.get("/api/v2/me/").status_code == 200

    assert "is suspended" in run("suspend_account", "ADA@example.com", "--reason", "phishing")
    assert laptop.get("/api/v2/me/").status_code == 401
    assert not Client().login(email=ada.email, password=PASSWORD)
    # allauth's own sign-in answers as for a wrong password: nothing more is revealed.
    response = Client().post(
        "/_allauth/browser/v1/auth/login",
        {"email": ada.email, "password": PASSWORD},
        content_type="application/json",
    )
    assert response.status_code == 400

    assert "can sign in again" in run("unsuspend_account", str(ada.pk), "--reason", "appeal")
    assert Client().login(email=ada.email, password=PASSWORD)
    assert laptop.get("/api/v2/me/").status_code == 401  # ended sessions stay ended


def test_unpublish_makes_the_accounts_lists_and_groups_private(ada):
    principal = Principal(user=ada)
    public_list = list_services.create_list(principal, title="Public")[0]
    private_list = list_services.create_list(principal, title="Private")[0]
    SharedList.objects.filter(pk=public_list.pk).update(visibility="public")
    group = group_services.create_group(principal, title="Portal")
    Group.objects.filter(pk=group.pk).update(visibility="unlisted")

    output = run("suspend_account", str(ada.pk), "--reason", "spam", "--unpublish")
    assert "1 lists and 1 groups are private now" in output
    assert set(SharedList.objects.values_list("visibility", flat=True)) == {"private"}
    assert Group.objects.get(pk=group.pk).visibility == "private"
    private_list.refresh_from_db()

    run("unsuspend_account", ada.email, "--reason", "appeal")
    public_list.refresh_from_db()
    assert public_list.visibility == "private"  # its owner decides again


def test_unknown_accounts_are_reported(db):
    with pytest.raises(CommandError, match="no account"):
        run("suspend_account", "nobody@example.com", "--reason", "spam")
    with pytest.raises(CommandError, match="no account"):
        run("unsuspend_account", "6f1c0d5e-0000-4000-8000-000000000000", "--reason", "spam")
