"""Query budgets per endpoint, and snapshot sizes (task 9.2,
docs/v2/14-INFRASTRUCTURE.md#performance-targets-initial).

Every endpoint is measured with little data and with the sizes the targets name (100 links,
30 lists in a group, 30 lists of your own): the counts must be equal, so a cost that grows
with the data (N+1) fails even under budget. Budgets leave out the two queries Django spends
loading a signed-in request's session and user. Throttled endpoints add the rate limit's own
statements (`THROTTLE`), counted separately.
"""

import secrets

import pytest
from allauth.account.models import EmailAddress
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.groups import services as group_services
from apps.groups.models import GroupList
from apps.sharing.models import ListMembership, SharedLink, SharedList
from apps.sharing.policy import Visibility
from apps.sharing.selectors import Principal
from apps.sharing.services import links as link_services
from apps.sharing.services import lists as list_services
from apps.shortener.models import ShortRedirect
from apps.versioning.models import ListRevision

pytestmark = pytest.mark.django_db
URL = "/api/v2/"
SESSION = 2  # the session row and its user, for a signed-in request
# The PostgreSQL rate limiter (V1's design, exact under concurrency): savepoints, an advisory
# lock, and the database cache's read, count and write.
THROTTLE = 8


def person(email: str) -> User:
    user = User.objects.create_user(email, "pw-correct-horse-1", display_name=email[:3])
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user


def signed_in(user) -> APIClient:
    client = APIClient()
    client.force_login(user)  # a real session, as in production
    return client


def a_list(owner, links: int, *, title="Tools") -> SharedList:
    shared_list = list_services.create_list(Principal(user=owner), title=title)[0]
    for n in range(links):
        link_services.add_link(
            Principal(user=owner), shared_list.pk, destination_url=f"https://e{n}.example/"
        )
    SharedList.objects.filter(pk=shared_list.pk).update(visibility=Visibility.PUBLIC.value)
    return SharedList.objects.get(pk=shared_list.pk)


def count(client: APIClient, path: str, status: int = 200) -> int:
    with CaptureQueriesContext(connection) as captured:
        response = client.get(path)
    assert response.status_code == status, response.content
    return len(captured.captured_queries)


@pytest.fixture
def alice():
    return person("alice@example.com")


@pytest.fixture
def bob():
    return person("bob@example.com")


# (path template, signed in, budget). The list page (detail + links) stays within the
# target's 4 queries; the group workspace (group + its lists) within its 5.
LIST_ENDPOINTS = [
    ("lists/{code}/", False, 1),
    ("lists/{code}/links/", False, 3),
    ("lists/{code}/", True, 1),
    ("lists/{code}/links/", True, 3),
    ("lists/{code}/revisions/", True, 3),
    ("lists/{code}/revisions/2/", True, 3),
    ("lists/{code}/members/", True, 3),
]


@pytest.mark.parametrize(("path", "signed", "budget"), LIST_ENDPOINTS)
def test_list_endpoints_cost_the_same_with_100_links(alice, bob, path, signed, budget):
    small, big = a_list(alice, 3), a_list(alice, 100, title="Big")
    for shared_list in (small, big):
        ListMembership.objects.create(shared_list=shared_list, user=bob, role="editor")
    client = signed_in(alice) if signed else APIClient()
    extra = SESSION if signed else 0
    costs = [count(client, URL + path.format(code=lst.public_code)) - extra for lst in (small, big)]
    assert costs[0] == costs[1] <= budget, costs


def test_group_workspace_costs_the_same_with_30_lists(alice):
    costs = []
    for n in (3, 30):
        group = group_services.create_group(Principal(user=alice), title=f"Group {n}")
        for i in range(n):
            GroupList.objects.create(
                group=group, shared_list=a_list(alice, 2, title=f"L{n}-{i}"), position=i
            )
        client = signed_in(alice)
        detail = count(client, f"{URL}groups/{group.code}/") - SESSION
        lists = count(client, f"{URL}groups/{group.code}/lists/") - SESSION
        costs.append((detail, lists))
    assert costs[0] == costs[1], costs
    assert sum(costs[1]) <= 5, costs


def test_my_lists_and_groups_cost_the_same_with_30_of_each(alice, bob):
    costs = []
    for n in (3, 30):
        user = person(f"u{n}@example.com")
        for i in range(n):
            mine = a_list(user, 1, title=f"Mine {i}")
            theirs = a_list(bob, 0, title=f"Theirs {n}-{i}")
            ListMembership.objects.create(shared_list=theirs, user=user, role="viewer")
            group_services.create_group(Principal(user=user), title=f"G {i}")
            assert mine.pk
        client = signed_in(user)
        costs.append((count(client, f"{URL}lists/"), count(client, f"{URL}groups/")))
    assert costs[0] == costs[1], costs
    assert all(c - SESSION <= 3 for c in costs[1]), costs


def test_short_urls_take_one_query(alice):
    link = SharedLink.objects.filter(shared_list=a_list(alice, 1)).get()
    code = ShortRedirect.objects.get(link=link).code
    assert count(APIClient(), f"/r/{code}", 302) == 1


@pytest.mark.parametrize(
    ("path", "budget"),
    [
        ("directory/lists/", 3),
        ("directory/lists/?q=tools&tags=dev", 3),
        ("directory/groups/", 2),
        ("directory/tags/", 2),
    ],
)
def test_the_directory_costs_the_same_with_more_results(alice, path, budget):
    costs = []
    for n in (3, 20):
        for i in range(n - (3 if n == 20 else 0)):
            lst = a_list(alice, 1, title=f"Tools {n}-{i}")
            SharedList.objects.filter(pk=lst.pk).update(tags=["dev"])
        costs.append(count(APIClient(), URL + path) - THROTTLE)
    assert costs[0] == costs[1] <= budget, costs


def test_a_full_snapshot_stays_small(alice):
    """Risk 27: a revision holds the whole list. At the cap, with every field at its maximum
    and incompressible, it stays under 512 KB; a typical list is a few kilobytes."""
    shared_list = list_services.create_list(Principal(user=alice), title="x" * 255)[0]
    for n in range(100):
        link_services.add_link(
            Principal(user=alice),
            shared_list.pk,
            destination_url=f"https://e{n}.example/{secrets.token_urlsafe(1440)}",
            title=secrets.token_urlsafe(180)[:255],
            description=secrets.token_urlsafe(720)[:1000],
        )
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT pg_column_size(snapshot) FROM {ListRevision._meta.db_table} "
            "WHERE shared_list_id = %s ORDER BY number DESC LIMIT 1",
            [shared_list.pk],
        )
        worst = cursor.fetchone()[0]
    assert worst < 512 * 1024, worst

    typical = a_list(alice, 100, title="Typical")
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT pg_column_size(snapshot) FROM {ListRevision._meta.db_table} "
            "WHERE shared_list_id = %s ORDER BY number DESC LIMIT 1",
            [typical.pk],
        )
        assert cursor.fetchone()[0] < 32 * 1024
