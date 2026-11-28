import pytest

from comptes.models import JournalAudit, Utilisateur
from conftest import MDP, connecter
from organisations.models import Groupe, Inscription

pytestmark = pytest.mark.django_db


def inscrire_en_attente(client, **autres):
    donnees = {
        "prenom": "Moussa", "nom": "Sow", "telephone": "781112233", "mot_de_passe": MDP,
        "est_mineur": False, "accepte_conditions": True,
    }
    donnees.update(autres)
    r = client.post("/api/auth/inscription/", donnees, format="json")
    assert r.status_code == 201, r.data
    return Utilisateur.objects.get(telephone="+221781112233")


# --- Codes de classe -------------------------------------------------------------

def test_code_de_classe_genere_et_lisible(terminale):
    code = terminale.code_inscription
    assert code.startswith("TERM-2026-")
    assert not set(code.split("-")[-1]) & set("01OIL")  # pas de caractères ambigus


def test_regenerer_le_code(client_api, admin, terminale):
    ancien = terminale.code_inscription
    connecter(client_api, admin)
    r = client_api.post(f"/api/admin/groupes/{terminale.id}/regenerer-code/")
    assert r.status_code == 200 and r.data["code_inscription"] != ancien


# --- Validation des comptes --------------------------------------------------------

def test_admin_valide_un_compte_venu_par_code(client_api, admin, terminale):
    eleve = inscrire_en_attente(client_api, code_classe=terminale.code_inscription)
    client_api.logout()
    connecter(client_api, admin)
    attente = client_api.get("/api/admin/comptes-en-attente/").data
    assert [c["telephone"] for c in attente] == ["+221781112233"]
    assert attente[0]["demandes"][0]["groupe"] == str(terminale.id)

    r = client_api.post(f"/api/admin/comptes/{eleve.id}/valider/", format="json")
    assert r.status_code == 200 and r.data["statut"] == "actif"
    assert Inscription.objects.get(utilisateur=eleve).statut == "validee"
    assert JournalAudit.objects.filter(action="compte_valide", acteur=admin).exists()


def test_admin_doit_choisir_la_classe_si_pas_de_code(client_api, admin, terminale):
    eleve = inscrire_en_attente(client_api)
    client_api.logout()
    connecter(client_api, admin)
    r = client_api.post(f"/api/admin/comptes/{eleve.id}/valider/", format="json")
    assert r.status_code == 400 and "groupe" in r.data
    r = client_api.post(f"/api/admin/comptes/{eleve.id}/valider/", {"groupe": str(terminale.id)}, format="json")
    assert r.status_code == 200
    assert eleve.inscriptions.get().groupe == terminale


def test_refus_supprime_le_compte(client_api, admin):
    eleve = inscrire_en_attente(client_api)
    client_api.logout()
    connecter(client_api, admin)
    assert client_api.post(f"/api/admin/comptes/{eleve.id}/refuser/").status_code == 204
    assert not Utilisateur.objects.filter(id=eleve.id).exists()


def test_compte_en_attente_ne_voit_aucune_classe(client_api, terminale):
    inscrire_en_attente(client_api, code_classe=terminale.code_inscription)
    assert client_api.get("/api/groupes/").data == []
    assert client_api.get(f"/api/groupes/{terminale.id}/").status_code == 404


def test_suspension_coupe_l_acces_immediatement(client_api, admin, terminale, creer_eleve):
    from rest_framework.test import APIClient

    eleve = creer_eleve(terminale, telephone="772223344")
    client_eleve = APIClient()
    client_eleve.post("/api/auth/connexion/", {"telephone": "772223344", "mot_de_passe": MDP}, format="json")
    assert client_eleve.get("/api/groupes/").status_code == 200
    connecter(client_api, admin)
    assert client_api.post(f"/api/admin/comptes/{eleve.id}/suspendre/", {"motif": "test"}, format="json").status_code == 200
    assert client_eleve.get("/api/groupes/").status_code == 403


def test_les_routes_admin_sont_fermees_aux_eleves(client_api, terminale, creer_eleve):
    connecter(client_api, creer_eleve(terminale))
    assert client_api.get("/api/admin/comptes-en-attente/").status_code == 403
    assert client_api.get("/api/admin/groupes/").status_code == 403
    assert client_api.post(f"/api/admin/groupes/{terminale.id}/regenerer-code/").status_code == 403


def test_routes_fermees_sans_connexion(client_api, terminale):
    assert client_api.get("/api/moi/").status_code == 403
    assert client_api.get("/api/groupes/").status_code == 403


# --- Isolement entre classes --------------------------------------------------------

def test_un_eleve_ne_voit_que_sa_classe(client_api, terminale, prepa, creer_eleve):
    connecter(client_api, creer_eleve(terminale))
    r = client_api.get("/api/groupes/")
    assert [g["id"] for g in r.data] == [str(terminale.id)]
    assert r.data[0]["mon_role"] == "eleve"
    assert client_api.get(f"/api/groupes/{prepa.id}/").status_code == 404  # 404, pas 403


@pytest.mark.parametrize("statut", ["en_attente", "refusee"])
def test_une_inscription_non_validee_n_ouvre_pas_la_classe(client_api, terminale, prepa, creer_eleve, statut):
    eleve = creer_eleve(terminale)
    Inscription.objects.create(utilisateur=eleve, groupe=prepa, statut=statut)
    connecter(client_api, eleve)
    assert [g["id"] for g in client_api.get("/api/groupes/").data] == [str(terminale.id)]
    assert client_api.get(f"/api/groupes/{prepa.id}/").status_code == 404
    assert client_api.get("/api/moi/").data["destination"] == {"type": "groupe", "groupe": str(terminale.id)}


def test_un_prof_en_attente_ne_voit_pas_les_eleves(client_api, terminale, creer_eleve):
    creer_eleve(terminale)
    prof = creer_eleve()
    Inscription.objects.create(utilisateur=prof, groupe=terminale, role="prof", statut="en_attente")
    connecter(client_api, prof)
    assert client_api.get(f"/api/groupes/{terminale.id}/membres/").status_code == 404


def test_un_eleve_ne_voit_pas_la_liste_de_sa_classe(client_api, terminale, creer_eleve):
    connecter(client_api, creer_eleve(terminale))
    assert client_api.get(f"/api/groupes/{terminale.id}/membres/").status_code == 404


def test_un_prof_voit_ses_eleves_mais_pas_ceux_des_autres(client_api, terminale, prepa, creer_eleve):
    creer_eleve(terminale)
    creer_eleve(terminale)
    creer_eleve(prepa)
    prof = creer_eleve(terminale, role="prof")
    connecter(client_api, prof)
    assert client_api.get("/api/moi/").data["destination"] == {"type": "prof"}
    r = client_api.get(f"/api/groupes/{terminale.id}/membres/")
    assert r.status_code == 200
    assert sorted(m["role"] for m in r.data) == ["eleve", "eleve", "prof"]
    assert client_api.get(f"/api/groupes/{prepa.id}/membres/").status_code == 404


def test_une_classe_archivee_disparait(client_api, terminale, creer_eleve):
    connecter(client_api, creer_eleve(terminale))
    terminale.archive = True
    terminale.save()
    assert client_api.get("/api/groupes/").data == []
    assert client_api.get("/api/moi/").data["destination"] == {"type": "aucun_groupe"}


# --- Import d'une liste de classe ---------------------------------------------------

def test_import_cree_les_comptes_avec_mot_de_passe_provisoire(client_api, admin, terminale, creer_eleve):
    deja = creer_eleve(telephone="779990000")
    connecter(client_api, admin)
    r = client_api.post(f"/api/admin/groupes/{terminale.id}/importer/", {"eleves": [
        {"prenom": "Fatou", "nom": "Ba", "telephone": "77 300 00 01"},
        {"prenom": "Ibou", "nom": "Fall", "telephone": "77 300 00 02"},
        {"prenom": "Déjà", "nom": "Inscrit", "telephone": "77 999 00 00"},
    ]}, format="json")
    assert r.status_code == 201, r.data
    etats = {x["telephone"]: x for x in r.data["resultats"]}
    assert etats["+221779990000"]["etat"] == "rattache" and "mot_de_passe_provisoire" not in etats["+221779990000"]
    fatou = Utilisateur.objects.get(telephone="+221773000001")
    assert fatou.statut == "actif" and fatou.doit_changer_mot_de_passe
    assert fatou.check_password(etats["+221773000001"]["mot_de_passe_provisoire"])
    assert terminale.inscriptions.filter(statut="validee").count() == 3
    assert deja.inscriptions.get().groupe == terminale


def test_import_active_un_compte_qui_etait_en_attente(client_api, admin, terminale):
    eleve = inscrire_en_attente(client_api)
    client_api.logout()
    connecter(client_api, admin)
    r = client_api.post(f"/api/admin/groupes/{terminale.id}/importer/", {"eleves": [
        {"prenom": "Moussa", "nom": "Sow", "telephone": "78 111 22 33"},
    ]}, format="json")
    assert r.data["resultats"][0]["etat"] == "rattache"
    eleve.refresh_from_db()
    assert eleve.statut == "actif"


def test_compte_en_attente_avec_inscription_validee_ne_voit_rien(client_api, terminale, creer_eleve):
    """Défense en profondeur : sans compte actif, une inscription validée n'ouvre rien."""
    eleve = creer_eleve(terminale, statut="en_attente")
    connecter(client_api, eleve)
    assert client_api.get("/api/groupes/").data == []
    assert client_api.get(f"/api/groupes/{terminale.id}/").status_code == 404


def test_import_tout_ou_rien_si_une_ligne_est_fausse(client_api, admin, terminale):
    connecter(client_api, admin)
    r = client_api.post(f"/api/admin/groupes/{terminale.id}/importer/", {"eleves": [
        {"prenom": "Fatou", "nom": "Ba", "telephone": "77 300 00 01"},
        {"prenom": "Erreur", "nom": "Numéro", "telephone": "123"},
    ]}, format="json")
    assert r.status_code == 400
    assert not Utilisateur.objects.filter(telephone="+221773000001").exists()


def test_admin_cree_un_groupe(client_api, admin, organisation, annee):
    connecter(client_api, admin)
    r = client_api.post("/api/admin/groupes/", {
        "nom": "M1 MCS", "cycle": "universite", "organisation": str(organisation.id), "annee": annee.id,
    }, format="json")
    assert r.status_code == 201, r.data
    assert Groupe.objects.get(nom="M1 MCS").code_inscription == r.data["code_inscription"]


def test_referentiel_pour_les_formulaires(client_api, admin, organisation, annee, terminale, creer_eleve):
    connecter(client_api, admin)
    r = client_api.get("/api/admin/referentiel/")
    assert r.data["organisations"] == [{"id": str(organisation.id), "nom": "Mathnexus Education"}]
    assert r.data["annees"][0]["libelle"] == "2026-2027"
    connecter(client_api, creer_eleve(terminale))
    assert client_api.get("/api/admin/referentiel/").status_code == 403


def test_admin_au_mot_de_passe_provisoire_le_change_d_abord(client_api, admin):
    admin.doit_changer_mot_de_passe = True
    admin.save()
    connecter(client_api, admin)
    assert client_api.get("/api/moi/").data["destination"] == {"type": "changer_mot_de_passe"}


def test_initialiser_plateforme_est_idempotent(db, monkeypatch):
    from django.core.management import call_command

    from comptes.models import Utilisateur as U
    from contenus.models import Parcours, VersionParcours
    from organisations.models import AnneeScolaire, Organisation

    monkeypatch.setenv("ADMIN_TELEPHONE", "77 100 00 00")
    monkeypatch.setenv("ADMIN_MOT_DE_PASSE_PROVISOIRE", "Provisoire-tres-long-2026")
    from pathlib import Path

    from comptes.management.commands.initialiser_plateforme import DOSSIER_PAQUETS
    from organisations.models import Groupe, Inscription

    paquets = {p.stem for p in Path(DOSSIER_PAQUETS).glob("*.zip")}
    assert {"nombres-complexes", "prepa-algebre-lineaire", "complexite-algorithmes"} <= paquets
    for _ in range(2):
        call_command("initialiser_plateforme")
        call_command("preparer_pilote")
    admin = U.objects.get(is_superuser=True)
    assert admin.telephone == "+221771000000" and admin.doit_changer_mot_de_passe
    assert Organisation.objects.count() == 1 and AnneeScolaire.objects.filter(en_cours=True).count() == 1
    assert set(Parcours.objects.values_list("slug", flat=True)) == paquets
    assert VersionParcours.objects.filter(statut="publiee").count() == len(paquets)
    assert VersionParcours.objects.count() == len(paquets)  # rien n'est réimporté
    # Les classes du pilote : créées une seule fois, l'admin élève de sa classe de master
    assert Groupe.objects.count() == 3
    m1 = Groupe.objects.get(nom="M1 MCS — Alseny")
    assert Inscription.objects.get(groupe=m1).role == "eleve" and not m1.inscriptions_ouvertes
    assert all(c.isascii() for c in Groupe.objects.get(nom="Prépa ECG1 — Cathy").code_inscription)


def test_annee_scolaire_commence_en_octobre():
    import datetime

    from comptes.management.commands.initialiser_plateforme import annee_en_cours

    assert annee_en_cours(datetime.date(2026, 11, 25))[0] == "2026-2027"
    assert annee_en_cours(datetime.date(2027, 3, 1))[0] == "2026-2027"
    assert annee_en_cours(datetime.date(2027, 10, 2))[0] == "2027-2028"


def test_mot_de_passe_provisoire_oublie_se_remet_tant_qu_il_n_a_pas_ete_change(db, monkeypatch):
    """Changer la variable puis redéployer redonne l'accès, mais jamais une fois le mot de passe choisi."""
    from django.core.management import call_command

    from comptes.models import Utilisateur as U

    monkeypatch.setenv("ADMIN_TELEPHONE", "771000000")
    monkeypatch.setenv("ADMIN_MOT_DE_PASSE_PROVISOIRE", "Premier-provisoire-2026")
    call_command("initialiser_plateforme")
    monkeypatch.setenv("ADMIN_MOT_DE_PASSE_PROVISOIRE", "Second-provisoire-2026")
    call_command("initialiser_plateforme")
    admin = U.objects.get(is_superuser=True)
    assert admin.check_password("Second-provisoire-2026")

    # Une fois son propre mot de passe choisi, la variable ne compte plus.
    admin.set_password("Mon-vrai-mot-de-passe-2026")
    admin.doit_changer_mot_de_passe = False
    admin.save()
    monkeypatch.setenv("ADMIN_MOT_DE_PASSE_PROVISOIRE", "Troisieme-provisoire-2026")
    call_command("initialiser_plateforme")
    admin.refresh_from_db()
    assert admin.check_password("Mon-vrai-mot-de-passe-2026")
