import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.sharing.models import MEMBER_ROLE_CHOICES, VISIBILITY_CHOICES
from apps.sharing.policy import Role, Visibility
from apps.shortener.generators import SHORT_CODE_LENGTH

GROUP_CODE_CONSTRAINT = "groups_group_code_uniq"
GROUP_LIST_CONSTRAINT = "groups_grouplist_group_list_uniq"
GROUP_POSITION_CONSTRAINT = "groups_grouplist_position_uniq"
GROUP_MEMBERSHIP_CONSTRAINT = "groups_membership_group_user_uniq"

# Groups whose owner is deleting their account are hidden from everyone, like their lists
# (docs/v2/adr/ADR-016).
GROUP_OWNER_ACTIVE = Q(owner__deleted_at__isnull=True)


class Group(models.Model):
    """An ordered collection of Lists with its own code, owner and visibility
    (docs/v2/04-DOMAIN-MODEL.md#group-grouplist). It never copies the lists' content and never
    grants access to them (G2)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=SHORT_CODE_LENGTH, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,  # erasing an account deletes its groups explicitly first
        related_name="owned_groups",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    # A media path (apps.metadata.images), relative to MEDIA_ROOT. NULL: no image.
    image = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001 (spec: nullable)
    # Cosmetic URL suffix derived from the title (/g/{code}/{slug}); never an identifier.
    slug = models.CharField(max_length=80, blank=True, default="")
    visibility = models.CharField(
        max_length=8, choices=VISIBILITY_CHOICES, default=Visibility.PRIVATE.value
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["code"], name=GROUP_CODE_CONSTRAINT),
            models.CheckConstraint(
                condition=Q(visibility__in=[v.value for v in Visibility]),
                name="groups_group_visibility_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.code


class GroupList(models.Model):
    """One list's place in a group. A list appears at most once per group (G1)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="entries")
    shared_list = models.ForeignKey(
        "sharing.SharedList", on_delete=models.CASCADE, related_name="group_entries"
    )
    # The list's order in the group. Unique, but deleting a list can leave a gap, which the
    # group's next write closes: readers only ever sort by it.
    position = models.IntegerField()
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
            models.UniqueConstraint(fields=["group", "shared_list"], name=GROUP_LIST_CONSTRAINT),
            # Checked at commit, so a move can shift several positions in one statement.
            models.UniqueConstraint(
                fields=["group", "position"],
                deferrable=models.Deferrable.DEFERRED,
                name=GROUP_POSITION_CONSTRAINT,
            ),
            models.CheckConstraint(
                condition=Q(position__gte=0), name="groups_grouplist_position_not_negative"
            ),
        ]
        # The unique constraint covers (group, …); this one serves "groups containing a list".
        indexes = [models.Index(fields=["shared_list"], name="groups_grouplist_list_idx")]

    def __str__(self) -> str:
        return f"{self.group_id} #{self.position}: {self.shared_list_id}"


class GroupMembership(models.Model):
    """A user's EDITOR or VIEWER role on one group. The owner is never a member. A group role
    grants nothing on the lists in the group."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_memberships"
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
            models.UniqueConstraint(fields=["group", "user"], name=GROUP_MEMBERSHIP_CONSTRAINT),
            models.CheckConstraint(
                condition=Q(role__in=[Role.EDITOR.value, Role.VIEWER.value]),
                name="groups_membership_role_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} {self.role} {self.group_id}"
