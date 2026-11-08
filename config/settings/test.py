import os

from .base import *  # noqa: F403
from .base import BASE_DIR

SECRET_KEY = "test-only-key"
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
RATELIMIT_BACKEND = "memory"
TRUSTED_PROXY_COUNT = 0
SITE_URL = "http://testserver"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
STORAGES = {  # noqa: F405
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# CI sets DATABASE_URL to a real PostgreSQL service. Without it (quick local runs),
# fall back to SQLite so unit tests still work. Always run the full suite on PostgreSQL.
if not os.environ.get("DATABASE_URL"):
    DATABASES = {  # noqa: F405
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "test.sqlite3"}
    }
