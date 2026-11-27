from pathlib import Path

from django.core.management.base import BaseCommand

from contenus.exemple import paquet_exemple


class Command(BaseCommand):
    help = "Écrit le paquet d'essai au format 2 (QCM de sortie et évaluation chronométrée)."

    def add_arguments(self, parser):
        parser.add_argument("sortie", nargs="?", default="exemple-format2.zip")

    def handle(self, sortie, **_):
        donnees = paquet_exemple()
        Path(sortie).write_bytes(donnees)
        self.stdout.write(self.style.SUCCESS(f"{sortie} : {len(donnees)} octets"))
