from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured


class SharingConfig(AppConfig):
    name = "apps.sharing"
    label = "sharing"

    def ready(self) -> None:
        from .domain import blocked_hosts

        # Fail at startup rather than on every link creation and redirect.
        try:
            blocked_hosts()
        except ValueError as exc:
            raise ImproperlyConfigured(
                f"BLOCKED_DESTINATION_HOSTS or DJANGO_ALLOWED_HOSTS: {exc}"
            ) from exc
