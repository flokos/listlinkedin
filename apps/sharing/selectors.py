from django.db.models import OuterRef, QuerySet, Subquery
from rest_framework.exceptions import NotFound

from apps.shortener.models import ShortRedirect

from .exceptions import Gone
from .models import SharedLink, SharedList


def get_active_list(public_code: str) -> SharedList:
    """Return a non-expired list. Unknown codes raise 404, expired ones 410."""
    shared_list = SharedList.objects.filter(public_code=public_code).first()
    if shared_list is None:
        raise NotFound()
    if shared_list.is_expired:
        raise Gone()
    return shared_list


def links_with_short_codes(shared_list: SharedList) -> QuerySet[SharedLink]:
    """Links of a list, newest first, each annotated with its active `short_code`."""
    active_code = ShortRedirect.objects.filter(link=OuterRef("pk"), is_active=True).values("code")
    return (
        SharedLink.objects.filter(shared_list=shared_list)
        .annotate(short_code=Subquery(active_code[:1]))
        .order_by("-created_at", "-id")
    )


def get_link(shared_list: SharedList, link_id) -> SharedLink:
    link = links_with_short_codes(shared_list).filter(pk=link_id).first()
    if link is None:
        raise NotFound()
    return link
