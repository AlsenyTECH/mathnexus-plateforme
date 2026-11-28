"""Prépare une plateforme neuve, sans jamais rien écraser : on peut le relancer à chaque déploiement.

- crée l'organisation et l'année scolaire en cours si aucune n'existe ;
- crée le compte admin si aucun n'existe, avec un mot de passe provisoire à changer
  à la première connexion (ADMIN_TELEPHONE, ADMIN_PRENOM, ADMIN_NOM, ADMIN_MOT_DE_PASSE_PROVISOIRE) ;
- tant que cet admin n'a jamais choisi son mot de passe, lui redonne le mot de passe provisoire actuel
  (pour s'en sortir si on l'a oublié : changer la variable, puis redéployer) ;
- importe les paquets de contenus_initiaux/ qui ne le sont pas encore, et publie un parcours
  qui n'a pas encore de version publiée.
"""
import datetime
import os
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from comptes.models import Utilisateur
from comptes.telephone import normaliser_telephone
from contenus.importation import PaquetDejaImporte, importer_paquet
from contenus.models import VersionParcours
from contenus.paquet import PaquetInvalide
from organisations.models import AnneeScolaire, Organisation

DOSSIER_PAQUETS = Path(__file__).resolve().parents[3] / "contenus_initiaux"


def annee_en_cours(aujourd_hui=None):
    """Au Sénégal, l'année scolaire commence en octobre."""
    d = aujourd_hui or datetime.date.today()
    debut = d.year if d.month >= 10 else d.year - 1
    return f"{debut}-{debut + 1}", datetime.date(debut, 10, 1), datetime.date(debut + 1, 7, 31)


class Command(BaseCommand):
    help = "Prépare une plateforme neuve (organisation, année, admin, parcours initiaux), sans rien écraser."

    @transaction.atomic
    def handle(self, **_):
        if not Organisation.objects.exists():
            Organisation.objects.create(nom="Mathnexus Education", slug="mathnexus")
            self.stdout.write("Organisation « Mathnexus Education » créée.")
        if not AnneeScolaire.objects.exists():
            libelle, debut, fin = annee_en_cours()
            AnneeScolaire.objects.create(libelle=libelle, debut=debut, fin=fin, en_cours=True)
            self.stdout.write(f"Année scolaire {libelle} créée.")

        telephone = os.environ.get("ADMIN_TELEPHONE")
        mdp = os.environ.get("ADMIN_MOT_DE_PASSE_PROVISOIRE")
        if not Utilisateur.objects.filter(is_superuser=True).exists():
            if telephone and mdp:
                admin = Utilisateur.objects.create_superuser(
                    telephone, mdp,
                    prenom=os.environ.get("ADMIN_PRENOM", "Admin"), nom=os.environ.get("ADMIN_NOM", "Mathnexus"),
                )
                admin.doit_changer_mot_de_passe = True
                admin.save(update_fields=["doit_changer_mot_de_passe"])
                self.stdout.write(f"Compte admin {admin.telephone} créé (mot de passe à changer à la première connexion).")
            else:
                self.stdout.write("Aucun admin : définir ADMIN_TELEPHONE et ADMIN_MOT_DE_PASSE_PROVISOIRE.")
        elif telephone and mdp:
            admin = Utilisateur.objects.filter(is_superuser=True, telephone=normaliser_telephone(telephone)).first()
            if admin and admin.doit_changer_mot_de_passe and not admin.check_password(mdp):
                admin.set_password(mdp)
                admin.save(update_fields=["password"])
                self.stdout.write(f"Mot de passe provisoire de {admin.telephone} remis à jour (jamais changé).")

        for chemin in sorted(DOSSIER_PAQUETS.glob("*.zip")):
            try:
                version = importer_paquet(chemin.read_bytes())
            except PaquetDejaImporte:
                continue
            except PaquetInvalide as e:
                self.stderr.write(f"{chemin.name} refusé : {'; '.join(e.problemes)}")
                continue
            if not version.parcours.versions.filter(statut=VersionParcours.Statut.PUBLIEE).exists():
                version.publier()
            self.stdout.write(f"{chemin.name} : {version}.")
