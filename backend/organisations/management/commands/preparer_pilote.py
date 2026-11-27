"""Prépare les classes du pilote, sans jamais rien écraser : on peut le relancer à chaque déploiement.

- « Prépa ECG1 — Cathy » : les parcours de prépa ;
- « Terminale S2 » : maths (complexes, étude de fonction) et physique (P1, P2) ;
- « M1 MCS — Alseny » : classe privée où l'admin travaille comme élève (ses parcours du master).

Seules les classes absentes sont créées ; un parcours n'est rattaché que s'il existe et ne l'est
pas déjà. Les élèves rejoignent une classe avec son code d'inscription (visible dans « Classes »).
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from comptes.models import Utilisateur
from contenus.models import Parcours, Rattachement
from organisations.models import AnneeScolaire, Groupe, Inscription, Organisation

CLASSES = [
    {
        "nom": "Prépa ECG1 — Cathy", "cycle": "prepa", "privee": False,
        "parcours": ["prepa-algebre-lineaire", "prepa-suites-fonctions", "prepa-limites-suites"],
    },
    {
        "nom": "Terminale S2", "cycle": "lycee", "privee": False,
        "parcours": ["nombres-complexes", "etude-de-fonction", "physique-p1-cinematique", "physique-p2-dynamique"],
    },
    {
        "nom": "M1 MCS — Alseny", "cycle": "universite", "privee": True,
        "parcours": [
            "complexite-algorithmes", "mcs-fondements-niveau-0", "mcs-fondements-niveau-1", "mcs-fondements-niveau-2",
            "mcs-fondements-niveau-3", "mcs-fondements-niveau-4", "reseaux-securite-s2",
        ],
    },
]


class Command(BaseCommand):
    help = "Crée les classes du pilote (Cathy, Terminale S2, M1 MCS) et y rattache les parcours, sans rien écraser."

    @transaction.atomic
    def handle(self, **_):
        organisation = Organisation.objects.order_by("cree_le").first()
        annee = AnneeScolaire.objects.filter(en_cours=True).first() or AnneeScolaire.objects.first()
        if organisation is None or annee is None:
            self.stdout.write("Lancer d'abord initialiser_plateforme (organisation et année).")
            return
        admin = Utilisateur.objects.filter(is_superuser=True).order_by("date_joined").first()
        for modele in CLASSES:
            groupe, cree = Groupe.objects.get_or_create(
                organisation=organisation, annee=annee, nom=modele["nom"],
                defaults={"cycle": modele["cycle"], "inscriptions_ouvertes": not modele["privee"]},
            )
            if cree:
                self.stdout.write(f"Classe « {groupe.nom} » créée (code {groupe.code_inscription}).")
            for ordre, slug in enumerate(modele["parcours"]):
                parcours = Parcours.objects.filter(slug=slug).first()
                if parcours and not Rattachement.objects.filter(groupe=groupe, parcours=parcours).exists():
                    Rattachement.objects.create(groupe=groupe, parcours=parcours, ordre=ordre)
                    self.stdout.write(f"  + {parcours.titre}")
            if modele["privee"] and admin and not Inscription.objects.filter(utilisateur=admin, groupe=groupe).exists():
                Inscription.objects.create(utilisateur=admin, groupe=groupe, role=Inscription.Role.ELEVE).valider(par=admin)
                self.stdout.write(f"  {admin.prenom} inscrit comme élève.")
