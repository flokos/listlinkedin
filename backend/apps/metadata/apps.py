import logging

from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class MetadataConfig(AppConfig):
    name = "apps.metadata"
    label = "metadata"

    def ready(self) -> None:
        from .fetcher import denied_networks, test_hosts

        # Fail at startup, not on the first fetch: an entry that doesn't parse would
        # otherwise make every fetch fail (or, worse, be skipped).
        try:
            denied_networks()
        except ValueError as exc:
            raise ImproperlyConfigured(f"FETCH_BLOCKED_NETWORKS: {exc}") from exc
        try:
            fixtures = test_hosts()
        except ValueError as exc:
            raise ImproperlyConfigured(f"FETCH_TEST_HOSTS: {exc}") from exc
        if fixtures:
            logger.warning(
                "FETCH_TEST_HOSTS is set (%s): the metadata fetcher may reach these private "
                "test hosts. This is for end-to-end tests only, never production.",
                ", ".join(f"{name}={target}" for name, target in fixtures.items()),
            )
