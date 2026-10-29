import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.shortener.generators import SHORT_CODE_LENGTH

from .policy import Role, Visibility

PUBLIC_CODE_CONSTRAINT = "sharing_list_public_code_uniq"
UNIQUE_DESTINATION_CONSTRAINT = "sharing_link_destination_per_list_uniq"
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
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["shared_list", "destination_url"], name=UNIQUE_DESTINATION_CONSTRAINT
            ),
        ]

    def __str__(self) -> str:
        return self.destination_url


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
