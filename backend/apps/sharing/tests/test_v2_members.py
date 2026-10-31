"""/api/v2/lists/{code}/members/, and the list permission matrix over HTTP
(docs/v2/12-AUTHORIZATION.md#list-permission-matrix)."""

import threading

import pytest
from allauth.account.models import EmailAddress
from django.db import connection, transaction
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import User
from apps.sharing.models import ListMembership, SharedLink, SharedList
from apps.sharing.selectors import Principal
from apps.sharing.services import links as link_services
from apps.sharing.services import members as member_services
from apps.sharing.services.members import CANNOT_ADD

URL = "/api/v2/lists/"


def make_user(email: str, *, verified: bool = True) -> User:
    user = User.objects.create_user(email, "pw-correct-horse-1", display_name=email.split("@")[0])
    EmailAddress.objects.create(user=user, email=email, verified=verified, primary=True)
    return user


@pytest.fixture
def alice(db):
    return make_user("alice@example.com")


@pytest.fixture
def bob(db):
    return make_user("bob@example.com")


@pytest.fixture
def carol(db):
    return make_user("carol@example.com")


def client_for(user=None) -> APIClient:
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


def create(user, **data) -> str:
    response = client_for(user).post(URL, {"title": "Team", **data}, format="json")
    assert response.status_code == 201, response.content
    return response.json()["code"]


def members_url(code: str, user=None) -> str:
    return f"{URL}{code}/members/" + (f"{user.pk}/" if user else "")


def add(owner, code, email, role="viewer"):
    return client_for(owner).post(members_url(code), {"email": email, "role": role}, format="json")


def test_the_owner_adds_people_who_then_see_the_list(alice, bob):
    code = create(alice)
    assert client_for(bob).get(f"{URL}{code}/").status_code == 404  # private

    response = add(alice, code, "BOB@example.com", "viewer")  # addresses match case-insensitively
    assert response.status_code == 201, response.content
    member = response.json()
    assert member == {
        "user_id": str(bob.pk),
        "display_name": "bob",
        "email_hint": "b…@example.com",
        "role": "viewer",
        "added_at": member["added_at"],
        "is_you": False,
    }
    assert ListMembership.objects.get(user=bob).added_by == alice

    detail = client_for(bob).get(f"{URL}{code}/").json()
    assert detail["my_role"] == "viewer"
    assert "leave" in detail["permissions"] and "edit" not in detail["permissions"]
    assert [lst["code"] for lst in client_for(bob).get(URL).json()["results"]] == [code]


def test_member_lists_never_show_full_email_addresses(alice, bob, carol):
    code = create(alice)
    add(alice, code, "bob@example.com", "editor")
    add(alice, code, "carol@example.com")
    for user in (alice, bob):
        response = client_for(user).get(members_url(code))
        assert response.status_code == 200
        assert "@example.com" in response.content.decode()
        assert "bob@example.com" not in response.content.decode()
        assert "carol@example.com" not in response.content.decode()
    names = [m["display_name"] for m in client_for(bob).get(members_url(code)).json()["results"]]
    assert names == ["bob", "carol"]  # oldest first
    assert [m["is_you"] for m in client_for(bob).get(members_url(code)).json()["results"]] == [
        True,
        False,
    ]


def test_only_verified_accounts_can_be_added_with_one_generic_answer(alice, db):
    make_user("unverified@example.com", verified=False)
    code = create(alice)
    for email in ("nobody@example.com", "unverified@example.com"):
        response = add(alice, code, email)
        assert response.status_code == 400
        assert response.json()["email"] == [CANNOT_ADD]
    assert not ListMembership.objects.exists()


def test_adding_needs_a_verified_owner(db, bob):
    owner = make_user("owner@example.com", verified=False)
    code = create(owner)
    response = add(owner, code, "bob@example.com")
    assert response.status_code == 403
    assert response.json()["code"] == "email_unverified"


def test_the_owner_and_existing_members_cannot_be_added_again(alice, bob):
    code = create(alice)
    assert add(alice, code, "alice@example.com").json()["email"] == [
        "That's you. You own this list already."
    ]
    add(alice, code, "bob@example.com")
    assert add(alice, code, "bob@example.com", "editor").json()["email"] == [
        "This person is already on the list."
    ]
    assert ListMembership.objects.get(user=bob).role == "viewer"


def test_roles_are_editor_or_viewer_only(alice, bob):
    code = create(alice)
    assert add(alice, code, "bob@example.com", "owner").status_code == 400
    add(alice, code, "bob@example.com")
    response = client_for(alice).patch(members_url(code, bob), {"role": "owner"}, format="json")
    assert response.status_code == 400


def test_changing_a_role_changes_what_they_may_do(alice, bob):
    code = create(alice)
    add(alice, code, "bob@example.com")
    link = {"destination_url": "https://example.com/a"}
    assert client_for(bob).post(f"{URL}{code}/links/", link, format="json").status_code == 403

    response = client_for(alice).patch(members_url(code, bob), {"role": "editor"}, format="json")
    assert response.status_code == 200 and response.json()["role"] == "editor"
    assert client_for(bob).post(f"{URL}{code}/links/", link, format="json").status_code == 201


def test_only_the_owner_manages_people(alice, bob, carol):
    code = create(alice)
    add(alice, code, "bob@example.com", "editor")
    add(alice, code, "carol@example.com")
    editor = client_for(bob)
    assert editor.get(members_url(code)).status_code == 200  # editors may read
    assert (
        editor.post(
            members_url(code), {"email": "x@example.com", "role": "viewer"}, format="json"
        ).status_code
        == 403
    )
    assert (
        editor.patch(members_url(code, carol), {"role": "editor"}, format="json").status_code == 403
    )
    assert editor.delete(members_url(code, carol)).status_code == 403
    assert client_for(carol).get(members_url(code)).status_code == 403  # viewers may not
    assert ListMembership.objects.get(user=carol).role == "viewer"


def test_removed_people_lose_access_at_once(alice, bob):
    code = create(alice)
    add(alice, code, "bob@example.com", "editor")
    assert client_for(alice).delete(members_url(code, bob)).status_code == 204
    assert client_for(bob).get(f"{URL}{code}/").status_code == 404
    assert client_for(bob).get(URL).json()["results"] == []
    assert client_for(alice).delete(members_url(code, bob)).status_code == 404  # already gone


def test_members_can_leave_but_owners_cannot(alice, bob):
    code = create(alice)
    add(alice, code, "bob@example.com")
    assert client_for(bob).delete(members_url(code, bob)).status_code == 204
    assert not ListMembership.objects.exists()
    response = client_for(alice).delete(members_url(code, alice))
    assert response.status_code == 403


def test_members_need_a_session(alice, bob):
    code = create(alice, visibility="unlisted")
    response = client_for().get(members_url(code))
    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Session"


def test_strangers_cannot_tell_a_private_list_exists(alice, bob):
    code = create(alice)
    assert client_for(bob).get(members_url(code)).status_code == 404
    assert add(bob, code, "bob@example.com").status_code == 404


def test_adding_people_has_its_own_rate_limit(alice, bob, carol, monkeypatch):
    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {"member_add": "1/hour", "list_manage": "100/hour", "list_create": "100/hour"},
    )
    code = create(alice)
    assert add(alice, code, "bob@example.com").status_code == 201
    assert add(alice, code, "carol@example.com").status_code == 429
    assert client_for(alice).delete(members_url(code, bob)).status_code == 204  # other writes


# The list permission matrix (docs/v2/12-AUTHORIZATION.md), over HTTP: every principal ×
# visibility × action. Expected statuses are written out, not derived from the policy, so a
# change to the policy that breaks the documented rules fails here.

ROLES = ["anonymous", "stranger", "viewer", "editor", "owner"]
VISIBILITIES = ["private", "unlisted", "public"]


def _expected(action: str, role: str, visibility: str) -> int:
    visible = visibility != "private" or role in ("viewer", "editor", "owner")
    if action == "members.read" and role == "anonymous":
        return 401  # session-only endpoint: asks for sign-in before looking at the list
    if not visible:
        return 404
    ok = {"view": 200, "links.add": 201, "settings": 200, "members.read": 200, "delete": 204}
    allowed = {
        "view": ROLES,
        "links.add": ["editor", "owner"],
        "settings": ["owner"],
        "members.read": ["editor", "owner"],
        "delete": ["owner"],
    }[action]
    if role in allowed:
        return ok[action]
    return 401 if role == "anonymous" else 403


def _request(action: str, client: APIClient, code: str):
    match action:
        case "view":
            return client.get(f"{URL}{code}/")
        case "links.add":
            data = {"destination_url": "https://example.com/matrix"}
            return client.post(f"{URL}{code}/links/", data, format="json")
        case "settings":
            return client.patch(f"{URL}{code}/", {"allow_fork": True}, format="json")
        case "members.read":
            return client.get(members_url(code))
        case "delete":
            return client.delete(f"{URL}{code}/")


@pytest.mark.parametrize("visibility", VISIBILITIES)
@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("action", ["view", "links.add", "settings", "members.read", "delete"])
def test_list_permission_matrix(db, action, role, visibility):
    owner = make_user("owner@example.com")
    code = create(owner, visibility=visibility)
    users = {"anonymous": None, "owner": owner}
    user = users[role] if role in users else make_user(f"{role}@example.com")
    if role in ("viewer", "editor"):
        ListMembership.objects.create(
            shared_list=SharedList.objects.get(public_code=code), user=user, role=role
        )
    response = _request(action, client_for(user), code)
    assert response.status_code == _expected(action, role, visibility), response.content
    if response.status_code == 404:
        assert response.json() == {"detail": "Not found.", "code": "not_found"}  # no leak


@pytest.mark.django_db(transaction=True)
def test_an_editor_removed_mid_write_cannot_commit_after_the_removal():
    """The removal holds the list's row lock; the editor's write waits for it, then re-checks
    the policy and is refused (docs/v2/12-AUTHORIZATION.md#concurrent-permission-changes)."""
    owner, editor = make_user("owner@example.com"), make_user("editor@example.com")
    code = create(owner)
    shared_list = SharedList.objects.get(public_code=code)
    ListMembership.objects.create(shared_list=shared_list, user=editor, role="editor")

    removal_locked, outcome = threading.Event(), {}

    def editor_adds_a_link():
        removal_locked.wait()
        try:
            link_services.add_link(
                Principal(user=editor), shared_list.pk, destination_url="https://example.com/x"
            )
            outcome["result"] = "added"
        except Exception as exc:  # noqa: BLE001 - the test reports whatever happened
            outcome["result"] = type(exc).__name__
        finally:
            connection.close()

    writer = threading.Thread(target=editor_adds_a_link)
    writer.start()
    with transaction.atomic():
        member_services.remove_member(Principal(user=owner), shared_list.pk, editor.pk)
        removal_locked.set()
        writer.join(timeout=1)
        assert writer.is_alive(), "the write must wait for the removal's lock"
    writer.join(timeout=10)

    assert outcome["result"] == "NotVisible"  # private: a removed editor can't even see it
    assert not SharedLink.objects.exists()
