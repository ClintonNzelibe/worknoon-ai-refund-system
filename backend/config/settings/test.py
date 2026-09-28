"""SQLite test settings so model tests can run without a local PostgreSQL service."""

from .base import *  # noqa: F403


DATABASES = {  # noqa: F405
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}
