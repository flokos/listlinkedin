"""List images and link icons (docs/v2/adr/ADR-012-media-and-images.md).

Uploading needs an editor or owner account (Action.UPLOAD): an edit link can't upload. The
image is decoded and re-encoded *outside* the list's row lock, so a slow decode never holds
up the list's other writers. Permission is checked before (so strangers can't fill the disk)
and again under the lock (so a removed editor can't commit after the removal). A stored file
that ends up unused is harmless: `cleanup_media` deletes it after its grace period.
"""

from uuid import UUID

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.metadata import images
from apps.versioning.models import RevisionKind
from apps.versioning.services import record_revision

from ..models import SharedLink, SharedList
from ..policy import Action, can
from ..selectors import Principal
from .links import get_live_link
from .lists import _lock, check_head, denied

CANNOT_UPLOAD = "Only the list's editors and owner can change its images."


def set_list_image(principal: Principal, list_id: UUID, data: bytes | None) -> SharedList:
    """Replace the list's image with `data` (any accepted format), or remove it (None)."""
    path = _store(principal, list_id, None, data, images.IMAGE)
    with transaction.atomic():
        locked = _lock_for_upload(principal, list_id)
        locked.image = path
        locked.save(update_fields=["image", "updated_at"])
    return locked


def set_link_icon(
    principal: Principal,
    list_id: UUID,
    link_id: UUID,
    data: bytes | None,
    *,
    expected_head: int | None = None,
) -> SharedLink:
    """Replace a live link's uploaded icon, or remove it (None). A fetched icon, if any, is
    kept apart (`metadata`) and shows again once the uploaded one is removed. The uploaded
    icon is content, so this is versioned (the list image is a setting and isn't)."""
    path = _store(principal, list_id, link_id, data, images.ICON)
    with transaction.atomic():
        locked = _lock_for_upload(principal, list_id)
        check_head(locked, expected_head)
        link = get_live_link(locked, link_id)
        link.icon = path
        link.save(update_fields=["icon", "updated_at"])
        record_revision(locked, kind=RevisionKind.EDITED, user=principal.user)
    return link


def _store(principal, list_id, link_id, data: bytes | None, kind: images.Kind) -> str | None:
    if data is None:
        return None
    with transaction.atomic():  # a brief lock: may this principal upload here at all?
        locked = _lock_for_upload(principal, list_id)
        if link_id is not None:
            get_live_link(locked, link_id)
    try:
        return images.store(images.process(data, kind), kind)
    except images.ImageRejected as exc:
        raise ValidationError({"file": [str(exc)]}) from None


def _lock_for_upload(principal: Principal, list_id: UUID) -> SharedList:
    locked, actor, facts = _lock(principal, list_id)
    if not can(actor, Action.UPLOAD, facts):
        raise denied(principal, CANNOT_UPLOAD)
    return locked
