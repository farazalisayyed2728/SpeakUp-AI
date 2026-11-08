import os
import subprocess
import sys

import pytest

BASE_ENV = {
    **{
        key: value
        for key, value in os.environ.items()
        if not key.startswith("DJANGO_") and key not in {"DATABASE_URL", "SENTRY_DSN"}
    },
    "DJANGO_SETTINGS_MODULE": "config.settings.production",
    "DATABASE_URL": "postgresql://u:p@localhost:5432/db",
}


def run_check(extra: dict, *args: str):
    env = {**BASE_ENV, **extra}
    return subprocess.run(
        [sys.executable, "manage.py", "check", *args], env=env, capture_output=True, text=True
    )


def test_production_refuses_to_boot_without_secret_key():
    r = run_check({"DJANGO_ALLOWED_HOSTS": "example.com"})
    assert r.returncode != 0 and "DJANGO_SECRET_KEY" in r.stderr


def test_production_refuses_to_boot_without_allowed_hosts():
    r = run_check({"DJANGO_SECRET_KEY": "x" * 60})
    assert r.returncode != 0 and "ALLOWED_HOSTS" in r.stderr


@pytest.mark.parametrize("hsts_preload", ["1"])
def test_production_passes_deploy_checks(hsts_preload):
    r = run_check(
        {
            "DJANGO_SECRET_KEY": "k" * 4 + "Zq9!" * 12,
            "DJANGO_ALLOWED_HOSTS": "example.com",
            "DJANGO_HSTS_PRELOAD": hsts_preload,
        },
        "--deploy",
        "--fail-level",
        "WARNING",
    )
    assert r.returncode == 0, r.stderr
