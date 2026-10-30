from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured


class MetadataConfig(AppConfig):
    name = "apps.metadata"
    label = "metadata"

    def ready(self) -> None:
        from .fetcher import denied_networks

        # Fail at startup, not on the first fetch: an entry that doesn't parse would
        # otherwise make every fetch fail (or, worse, be skipped).
        try:
            denied_networks()
        except ValueError as exc:
            raise ImproperlyConfigured(f"FETCH_BLOCKED_NETWORKS: {exc}") from exc
