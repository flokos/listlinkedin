import uuid

from django.db import models
from django.utils import timezone

from .generators import SHORT_CODE_LENGTH

REDIRECT_CODE_CONSTRAINT = "shortener_redirect_code_uniq"


class ShortRedirect(models.Model):
    """Maps a stable public code to a link; the link's destination may change underneath."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=SHORT_CODE_LENGTH, editable=False)
    link = models.ForeignKey(
        "sharing.SharedLink", on_delete=models.CASCADE, related_name="redirects"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["code"], name=REDIRECT_CODE_CONSTRAINT),
        ]

    def __str__(self) -> str:
        return self.code
