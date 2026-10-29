import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.shortener.generators import SHORT_CODE_LENGTH

from .policy import Role, Visibility

PUBLIC_CODE_CONSTRAINT = "sharing_list_public_code_uniq"
# Live links only: a deleted link (tombstone) keeps its URL without blocking re-adding it.
UNIQUE_DESTINATION_CONSTRAINT = "sharing_link_live_destination_uniq"
LINK_POSITION_CONSTRAINT = "sharing_link_position_uniq"
LINK_CREATION_KEY_CONSTRAINT = "sharing_link_creation_key_uniq"
CREATION_KEY_CONSTRAINT = "sharing_list_creation_key_uniq"
MEMBERSHIP_CONSTRAINT = "sharing_membership_list_user_uniq"

VISIBILITY_CHOICES = [(v.value, v.value.capitalize()) for v in Visibility]
MEMBER_ROLE_CHOICES = [(r.value, r.value.capitalize()) for r in (Role.EDITOR, Role.VIEWER)]


class SharedList(models.Model):
    """A List (docs/v2/04-DOMAIN-MODEL.md). Its id and public code never change.

    An account owns it (`owner`), or, for a list created before accounts existed, the
    holder of its owner token manages it until it is claimed or expires: a legacy list.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_code = models.CharField(max_length=SHORT_CODE_LENGTH, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,  # account deletion removes owned lists explicitly first
        related_name="owned_lists",
    )
    # SHA-256 hex digest of a legacy list's owner token; NULL for account-owned lists.
    owner_token_hash = models.CharField(max_length=64, null=True, blank=True, editable=False)  # noqa: DJ001
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    # A media path (apps.metadata.images), relative to MEDIA_ROOT. NULL: no image.
    image = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001 (spec: nullable)
    # Cosmetic URL suffix derived from the title (/l/{code}/{slug}); never an identifier.
    slug = models.CharField(max_length=80, blank=True, default="")
    visibility = models.CharField(
        max_length=8, choices=VISIBILITY_CHOICES, default=Visibility.PRIVATE.value
    )
    allow_fork = models.BooleanField(default=False)
    allow_branch = models.BooleanField(default=False)
    # Idempotency-Key of the request that created the list (a retried create returns it).
    creation_key = models.UUIDField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)  # NULL = permanent

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["public_code"], name=PUBLIC_CODE_CONSTRAINT),
            models.UniqueConstraint(fields=["creation_key"], name=CREATION_KEY_CONSTRAINT),
            models.CheckConstraint(
                condition=Q(visibility__in=[v.value for v in Visibility]),
                name="sharing_list_visibility_valid",
            ),
            # L2: every list has a manager, an owner account or an owner token.
            models.CheckConstraint(
                condition=Q(owner__isnull=False) | Q(owner_token_hash__isnull=False),
                name="sharing_list_has_manager",
            ),
            # L3: a legacy list stays unlisted and expiring until it is claimed.
            models.CheckConstraint(
                condition=Q(owner__isnull=False)
                | Q(visibility=Visibility.UNLISTED.value, expires_at__isnull=False),
                name="sharing_list_legacy_unlisted_expiring",
            ),
        ]

    def __str__(self) -> str:
        return self.public_code

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and timezone.now() >= self.expires_at

    @property
    def is_legacy(self) -> bool:
        return self.owner_id is None


class SharedLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shared_list = models.ForeignKey(SharedList, on_delete=models.CASCADE, related_name="links")
    # Stored in normalized form (see domain.normalize_destination_url).
    destination_url = models.TextField()
    title = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001 (spec: nullable)
    description = models.TextField(null=True, blank=True)  # noqa: DJ001 (spec: nullable)
    # The uploaded icon's media path. A fetched icon lives in `metadata`, never here.
    icon = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001 (spec: nullable)
    # 0-based order among the list's live links (K3). NULL exactly when the link is deleted.
    position = models.IntegerField(null=True, blank=True)
    # Tombstone: the row, its id and its short code survive deletion (docs/v2/adr/ADR-013).
    deleted_at = models.DateTimeField(null=True, blank=True)
    # The link this one was copied from (forks). A plain UUID on purpose: no FK (K5).
    source_link_id = models.UUIDField(null=True, blank=True)
    # Fetched values only, written by the metadata worker (task 7.3); never user fields.
    metadata = models.JSONField(default=dict, blank=True)
    metadata_fetched_at = models.DateTimeField(null=True, blank=True)
    creation_key = models.UUIDField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["shared_list", "destination_url"],
                condition=Q(deleted_at__isnull=True),
                name=UNIQUE_DESTINATION_CONSTRAINT,
            ),
            # Checked at commit, so a move can shift several positions in one statement.
            # It can't be partial (Django refuses deferrable + condition), which is why
            # tombstones have position NULL: NULLs never collide.
            models.UniqueConstraint(
                fields=["shared_list", "position"],
                deferrable=models.Deferrable.DEFERRED,
                name=LINK_POSITION_CONSTRAINT,
            ),
            models.CheckConstraint(
                condition=Q(deleted_at__isnull=True, position__isnull=False)
                | Q(deleted_at__isnull=False, position__isnull=True),
                name="sharing_link_tombstone_position",
            ),
            models.CheckConstraint(
                condition=Q(position__gte=0), name="sharing_link_position_not_negative"
            ),
            models.UniqueConstraint(
                fields=["shared_list", "source_link_id"],
                condition=Q(source_link_id__isnull=False, deleted_at__isnull=True),
                name="sharing_link_live_source_uniq",
            ),
            models.UniqueConstraint(
                fields=["shared_list", "creation_key"], name=LINK_CREATION_KEY_CONSTRAINT
            ),
        ]

    def __str__(self) -> str:
        return self.destination_url

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class ListMembership(models.Model):
    """A user's EDITOR or VIEWER role on one list. The owner is never a member (L6)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shared_list = models.ForeignKey(
        SharedList, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="list_memberships"
    )
    role = models.CharField(max_length=8, choices=MEMBER_ROLE_CHOICES)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["shared_list", "user"], name=MEMBERSHIP_CONSTRAINT),
            models.CheckConstraint(
                condition=Q(role__in=[Role.EDITOR.value, Role.VIEWER.value]),
                name="sharing_membership_role_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} {self.role} {self.shared_list_id}"
