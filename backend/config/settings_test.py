"""Réglages des tests : base SQLite en mémoire, cache local, pas de secret requis."""
import os

os.environ["DJANGO_DEBUG"] = "1"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("REDIS_URL", None)

from .settings import *  # noqa: E402,F401,F403
