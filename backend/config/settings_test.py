"""Réglages des tests : SQLite en mémoire par défaut, PostgreSQL si TEST_DATABASE_URL est défini."""
import os

os.environ["DJANGO_DEBUG"] = "1"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("REDIS_URL", None)

from .settings import *  # noqa: E402,F401,F403

if os.environ.get("TEST_DATABASE_URL"):
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(os.environ["TEST_DATABASE_URL"])}  # noqa: F405
