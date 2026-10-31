import itertools
from datetime import timedelta

import pytest
from allauth.account.models import EmailAddress
from django.utils import timezone

from apps.accounts.models import User
from apps.sharing.models import ListMembership, SharedList
from apps.sharing.selectors import Principal

_codes = itertools.count()


def make_user(email: str, *, verified: bool = True) -> User:
    user = User.objects.create_user(email, "pw-correct-horse-1", display_name=email.split("@")[0])
    EmailAddress.objects.create(user=user, email=email, verified=verified, primary=True)
    return user


def make_list(owner, visibility="private", *, title=None, **fields) -> SharedList:
    n = next(_codes)
    return SharedList.objects.create(
        public_code=f"list{n:012d}",
        owner=owner,
        title=title or f"List {n}",
        visibility=visibility,
        **fields,
    )


def make_legacy_list() -> SharedList:
    n = next(_codes)
    return SharedList.objects.create(
        public_code=f"lgcy{n:012d}",
        owner_token_hash="0" * 64,
        title=f"Legacy {n}",
        visibility="unlisted",
        expires_at=timezone.now() + timedelta(days=3),
    )


def share(shared_list: SharedList, user, role="viewer") -> None:
    ListMembership.objects.create(shared_list=shared_list, user=user, role=role)


def as_(user=None) -> Principal:
    return Principal(user=user)


@pytest.fixture
def alice(db):
    return make_user("alice@example.com")


@pytest.fixture
def bob(db):
    return make_user("bob@example.com")


@pytest.fixture
def carol(db):
    return make_user("carol@example.com")
