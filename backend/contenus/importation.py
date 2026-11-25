from django.db import transaction
from django.db.models import Max

from .models import Etape, Matiere, Parcours, Partie, VersionParcours
from .paquet import lire_paquet


class PaquetDejaImporte(Exception):
    def __init__(self, version):
        self.version = version
        super().__init__(f"Ce paquet est identique à la version {version.numero}.")


@transaction.atomic
def importer_paquet(donnees: bytes, par=None) -> VersionParcours:
    """Valide le paquet puis crée une nouvelle version en brouillon.

    Lève PaquetInvalide (problèmes de contenu) ou PaquetDejaImporte.
    Rien n'est écrit si le paquet est refusé.
    """
    lu = lire_paquet(donnees)
    matiere, _ = Matiere.objects.get_or_create(nom=lu.matiere)
    parcours, cree = Parcours.objects.select_for_update().get_or_create(
        slug=lu.slug,
        defaults={"titre": lu.titre, "matiere": matiere, "cycle": lu.cycle, "description": lu.description},
    )
    if not cree:
        derniere = parcours.versions.order_by("-numero").first()
        if derniere and derniere.empreinte == lu.empreinte:
            raise PaquetDejaImporte(derniere)
        parcours.titre, parcours.matiere, parcours.cycle, parcours.description = (
            lu.titre, matiere, lu.cycle, lu.description,
        )
        parcours.save()

    numero = (parcours.versions.aggregate(m=Max("numero"))["m"] or 0) + 1
    version = VersionParcours.objects.create(
        parcours=parcours, numero=numero, empreinte=lu.empreinte, manifeste=lu.manifeste,
        importee_par=par if par and par.is_authenticated else None,
    )
    ordre = 0
    for i, pl in enumerate(lu.parties, 1):
        partie = Partie.objects.create(version=version, cle=pl.cle, titre=pl.titre, ordre=i)
        for el in pl.etapes:
            ordre += 1
            Etape.objects.create(
                version=version, partie=partie, cle=el.cle, titre=el.titre, ordre=ordre,
                duree_min=el.duree_min, acces=el.acces, html=el.html,
            )
    return version
