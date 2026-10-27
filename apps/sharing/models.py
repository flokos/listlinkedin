import uuid

from django.db import models
from django.utils import timezone

from apps.shortener.generators import SHORT_CODE_LENGTH

PUBLIC_CODE_CONSTRAINT = "sharing_list_public_code_uniq"
UNIQUE_DESTINATION_CONSTRAINT = "sharing_link_destination_per_list_uniq"


class SharedList(models.Model):
    # Identity and lifetime are fixed at creation; only `title` (and contents) change.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_code = models.CharField(max_length=SHORT_CODE_LENGTH, editable=False)
    owner_token_hash = models.CharField(max_length=64, editable=False)  # SHA-256 hex digest
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(editable=False, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["public_code"], name=PUBLIC_CODE_CONSTRAINT),
        ]

    def __str__(self) -> str:
        return self.public_code

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at


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
