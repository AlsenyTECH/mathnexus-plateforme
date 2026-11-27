import pytest
from django.core.exceptions import ValidationError

from comptes.models import JournalAudit, SessionAppareil, Utilisateur
from comptes.telephone import normaliser_telephone
from conftest import MDP, connecter
from organisations.models import Inscription

pytestmark = pytest.mark.django_db


def formulaire(**autres):
    donnees = {
        "prenom": "Awa", "nom": "Ndiaye", "telephone": "77 123 45 67", "mot_de_passe": MDP,
        "niveau_declare": "Terminale S2", "est_mineur": True, "telephone_parent": "76 555 44 33",
        "accepte_conditions": True,
    }
    donnees.update(autres)
    return donnees


# --- Téléphone -------------------------------------------------------------------

@pytest.mark.parametrize("saisie,attendu", [
    ("77 123 45 67", "+221771234567"),
    ("+221 77-123-45-67", "+221771234567"),
    ("00221771234567", "+221771234567"),
    ("338201234", "+221338201234"),
    ("+33612345678", "+33612345678"),
])
def test_normalisation_du_telephone(saisie, attendu):
    assert normaliser_telephone(saisie) == attendu


@pytest.mark.parametrize("saisie", ["12345", "abc", "", "88 123 45 67"])
def test_telephone_invalide_refuse(saisie):
    with pytest.raises(ValidationError):
        normaliser_telephone(saisie)


# --- Inscription -------------------------------------------------------------------

def test_inscription_sans_code_cree_un_compte_en_attente(client_api):
    r = client_api.post("/api/auth/inscription/", formulaire(), format="json")
    assert r.status_code == 201, r.data
    u = Utilisateur.objects.get(telephone="+221771234567")
    assert u.statut == "en_attente"
    assert u.password.startswith("argon2")  # haché en Argon2id
    assert u.cgu_acceptees_le is not None
    assert r.data["destination"] == {"type": "attente"}
    assert not u.inscriptions.exists()


def test_inscription_avec_code_range_dans_la_bonne_classe(client_api, terminale):
    r = client_api.post("/api/auth/inscription/", formulaire(code_classe=terminale.code_inscription.lower()), format="json")
    assert r.status_code == 201, r.data
    inscription = Inscription.objects.get(utilisateur__telephone="+221771234567")
    assert inscription.groupe == terminale
    assert inscription.statut == "en_attente"
    assert r.data["destination"] == {"type": "attente"}


def test_code_avec_validation_automatique_donne_acces_direct(client_api, terminale):
    terminale.validation_automatique = True
    terminale.save()
    r = client_api.post("/api/auth/inscription/", formulaire(code_classe=terminale.code_inscription), format="json")
    assert r.status_code == 201
    assert r.data["utilisateur"]["statut"] == "actif"
    assert r.data["destination"] == {"type": "groupe", "groupe": str(terminale.id)}


def test_code_inconnu_ou_ferme_refuse(client_api, terminale):
    r = client_api.post("/api/auth/inscription/", formulaire(code_classe="FAUX-2026-XXXXX"), format="json")
    assert r.status_code == 400 and "code_classe" in r.data
    terminale.inscriptions_ouvertes = False
    terminale.save()
    r = client_api.post("/api/auth/inscription/", formulaire(code_classe=terminale.code_inscription), format="json")
    assert r.status_code == 400 and "code_classe" in r.data


def test_mineur_sans_telephone_parent_refuse(client_api):
    r = client_api.post("/api/auth/inscription/", formulaire(telephone_parent=""), format="json")
    assert r.status_code == 400 and "telephone_parent" in r.data


def test_conditions_non_acceptees_refuse(client_api):
    r = client_api.post("/api/auth/inscription/", formulaire(accepte_conditions=False), format="json")
    assert r.status_code == 400 and "accepte_conditions" in r.data


def test_mot_de_passe_faible_refuse(client_api):
    r = client_api.post("/api/auth/inscription/", formulaire(mot_de_passe="12345678"), format="json")
    assert r.status_code == 400 and "mot_de_passe" in r.data


def test_numero_deja_utilise_refuse(client_api):
    client_api.post("/api/auth/inscription/", formulaire(), format="json")
    r = client_api.post("/api/auth/inscription/", formulaire(telephone="+221771234567"), format="json")
    assert r.status_code == 400 and "telephone" in r.data


# --- Connexion -------------------------------------------------------------------

def test_connexion_exige_le_jeton_csrf(creer_eleve):
    from rest_framework.test import APIClient

    creer_eleve(telephone="772223344")
    client = APIClient(enforce_csrf_checks=True)
    sans_jeton = client.post("/api/auth/connexion/", {"telephone": "772223344", "mot_de_passe": MDP}, format="json")
    assert sans_jeton.status_code == 403
    client.get("/api/auth/csrf/")
    jeton = client.cookies["csrftoken"].value
    avec_jeton = client.post(
        "/api/auth/connexion/", {"telephone": "772223344", "mot_de_passe": MDP}, format="json", HTTP_X_CSRFTOKEN=jeton
    )
    assert avec_jeton.status_code == 200


def test_connexion_et_redirection_vers_la_classe(client_api, terminale, creer_eleve):
    eleve = creer_eleve(terminale, telephone="772223344")
    r = client_api.post("/api/auth/connexion/", {"telephone": "77 222 33 44", "mot_de_passe": MDP}, format="json")
    assert r.status_code == 200, r.data
    assert r.data["destination"] == {"type": "groupe", "groupe": str(terminale.id)}
    assert SessionAppareil.objects.filter(utilisateur=eleve).count() == 1


def test_mauvais_mot_de_passe_meme_message_que_compte_inconnu(client_api, creer_eleve):
    creer_eleve(telephone="772223344")
    r1 = client_api.post("/api/auth/connexion/", {"telephone": "772223344", "mot_de_passe": "faux"}, format="json")
    r2 = client_api.post("/api/auth/connexion/", {"telephone": "779999999", "mot_de_passe": "faux"}, format="json")
    assert r1.status_code == r2.status_code == 400
    assert r1.data == r2.data == {"detail": "Identifiants incorrects."}


def test_limitation_des_tentatives_de_connexion(client_api, creer_eleve):
    creer_eleve(telephone="772223344")
    codes = [
        client_api.post("/api/auth/connexion/", {"telephone": "772223344", "mot_de_passe": "faux"}, format="json").status_code
        for _ in range(6)
    ]
    assert codes[:5] == [400] * 5
    assert codes[5] == 429  # sixième essai dans la minute : bloqué


def test_compte_suspendu_ne_peut_pas_se_connecter(client_api, creer_eleve):
    creer_eleve(telephone="772223344", statut="suspendu")
    r = client_api.post("/api/auth/connexion/", {"telephone": "772223344", "mot_de_passe": MDP}, format="json")
    assert r.status_code == 403


def test_au_plus_deux_appareils_par_compte(creer_eleve, terminale):
    from django.contrib.sessions.models import Session
    from rest_framework.test import APIClient

    eleve = creer_eleve(terminale, telephone="772223344")
    clients = [APIClient() for _ in range(3)]
    for c in clients:
        assert c.post("/api/auth/connexion/", {"telephone": "772223344", "mot_de_passe": MDP}, format="json").status_code == 200
    assert SessionAppareil.objects.filter(utilisateur=eleve).count() == 2
    assert Session.objects.count() == 2
    assert clients[0].get("/api/moi/").status_code == 403  # le plus ancien appareil est déconnecté
    assert clients[2].get("/api/moi/").status_code == 200


def test_eleve_avec_plusieurs_classes_choisit_puis_est_retenu(client_api, terminale, prepa, creer_eleve):
    eleve = creer_eleve(terminale, prepa)
    connecter(client_api, eleve)
    r = client_api.get("/api/moi/")
    assert r.data["destination"]["type"] == "choix_groupe"
    r = client_api.post("/api/moi/groupe-courant/", {"groupe": str(prepa.id)}, format="json")
    assert r.data["destination"] == {"type": "groupe", "groupe": str(prepa.id)}


def test_mot_de_passe_provisoire_force_le_changement(client_api, terminale, creer_eleve):
    eleve = creer_eleve(terminale)
    eleve.doit_changer_mot_de_passe = True
    eleve.save()
    connecter(client_api, eleve)
    assert client_api.get("/api/moi/").data["destination"] == {"type": "changer_mot_de_passe"}
    r = client_api.post("/api/moi/mot-de-passe/", {"actuel": MDP, "nouveau": "Nouveau-cahier-2027"}, format="json")
    assert r.status_code == 200, r.data
    assert r.data["destination"]["type"] == "groupe"
    assert JournalAudit.objects.filter(action="mot_de_passe_change").exists()


def test_etat_de_session_sans_erreur(client_api, terminale, creer_eleve):
    assert client_api.get("/api/auth/session/").data == {"utilisateur": None, "destination": None}
    eleve = creer_eleve(terminale)
    connecter(client_api, eleve)
    r = client_api.get("/api/auth/session/")
    assert r.data["utilisateur"]["id"] == str(eleve.id)
    assert r.data["destination"] == {"type": "groupe", "groupe": str(terminale.id)}
    eleve.statut = "suspendu"
    eleve.save()
    assert client_api.get("/api/auth/session/").data["utilisateur"] is None


# --- Numéro tapé sans indicatif : admin Django et createsuperuser ------------------------

def test_get_by_natural_key_normalise_le_numero(admin):
    """Le compte « +221771000000 » se retrouve quelle que soit l'écriture du numéro."""
    for saisie in ("771000000", "77 100 00 00", "+221771000000", "00221771000000"):
        assert Utilisateur.objects.get_by_natural_key(saisie) == admin
    with pytest.raises(Utilisateur.DoesNotExist):
        Utilisateur.objects.get_by_natural_key("pas un numéro")


def test_connexion_admin_django_sans_indicatif(client, db):
    Utilisateur.objects.create_superuser("+221775148833", MDP, prenom="Alseny", nom="Diallo")
    reponse = client.post("/gestion/login/?next=/gestion/", {"username": "775148833", "password": MDP})
    assert reponse.status_code == 302 and reponse.url == "/gestion/"
    assert client.get("/gestion/").status_code == 200


def test_createsuperuser_reconnait_un_numero_deja_pris(db, monkeypatch):
    from django.core.management import CommandError, call_command

    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", MDP)
    options = {"interactive": False, "prenom": "Alseny", "nom": "Diallo", "verbosity": 0}
    call_command("createsuperuser", telephone="775148833", **options)
    assert Utilisateur.objects.get().telephone == "+221775148833"
    with pytest.raises(CommandError, match="already taken|déjà"):
        call_command("createsuperuser", telephone="77 514 88 33", **options)
