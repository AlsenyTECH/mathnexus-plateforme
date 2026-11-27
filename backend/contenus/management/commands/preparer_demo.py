"""Prépare une classe de démonstration pour essayer les évaluations en local.

    set DJANGO_DEBUG=1
    python manage.py preparer_demo

Crée (si absents) l'organisation, l'année en cours, la classe « Démo évaluations », le parcours
d'essai au format 2 (importé, publié, rattaché) et un compte élève actif inscrit dans la classe.
Refuse de tourner hors du mode développement : ce n'est pas un outil de production.
"""
import datetime
import secrets

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from comptes.models import Utilisateur
from contenus.exemple import paquet_exemple
from contenus.importation import importer_paquet
from contenus.models import Parcours, Rattachement
from organisations.models import AnneeScolaire, Groupe, Inscription, Organisation


class Command(BaseCommand):
    help = "Classe de démonstration avec le parcours d'essai des évaluations (développement seulement)."

    def add_arguments(self, parser):
        parser.add_argument("--telephone", default="770000001", help="Numéro de l'élève de démonstration")
        parser.add_argument("--mot-de-passe", help="Par défaut : tiré au hasard et affiché une fois")

    @transaction.atomic
    def handle(self, telephone, mot_de_passe, **_):
        if not settings.DEBUG:
            raise CommandError("preparer_demo ne tourne qu'en développement (DJANGO_DEBUG=1).")
        organisation, _ = Organisation.objects.get_or_create(slug="mathnexus", defaults={"nom": "Mathnexus Education"})
        annee = AnneeScolaire.objects.filter(en_cours=True).first() or AnneeScolaire.objects.create(
            libelle="2026-2027", debut=datetime.date(2026, 10, 1), fin=datetime.date(2027, 7, 31), en_cours=True)
        groupe, _ = Groupe.objects.get_or_create(
            organisation=organisation, annee=annee, nom="Démo évaluations", defaults={"cycle": "lycee"})

        parcours = Parcours.objects.filter(slug="demo-evaluations").first()
        if parcours is None:
            importer_paquet(paquet_exemple()).publier()
            parcours = Parcours.objects.get(slug="demo-evaluations")
        elif parcours.version_publiee() is None:
            parcours.versions.order_by("-numero").first().publier()
        Rattachement.objects.get_or_create(groupe=groupe, parcours=parcours)

        eleve = Utilisateur.objects.filter(telephone__endswith=telephone[-9:]).first()
        if eleve is None:
            mot_de_passe = mot_de_passe or secrets.token_urlsafe(9)
            eleve = Utilisateur.objects.create_user(telephone, mot_de_passe, prenom="Élève", nom="Démo", statut="actif")
            self.stdout.write(f"Élève créé : {eleve.telephone}, mot de passe : {mot_de_passe} (affiché une seule fois)")
        else:
            self.stdout.write(f"Élève existant : {eleve.telephone} (mot de passe inchangé)")
        if not Inscription.objects.filter(utilisateur=eleve, groupe=groupe).exists():
            Inscription.objects.create(utilisateur=eleve, groupe=groupe, role="eleve").valider(par=None)

        self.stdout.write(self.style.SUCCESS(
            f"Classe « {groupe.nom} » prête. Étape avec le QCM :\n"
            f"  http://localhost:5173/classe/{groupe.id}/demo-evaluations/module-conjugue"))
