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
        manage("migrate", "--noinput")
        manage("createcachetable")
        manage("initialiser_plateforme")
    else:
        print("Déploiement de prévisualisation : la base n'est pas modifiée.")
