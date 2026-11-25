import datetime


import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

MDP = "Cahier-quadrille-2026"


@pytest.fixture(autouse=True)
def _cache_vide():
    cache.clear()  # la limitation des tentatives repart de zéro à chaque test
    yield
    cache.clear()


@pytest.fixture
def client_api():
    return APIClient()


@pytest.fixture
def organisation(db):
    from organisations.models import Organisation

    return Organisation.objects.create(nom="Mathnexus Education", slug="mathnexus")


@pytest.fixture
def annee(db):
    from organisations.models import AnneeScolaire

    return AnneeScolaire.objects.create(
        libelle="2026-2027", debut=datetime.date(2026, 10, 1), fin=datetime.date(2027, 7, 31), en_cours=True
    )


@pytest.fixture
def terminale(organisation, annee):
    from organisations.models import Groupe

    return Groupe.objects.create(organisation=organisation, annee=annee, nom="Terminale S2", cycle="lycee")


@pytest.fixture
def prepa(organisation, annee):
    from organisations.models import Groupe

    return Groupe.objects.create(organisation=organisation, annee=annee, nom="ECG 1", cycle="prepa")


@pytest.fixture
def admin(db):
    from comptes.models import Utilisateur

    return Utilisateur.objects.create_superuser("771000000", MDP, prenom="Alseny", nom="Diallo")


@pytest.fixture
def creer_eleve(db):
    """Fabrique un élève actif inscrit (et validé) dans les groupes donnés."""
    from comptes.models import Utilisateur
    from organisations.models import Inscription

    compteur = {"n": 0}

    def fabrique(*groupes, telephone=None, role="eleve", statut="actif"):
        compteur["n"] += 1
        tel = telephone or f"77200{compteur['n']:04d}"
        u = Utilisateur.objects.create_user(tel, MDP, prenom=f"Élève{compteur['n']}", nom="Test", statut=statut)
        for g in groupes:
            Inscription.objects.create(utilisateur=u, groupe=g, role=role).valider(par=None)
        return u

    return fabrique


def connecter(client, utilisateur):
    client.force_login(utilisateur)
    return client
