import os
import secrets
import subprocess
import sys

import pytest
from django.conf import settings


def run_check(**env_overrides) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.production",
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(50),
        **env_overrides,
    }
    return subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("value", ["0", "20s", "500ms", "2min"])
def test_database_timeouts_accept_postgres_durations(value):
    result = run_check(DB_STATEMENT_TIMEOUT=value, DB_LOCK_TIMEOUT=value)
    assert result.returncode == 0, result.stderr


def test_malformed_database_timeout_refuses_to_start():
    # The value ends up in the connection options; anything but a duration is a mistake.
    result = run_check(DB_STATEMENT_TIMEOUT="20s -c search_path=evil")
    assert result.returncode != 0
    assert "DB_STATEMENT_TIMEOUT must be a PostgreSQL duration" in result.stderr
