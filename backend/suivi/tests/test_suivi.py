"""V1 : séance du jour, carnet d'erreurs, devoirs chronométrés, sujet joint, suivi, bilan, mot de passe.

Chaque règle d'accès a son test : un élève ne voit que lui, un prof que ses classes.
"""
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from comptes.models import Utilisateur
from conftest import connecter
from contenus import exemple
from contenus.importation import importer_paquet
from contenus.models import Rattachement
from evaluations.models import EntreeCarnet, Question

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n" + b"0" * 100
QCM = "demo-qcm-sortie"


@pytest.fixture
def demo(terminale):
    version = importer_paquet(exemple.paquet_exemple())
    version.publier()
    return Rattachement.objects.create(groupe=terminale, parcours=version.parcours)


@pytest.fixture
def prof(terminale, creer_eleve):
    return connecter(APIClient(), creer_eleve(terminale, role="prof"))


@pytest.fixture
def eleve_u(terminale, creer_eleve):
    return creer_eleve(terminale)


@pytest.fixture
def eleve(eleve_u):
    return connecter(APIClient(), eleve_u)


def donner(prof, groupe, **champs):
    corps = {"type": "libre", "titre": "Évaluation du jour", "consigne": "Calcule \\(A^2\\)."} | champs
    r = prof.post(f"/api/groupes/{groupe.id}/devoirs/", corps, format="json")
    assert r.status_code == 201, r.content
    return r.json()


def rater_le_qcm(client, groupe):
    """Passe le QCM d'exemple en répondant faux partout (ou rien) : tout part au carnet."""
    t = client.post(f"/api/groupes/{groupe.id}/parcours/demo-evaluations/evaluations/{QCM}/tentatives/", format="json").json()
    for q in t["questions"]:
        bonnes = Question.objects.get(evaluation__cle=QCM, cle=q["cle"]).bonnes
        faux = next(i for i in range(len(q["choix"])) if i not in bonnes)
        client.put(f"/api/tentatives/{t['id']}/reponses/{q['cle']}/", {"choix": [faux], "temps_ms": 500}, format="json")
    r = client.post(f"/api/tentatives/{t['id']}/terminer/", {"temps": {}}, format="json")
    assert r.status_code == 200, r.content
    return t


# --- Devoirs chronométrés et sujet joint ------------------------------------------------------


def test_le_sujet_d_un_devoir_chronometre_reste_cache_jusqu_au_debut(prof, eleve, terminale):
    d = donner(prof, terminale, duree_min=15)
    prof.post(f"/api/devoirs/{d['id']}/sujet/", {"fichier": SimpleUploadedFile("td.pdf", PDF)}, format="multipart")
    vue = eleve.get(f"/api/devoirs/{d['id']}/").json()
    assert vue["sujet_masque"] and vue["consigne"] == "" and vue["pieces"] == []
    piece = prof.get(f"/api/devoirs/{d['id']}/").json()["pieces"][0]
    assert eleve.get(piece["url"]).status_code == 404, "le fichier du sujet est caché lui aussi"
    # Rendre avant de commencer : refusé
    assert eleve.post(f"/api/devoirs/{d['id']}/rendu/", {"texte": "x", "envoyer": True}, format="json").status_code == 400

    vue = eleve.post(f"/api/devoirs/{d['id']}/commencer/").json()
    assert not vue["sujet_masque"] and "A^2" in vue["consigne"] and vue["fin_prevue"]
    assert eleve.get(piece["url"]).status_code == 200
    # Recommencer ne relance pas le chronomètre
    assert eleve.post(f"/api/devoirs/{d['id']}/commencer/").json()["commence_le"] == vue["commence_le"]


def test_le_sujet_joint_refuse_ce_qui_n_est_ni_photo_ni_pdf(prof, terminale):
    d = donner(prof, terminale)
    r = prof.post(f"/api/devoirs/{d['id']}/sujet/", {"fichier": SimpleUploadedFile("x.pdf", b"<html>")}, format="multipart")
    assert r.status_code == 400


def test_un_eleve_ne_joint_pas_de_sujet_et_un_autre_ne_le_lit_pas(prof, eleve, terminale, prepa, creer_eleve):
    d = donner(prof, terminale)
    assert eleve.post(f"/api/devoirs/{d['id']}/sujet/", {"fichier": SimpleUploadedFile("t.pdf", PDF)}, format="multipart").status_code == 404
    prof.post(f"/api/devoirs/{d['id']}/sujet/", {"fichier": SimpleUploadedFile("t.pdf", PDF)}, format="multipart")
    url = prof.get(f"/api/devoirs/{d['id']}/").json()["pieces"][0]["url"]
    assert eleve.get(url).status_code == 200
    assert connecter(APIClient(), creer_eleve(prepa)).get(url).status_code == 404


def test_rendu_hors_temps_signale(prof, eleve, eleve_u, terminale):
    d = donner(prof, terminale, duree_min=10)
    eleve.post(f"/api/devoirs/{d['id']}/commencer/")
    from devoirs.models import Rendu

    Rendu.objects.filter(eleve=eleve_u).update(commence_le=timezone.now() - timedelta(minutes=30))
    vue = eleve.post(f"/api/devoirs/{d['id']}/rendu/", {"texte": "fini", "envoyer": True}, format="json").json()
    assert vue["hors_temps"] is True


def test_banque_de_commentaires_du_prof(prof, terminale, creer_eleve):
    eleves = [creer_eleve(terminale) for _ in range(2)]
    d = donner(prof, terminale)
    for e in eleves:
        prof.post(f"/api/devoirs/{d['id']}/eleves/{e.id}/", {"commentaire": "Attention aux signes.", "rendre": True}, format="json")
    assert prof.get("/api/mes-commentaires/").json()[0] == "Attention aux signes."


# --- Carnet d'erreurs ---------------------------------------------------------------------------


def test_les_questions_ratees_entrent_au_carnet_sans_la_correction(demo, eleve, terminale):
    rater_le_qcm(eleve, terminale)
    carnet = eleve.get("/api/carnet/").json()
    assert carnet["a_revoir"] == len(carnet["entrees"]) > 0
    texte = str(carnet)
    assert "bonnes" not in texte and "explication" not in texte
    # Pas de doublon à la relecture
    assert len(eleve.get("/api/carnet/").json()["entrees"]) == len(carnet["entrees"])


def test_reviser_une_question_du_carnet(demo, eleve, terminale):
    rater_le_qcm(eleve, terminale)
    entree = eleve.get("/api/carnet/").json()["entrees"][0]
    e = EntreeCarnet.objects.get(pk=entree["id"])
    r = eleve.post(f"/api/carnet/{entree['id']}/repondre/", {"choix": e.question.bonnes}, format="json").json()
    assert r["juste"] and r["entree"]["due"] is False and "explication" in r
    # Trois bonnes réponses de suite : maîtrisée
    for _ in range(2):
        EntreeCarnet.objects.filter(pk=e.pk).update(a_revoir_le=timezone.now())
        r = eleve.post(f"/api/carnet/{entree['id']}/repondre/", {"choix": e.question.bonnes}, format="json").json()
    assert r["entree"]["maitrisee_le"] is not None
    # Une erreur fait revenir la question le lendemain
    autre = EntreeCarnet.objects.exclude(pk=e.pk).filter(utilisateur=e.utilisateur).first()
    if autre:
        faux = [i for i in range(len(autre.question.choix)) if i not in autre.question.bonnes][:1]
        r = eleve.post(f"/api/carnet/{autre.id}/repondre/", {"choix": faux}, format="json").json()
        assert r["juste"] is False and r["entree"]["reussites_de_suite"] == 0


def test_le_carnet_d_un_autre_eleve_est_inaccessible(demo, eleve, terminale, creer_eleve):
    rater_le_qcm(eleve, terminale)
    entree = eleve.get("/api/carnet/").json()["entrees"][0]
    autre = connecter(APIClient(), creer_eleve(terminale))
    assert autre.get("/api/carnet/").json()["entrees"] == []
    assert autre.post(f"/api/carnet/{entree['id']}/repondre/", {"choix": [0]}, format="json").status_code == 404


# --- Séance du jour -------------------------------------------------------------------------------


def test_seance_du_jour(demo, prof, eleve, terminale):
    donner(prof, terminale)
    rater_le_qcm(eleve, terminale)
    s = eleve.get(f"/api/groupes/{terminale.id}/seance/").json()
    assert [d["titre"] for d in s["devoirs"]] == ["Évaluation du jour"] and s["devoirs"][0]["pour_aujourd_hui"]
    assert s["etapes"] and s["etapes"][0]["parcours"] == "demo-evaluations"
    assert s["revisions"] > 0


def test_la_seance_d_une_classe_ou_on_n_est_pas_eleve_est_introuvable(prof, eleve, terminale, prepa):
    assert eleve.get(f"/api/groupes/{prepa.id}/seance/").status_code == 404
    assert prof.get(f"/api/groupes/{terminale.id}/seance/").status_code == 404


# --- Suivi du prof et bilan parent -----------------------------------------------------------------


def test_tableau_de_classe_et_fiche_eleve(demo, prof, eleve, eleve_u, terminale):
    d = donner(prof, terminale, note_sur=10)
    eleve.post(f"/api/devoirs/{d['id']}/rendu/", {"texte": "ok", "envoyer": True}, format="json")
    prof.post(f"/api/devoirs/{d['id']}/eleves/{eleve_u.id}/", {"note": "7", "rendre": True}, format="json")
    ligne = next(x for x in prof.get(f"/api/groupes/{terminale.id}/suivi/").json() if x["eleve"] == str(eleve_u.id))
    assert ligne["termines"] == 1 and ligne["moyenne"] == 14.0
    fiche = prof.get(f"/api/groupes/{terminale.id}/eleves/{eleve_u.id}/").json()
    assert fiche["liste_devoirs"][0]["sur_20"] == 14.0 and fiche["progression"]


def test_le_suivi_est_reserve_aux_profs_de_la_classe(prof, eleve, eleve_u, terminale, prepa, creer_eleve):
    assert eleve.get(f"/api/groupes/{terminale.id}/suivi/").status_code == 404
    assert eleve.get(f"/api/groupes/{terminale.id}/eleves/{eleve_u.id}/").status_code == 404
    autre_prof = connecter(APIClient(), creer_eleve(prepa, role="prof"))
    assert autre_prof.get(f"/api/groupes/{terminale.id}/eleves/{eleve_u.id}/bilan/").status_code == 404
    # Un élève d'une autre classe ne peut pas être consulté depuis cette classe
    etranger = creer_eleve(prepa)
    assert prof.get(f"/api/groupes/{terminale.id}/eleves/{etranger.id}/").status_code == 404


def test_bilan_parent(prof, eleve, eleve_u, terminale):
    d = donner(prof, terminale)
    eleve.post(f"/api/devoirs/{d['id']}/rendu/", {"texte": "ok", "envoyer": True}, format="json")
    prof.post(f"/api/devoirs/{d['id']}/eleves/{eleve_u.id}/", {"note": "15", "rendre": True}, format="json")
    b = prof.get(f"/api/groupes/{terminale.id}/eleves/{eleve_u.id}/bilan/?jours=7").json()
    assert eleve_u.prenom in b["texte"] and "15/20" in b["texte"] and b["travaux_faits"] == 1


# --- Mot de passe oublié -------------------------------------------------------------------------------


def test_l_admin_reinitialise_le_mot_de_passe_d_un_eleve(admin, eleve_u, eleve):
    client = connecter(APIClient(), admin)
    r = client.post(f"/api/admin/comptes/{eleve_u.id}/reinitialiser-mot-de-passe/").json()
    mdp = r["mot_de_passe_provisoire"]
    eleve_u.refresh_from_db()
    assert eleve_u.check_password(mdp) and eleve_u.doit_changer_mot_de_passe
    assert eleve.get("/api/moi/").status_code in (401, 403), "ses appareils sont déconnectés"


def test_seul_l_admin_reinitialise_un_mot_de_passe(prof, eleve, eleve_u, admin):
    assert prof.post(f"/api/admin/comptes/{eleve_u.id}/reinitialiser-mot-de-passe/").status_code == 403
    assert eleve.post(f"/api/admin/comptes/{eleve_u.id}/reinitialiser-mot-de-passe/").status_code == 403
    client = connecter(APIClient(), admin)
    assert client.post(f"/api/admin/comptes/{admin.id}/reinitialiser-mot-de-passe/").status_code == 400
