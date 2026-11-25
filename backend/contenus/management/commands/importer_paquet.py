from django.core.management.base import BaseCommand, CommandError

from contenus.importation import PaquetDejaImporte, importer_paquet
from contenus.paquet import PaquetInvalide


class Command(BaseCommand):
    help = "Importe un paquet de parcours (.zip) en version brouillon ; --publier la publie aussitôt."

    def add_arguments(self, parser):
        parser.add_argument("chemin")
        parser.add_argument("--publier", action="store_true")

    def handle(self, chemin, publier, **_):
        try:
            with open(chemin, "rb") as f:
                version = importer_paquet(f.read())
        except PaquetInvalide as e:
            raise CommandError("Paquet refusé :\n  - " + "\n  - ".join(e.problemes))
        except PaquetDejaImporte as e:
            raise CommandError(str(e))
        if publier:
            version.publier()
        self.stdout.write(self.style.SUCCESS(
            f"{version.parcours.slug} v{version.numero} ({version.get_statut_display()}) : "
            f"{version.etapes.count()} étapes"
        ))
