"""Moderation (task 9.0, docs/v2/13-SECURITY.md#moderation): reports about lists, and the
operator's commands for lists."""

import io
import smtplib
from datetime import timedelta

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import User
from apps.sharing.models import ListMembership, SharedList
from apps.sharing.policy import Visibility
from apps.sharing.selectors import Principal
from apps.sharing.services import links as link_services
from apps.sharing.services import lists as list_services
from apps.shortener.models import ShortRedirect

URL = "/api/v2/lists/"
REPORT = {"reason": "phishing", "details": "It asks for bank passwords."}
MODERATION = "moderation@example.test"


@pytest.fixture(autouse=True)
def moderation_address(settings):
    settings.MODERATION_EMAIL = MODERATION


@pytest.fixture
def alice(db):
    return User.objects.create_user("alice@example.com", "pw-correct-horse-1")


@pytest.fixture
def bob(db):
    return User.objects.create_user("bob@example.com", "pw-correct-horse-2")


def client_for(user=None) -> APIClient:
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


def make_list(owner, title="Team tools", visibility=Visibility.PUBLIC) -> SharedList:
    shared_list = list_services.create_list(Principal(user=owner), title=title)[0]
    SharedList.objects.filter(pk=shared_list.pk).update(visibility=visibility.value)
    shared_list.refresh_from_db()
    return shared_list


def report(client: APIClient, code: str, data=None):
    return client.post(f"{URL}{code}/report/", data or REPORT, format="json")


def test_anyone_who_can_see_a_list_may_report_it(alice, bob, mailoutbox):
    shared_list = make_list(alice)
    code = shared_list.public_code

    assert report(client_for(), code).status_code == 202
    (mail,) = mailoutbox
    assert mail.to == [MODERATION]
    assert mail.subject == "[listlinkedin] Report: Phishing or malware, list “Team tools”"
    for expected in (
        "Details: It asks for bank passwords.",
        f"Code: {code}",
        f"/l/{code}/team-tools",
        "Visibility: public",
        f"Owner: user {alice.pk}",
        "Reported by: someone who wasn't signed in",
        f"python manage.py unpublish_list --reason '…' -- {code}",
        f"python manage.py suspend_account {alice.pk}",
    ):
        assert expected in mail.body, expected
    # Who reported it is an id at most: never an address, never an IP.
    assert "127.0.0.1" not in mail.body and "@example.com" not in mail.body

    assert report(client_for(bob), code, {"reason": "spam"}).status_code == 202
    assert f"Reported by: user {bob.pk}" in mailoutbox[1].body
    assert "Details: (none)" in mailoutbox[1].body


def test_owners_cannot_report_their_own_list(alice):
    shared_list = make_list(alice)
    assert report(client_for(alice), shared_list.public_code).status_code == 403
    owner_view = client_for(alice).get(f"{URL}{shared_list.public_code}/").json()
    assert "report" not in owner_view["permissions"]
    visitor_view = client_for().get(f"{URL}{shared_list.public_code}/").json()
    assert visitor_view["permissions"] == ["view", "report"]


def test_private_and_expired_lists_answer_as_they_do_elsewhere(alice, bob, mailoutbox):
    private = make_list(alice, visibility=Visibility.PRIVATE)
    assert report(client_for(bob), private.public_code).status_code == 404
    assert report(client_for(), private.public_code).status_code == 404
    ListMembership.objects.create(shared_list=private, user=bob, role="viewer")
    assert report(client_for(bob), private.public_code).status_code == 202  # people on it may
    expired = make_list(alice, "Old")
    SharedList.objects.filter(pk=expired.pk).update(expires_at=timezone.now() - timedelta(1))
    assert report(client_for(), expired.public_code).status_code == 410
    assert len(mailoutbox) == 1


def test_invalid_reports_are_refused(alice):
    code = make_list(alice).public_code
    assert report(client_for(), code, {"reason": "boring"}).status_code == 400
    too_long = {"reason": "other", "details": "x" * 1001}
    assert report(client_for(), code, too_long).status_code == 400


def test_reports_are_rate_limited(alice, monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"report": "1/hour"})
    code = make_list(alice).public_code
    assert [report(client_for(), code).status_code for _ in range(2)] == [202, 429]


def test_without_a_moderation_address_reports_are_only_logged(alice, settings, mailoutbox, caplog):
    settings.MODERATION_EMAIL = ""
    shared_list = make_list(alice)
    assert report(client_for(), shared_list.public_code).status_code == 202
    assert mailoutbox == []
    assert f"Report on list {shared_list.pk} not emailed" in caplog.text
    assert "bank passwords" not in caplog.text  # the reporter's words aren't logged


def test_a_failing_mail_relay_answers_503(alice, monkeypatch):
    def refuse(*args, **kwargs):
        raise smtplib.SMTPServerDisconnected("gone")

    monkeypatch.setattr("apps.sharing.services.moderation.send_mail", refuse)
    response = report(client_for(), make_list(alice).public_code)
    assert response.status_code == 503 and response.json()["code"] == "unavailable"


# The operator's commands.


def run(*args) -> str:
    out = io.StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


def test_unpublish_list_makes_it_private_and_stops_its_short_urls(alice):
    shared_list = make_list(alice)
    link, _ = link_services.add_link(
        Principal(user=alice), shared_list.pk, destination_url="https://example.com/"
    )
    short = ShortRedirect.objects.get(link=link).code
    assert client_for().get(f"/r/{short}").status_code == 302

    output = run("unpublish_list", "--reason", "phishing", "--", shared_list.public_code)
    assert "is private now" in output
    shared_list.refresh_from_db()
    assert shared_list.visibility == "private"
    assert client_for().get(f"{URL}{shared_list.public_code}/").status_code == 404
    assert client_for().get(f"/r/{short}").status_code == 404
    assert client_for(alice).get(f"{URL}{shared_list.public_code}/").status_code == 200


def test_codes_that_start_with_a_dash_work_after_double_dash(alice):
    """Codes are Base64URL, so some start with "-", which argparse reads as an option: the
    commands are always shown with `--` before the code."""
    shared_list = make_list(alice)
    SharedList.objects.filter(pk=shared_list.pk).update(public_code="-dashFirstCode00")
    assert "is private now" in run("unpublish_list", "--reason", "spam", "--", "-dashFirstCode00")


def test_unpublish_list_refuses_unknown_lists(db):
    with pytest.raises(CommandError, match="no list"):
        run("unpublish_list", "--reason", "spam", "--", "no-such-code-000")


def test_delete_list_shows_what_it_would_delete_without_yes(alice):
    shared_list = make_list(alice)
    with pytest.raises(CommandError, match="Add --yes"):
        run("delete_list", "--reason", "spam", "--", shared_list.public_code)
    assert SharedList.objects.filter(pk=shared_list.pk).exists()
    assert "is deleted" in run(
        "delete_list", "--reason", "spam", "--yes", "--", shared_list.public_code
    )
    assert not SharedList.objects.filter(pk=shared_list.pk).exists()


def test_find_links_matches_a_host_and_its_subdomains(alice):
    shared_list = make_list(alice)
    for url in (
        "https://evil.example/",
        "https://login.evil.example/account",
        "https://notevil.example/",
        "https://example.com/?next=evil.example",
    ):
        link_services.add_link(Principal(user=alice), shared_list.pk, destination_url=url)
    output = run("find_links", "Evil.Example")
    assert "https://evil.example/" in output and "login.evil.example" in output
    assert "notevil.example" not in output and "example.com" not in output
    assert "2 links to Evil.Example." in output
