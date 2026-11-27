"""Devoirs : donner du travail, rendre, corriger — et surtout les droits."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from conftest import connecter
from contenus import exemple
from contenus.importation import importer_paquet
from contenus.models import Rattachement

pytestmark = pytest.mark.django_db

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200


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
    corps = {"type": "libre", "titre": "Exercices 1 à 3 p. 42", "consigne": "Sur ta copie."} | champs
    r = prof.post(f"/api/groupes/{groupe.id}/devoirs/", corps, format="json")
    assert r.status_code == 201, r.content
    return r.json()


def test_le_prof_donne_un_travail_et_l_eleve_le_voit(prof, eleve, terminale):
    d = donner(prof, terminale)
    assert d["date_limite"], "une date limite par défaut (ce soir)"
    mes = eleve.get("/api/mes-devoirs/").json()
    assert [x["id"] for x in mes] == [d["id"]] and mes[0]["statut"] == "a_faire"


def test_un_eleve_ne_peut_pas_donner_de_devoir(eleve, terminale):
    r = eleve.post(f"/api/groupes/{terminale.id}/devoirs/", {"type": "libre", "titre": "x"}, format="json")
    assert r.status_code == 404


def test_un_eleve_d_une_autre_classe_ne_voit_rien(prof, terminale, prepa, creer_eleve):
    d = donner(prof, terminale)
    autre = connecter(APIClient(), creer_eleve(prepa))
    assert autre.get("/api/mes-devoirs/").json() == []
    assert autre.get(f"/api/devoirs/{d['id']}/").status_code == 404


def test_un_devoir_personnel_n_est_vu_que_par_son_eleve(prof, terminale, eleve_u, creer_eleve):
    d = donner(prof, terminale, eleve=str(eleve_u.id))
    autre = connecter(APIClient(), creer_eleve(terminale))
    assert autre.get(f"/api/devoirs/{d['id']}/").status_code == 404
    assert connecter(APIClient(), eleve_u).get(f"/api/devoirs/{d['id']}/").status_code == 200


def test_rendre_corriger_et_lire_la_correction(prof, eleve, eleve_u, terminale):
    d = donner(prof, terminale)
    r = eleve.post(f"/api/devoirs/{d['id']}/rendu/", {"texte": "Ma réponse", "envoyer": True}, format="json")
    assert r.status_code == 200 and r.json()["statut"] == "rendu"
    a_corriger = prof.get("/api/a-corriger/").json()
    assert [(x["devoir"], x["eleve"]) for x in a_corriger] == [(d["id"], str(eleve_u.id))]

    url = f"/api/devoirs/{d['id']}/eleves/{eleve_u.id}/"
    prof.post(url, {"note": "14.5", "commentaire": "Bien", "correction": "Il fallait…"}, format="json")
    vue = eleve.get(f"/api/devoirs/{d['id']}/").json()
    assert vue["rendu"]["commentaire"] == "" and vue["statut"] == "rendu", "rien n'est visible avant que le prof rende la copie"

    r = prof.post(url, {"rendre": True}, format="json")
    assert r.json()["statut"] == "corrige"
    vue = eleve.get(f"/api/devoirs/{d['id']}/").json()
    assert vue["statut"] == "corrige" and vue["note"] == 14.5 and vue["rendu"]["correction"] == "Il fallait…"
    assert prof.get("/api/a-corriger/").json() == []
    r = eleve.post(f"/api/devoirs/{d['id']}/rendu/", {"texte": "changée"}, format="json")
    assert r.status_code == 400, "une copie corrigée ne se modifie plus"


def test_on_n_envoie_pas_une_copie_vide(prof, eleve, terminale):
    d = donner(prof, terminale)
    r = eleve.post(f"/api/devoirs/{d['id']}/rendu/", {"texte": "  ", "envoyer": True}, format="json")
    assert r.status_code == 400


def test_la_note_ne_depasse_pas_le_bareme(prof, eleve_u, terminale):
    d = donner(prof, terminale, note_sur="20")
    r = prof.post(f"/api/devoirs/{d['id']}/eleves/{eleve_u.id}/", {"note": "21"}, format="json")
    assert r.status_code == 400


def test_photos_verifiees_et_reservees(prof, eleve, eleve_u, terminale, creer_eleve):
    d = donner(prof, terminale)
    faux = SimpleUploadedFile("copie.jpg", b"<script>alert(1)</script>", content_type="image/jpeg")
    assert eleve.post(f"/api/devoirs/{d['id']}/rendu/photos/", {"photo": faux}).status_code == 400
    vraie = SimpleUploadedFile("copie.jpg", JPEG, content_type="image/jpeg")
    r = eleve.post(f"/api/devoirs/{d['id']}/rendu/photos/", {"photo": vraie})
    assert r.status_code == 201
    url = r.json()["rendu"]["photos"][0]["url"]
    assert eleve.get(url).status_code == 200
    assert prof.get(url)["Content-Type"] == "image/jpeg"
    camarade = connecter(APIClient(), creer_eleve(terminale))
    assert camarade.get(url).status_code == 404
    assert camarade.delete(url).status_code == 404
    assert prof.delete(url).status_code == 403, "le prof ne retire pas la photo d'un élève"


def test_la_photo_de_correction_reste_cachee_avant_la_correction(prof, eleve, eleve_u, terminale):
    d = donner(prof, terminale)
    photo = SimpleUploadedFile("c.jpg", JPEG, content_type="image/jpeg")
    r = prof.post(f"/api/devoirs/{d['id']}/eleves/{eleve_u.id}/photos/", {"photo": photo})
    url = r.json()["rendu"]["photos_correction"][0]["url"]
    assert eleve.get(url).status_code == 404
    prof.post(f"/api/devoirs/{d['id']}/eleves/{eleve_u.id}/", {"rendre": True}, format="json")
    assert eleve.get(url).status_code == 200


def test_une_evaluation_donnee_en_devoir_se_corrige_seule(prof, eleve, terminale, demo):
    evals = prof.get(f"/api/groupes/{terminale.id}/parcours/demo-evaluations/evaluations/").json()
    assert evals, "le prof voit les évaluations du parcours"
    cle = evals[0]["cle"]
    d = donner(prof, terminale, type="evaluation", parcours="demo-evaluations", cle_evaluation=cle, titre="")
    assert d["cle_etape"] == evals[0]["cle_etape"] and d["titre"] == evals[0]["titre"]
    base = f"/api/groupes/{terminale.id}/parcours/demo-evaluations/evaluations/{cle}/"
    t = eleve.post(base + "tentatives/", format="json").json()
    eleve.post(f"/api/tentatives/{t['id']}/terminer/", {"temps": {}}, format="json")
    vue = eleve.get(f"/api/devoirs/{d['id']}/").json()
    assert vue["statut"] == "fait" and vue["total"] is not None


def test_une_etape_inconnue_est_refusee(prof, terminale, demo):
    r = prof.post(f"/api/groupes/{terminale.id}/devoirs/",
                  {"type": "etape", "parcours": "demo-evaluations", "cle_etape": "n-existe-pas"}, format="json")
    assert r.status_code == 400


def test_l_admin_eleve_de_sa_propre_classe(admin, prepa):
    from organisations.models import Inscription

    Inscription.objects.create(utilisateur=admin, groupe=prepa, role="eleve").valider(par=admin)
    client = connecter(APIClient(), admin)
    moi = client.get("/api/moi/").json()["utilisateur"]
    assert moi["classes_eleve"] == [{"id": str(prepa.id), "nom": prepa.nom}] and moi["enseigne"]
    assert client.get(f"/api/groupes/{prepa.id}/").json()["mon_role"] == "eleve"
