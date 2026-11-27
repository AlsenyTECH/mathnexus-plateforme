"""Étape de construction sur Vercel : prépare la base, seulement pour la production.

Les déploiements de prévisualisation (branches, pull requests) ne touchent jamais la base.
"""
import os
import subprocess
import sys


def manage(*args):
    subprocess.run([sys.executable, "manage.py", *args], check=True)


if __name__ == "__main__":
    if os.environ.get("VERCEL_ENV") == "production":
        if not os.environ.get("DATABASE_URL"):
            # Sans base PostgreSQL, Vercel garderait une base SQLite jetable : tout serait perdu.
            sys.exit(
                "DATABASE_URL manque : branchez une base PostgreSQL (Vercel → Storage → Neon) "
                "au projet mathnexus-api pour la Production, puis redéployez."
            )
        manage("migrate", "--noinput")
        manage("createcachetable")
        manage("initialiser_plateforme")
        manage("preparer_pilote")
    else:
        print("Déploiement de prévisualisation : la base n'est pas modifiée.")
