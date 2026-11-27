"""Les tentatives : parcours complet, temps par question, échéance, et surtout les droits.

Règle centrale : avant la fin d'une tentative, rien de la correction ne quitte le serveur.
"""
import copy
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from conftest import connecter
from contenus import exemple
from contenus.importation import importer_paquet
from contenus.models import Rattachement
from contenus.paquet import construire_paquet
from evaluations.models import Reponse, Tentative
from organisations.models import Inscription

pytestmark = pytest.mark.django_db

QCM = "demo-qcm-sortie"
CHRONO = "demo-evaluation-chrono"


@pytest.fixture
def demo(admin, terminale):
    """Le parcours d'exemple publié et rattaché à la Terminale."""
    version = importer_paquet(exemple.paquet_exemple())
    version.publier()
    return Rattachement.objects.create(groupe=terminale, parcours=version.parcours)


@pytest.fixture
def eleve(client_api, demo, terminale, creer_eleve):
    return connecter(client_api, creer_eleve(terminale))


def url_eval(groupe, cle, suite=""):
    return f"/api/groupes/{groupe.id}/parcours/demo-evaluations/evaluations/{cle}/{suite}"


def commencer(client, groupe, cle=QCM):
    r = client.post(url_eval(groupe, cle, "tentatives/"), format="json")
    assert r.status_code in (200, 201), r.content
    return r.json()


def repondre(client, tentative_id, question, choix, temps_ms=1000):
    return client.put(f"/api/tentatives/{tentative_id}/reponses/{question}/",
                      {"choix": choix, "temps_ms": temps_ms}, format="json")


def terminer(client, tentative_id, temps=None):
    return client.post(f"/api/tentatives/{tentative_id}/terminer/", {"temps": temps or {}}, format="json")


def reculer(tentative_id, secondes, echeance_dans=None):
    """Fait comme si la tentative avait commencé il y a `secondes` secondes."""
    maintenant = timezone.now()
    champs = {"commencee_le": maintenant - timedelta(seconds=secondes)}
    if echeance_dans is not None:
        champs["echeance"] = maintenant + timedelta(seconds=echeance_dans)
    Tentative.objects.filter(pk=tentative_id).update(**champs)


def cles_partout(objet):
    """Toutes les clés de dictionnaire d'une réponse JSON, à toutes les profondeurs."""
    if isinstance(objet, dict):
        return set(objet) | set().union(*(cles_partout(v) for v in objet.values()))
    if isinstance(objet, list):
        return set().union(*(cles_partout(v) for v in objet)) if objet else set()
    return set()


# --- Rien de la correction avant la fin --------------------------------------------------

def test_presentation_sans_questions(eleve, terminale):
    r = eleve.get(url_eval(terminale, QCM))
    assert r.status_code == 200
    d = r.json()
    assert (d["titre"], d["nombre_questions"], d["total"], d["seuil"], d["en_cours"]) == (
        "Test de sortie — module et conjugué", 3, 3.0, 2.0, None)
    assert "questions" not in d


def test_rien_de_la_correction_avant_la_fin(eleve, terminale):
    reponses_recues = [eleve.get(url_eval(terminale, QCM)).json()]
    t = commencer(eleve, terminale)
    reponses_recues.append(t)
    reponses_recues.append(repondre(eleve, t["id"], "module", [0]).json())
    reponses_recues.append(repondre(eleve, t["id"], "reels", [1]).json())
    reponses_recues.append(eleve.get(f"/api/tentatives/{t['id']}/").json())
    reponses_recues.append(commencer(eleve, terminale))  # reprise

    texte = json.dumps(reponses_recues, ensure_ascii=False)
    for d in reponses_recues:
        assert not cles_partout(d) & {"bonnes", "explication", "juste", "correction", "points_obtenus"}
    for q in exemple.QCM_SORTIE["questions"]:
        assert q["explication"] not in texte
    assert all(d.get("score") is None for d in reponses_recues)
    assert t["questions"][0] == {"cle": "module", "type": "choix_unique", "enonce": exemple.QCM_SORTIE["questions"][0]["enonce"],
                                 "choix": exemple.QCM_SORTIE["questions"][0]["choix"], "points": 1.0}


# --- Parcours complet --------------------------------------------------------------------

def test_tentative_complete_corrigee_par_le_serveur(eleve, terminale):
    t = commencer(eleve, terminale)
    reculer(t["id"], 60)  # sans cela, le serveur plafonnerait les temps au temps écoulé (presque 0)
    assert t["terminee"] is False and t["secondes_restantes"] is None  # pas de chronomètre
    assert repondre(eleve, t["id"], "module", [0], 4000).status_code == 200      # juste
    assert repondre(eleve, t["id"], "conjugue", [0], 6000).status_code == 200    # faux
    assert repondre(eleve, t["id"], "reels", [2, 0], 9000).status_code == 200    # juste (ordre indifférent)

    r = terminer(eleve, t["id"])
    assert r.status_code == 200
    d = r.json()
    assert (d["terminee"], d["fin"], d["score"], d["total"], d["reussie"]) == (True, "terminee", 2.0, 3.0, True)
    assert [(c["cle"], c["juste"], c["points_obtenus"], c["bonnes"]) for c in d["correction"]] == [
        ("module", True, 1.0, [0]), ("conjugue", False, 0.0, [1]), ("reels", True, 1.0, [0, 2])]
    assert d["correction"][0]["explication"] == exemple.QCM_SORTIE["questions"][0]["explication"]

    tentative = Tentative.objects.get(pk=t["id"])
    temps = {r.question.cle: r.temps_ms for r in tentative.reponses.select_related("question")}
    assert temps == {"module": 4000, "conjugue": 6000, "reels": 9000}
    assert all(r.premiere_reponse_le and r.derniere_reponse_le for r in tentative.reponses.all())


def test_choix_multiple_tout_ou_rien(eleve, terminale):
    t = commencer(eleve, terminale)
    repondre(eleve, t["id"], "reels", [0])  # une seule des deux bonnes réponses
    d = terminer(eleve, t["id"]).json()
    assert d["correction"][2]["juste"] is False and d["score"] == 0.0 and d["reussie"] is False


def test_question_sans_reponse_comptee_fausse(eleve, terminale):
    t = commencer(eleve, terminale)
    repondre(eleve, t["id"], "module", [0])
    d = terminer(eleve, t["id"]).json()
    assert [c["juste"] for c in d["correction"]] == [True, False, False] and d["score"] == 1.0


def test_reprise_apres_rechargement(eleve, terminale):
    t = commencer(eleve, terminale)
    reculer(t["id"], 60)
    repondre(eleve, t["id"], "conjugue", [1], 2500)
    reprise = commencer(eleve, terminale)
    assert reprise["id"] == t["id"]
    assert eleve.get(url_eval(terminale, QCM)).json()["en_cours"] == t["id"]
    assert eleve.get(f"/api/tentatives/{t['id']}/").json()["reponses"] == {"conjugue": {"choix": [1], "temps_ms": 2500}}


def test_reponse_modifiable_jusqu_a_la_fin_puis_figee(eleve, terminale):
    t = commencer(eleve, terminale)
    repondre(eleve, t["id"], "module", [2])
    repondre(eleve, t["id"], "module", [0])
    assert Reponse.objects.get(tentative_id=t["id"]).modifications == 1
    terminer(eleve, t["id"])
    r = repondre(eleve, t["id"], "module", [1])
    assert r.status_code == 409 and r.json()["raison"] == "terminee"
    deuxieme = terminer(eleve, t["id"]).json()  # terminer deux fois ne change rien
    assert deuxieme["score"] == 1.0


def test_tentatives_illimitees(eleve, terminale):
    premiere = commencer(eleve, terminale)
    terminer(eleve, premiere["id"])
    seconde = eleve.post(url_eval(terminale, QCM, "tentatives/"), format="json")
    assert seconde.status_code == 201 and seconde.json()["id"] != premiere["id"]
    d = eleve.get(url_eval(terminale, QCM)).json()
    assert d["en_cours"] == seconde.json()["id"] and [x["id"] for x in d["tentatives"]] == [premiere["id"]]


# --- Temps par question : mesuré par le navigateur, plafonné par le serveur --------------

def test_temps_plafonne_par_le_temps_ecoule(eleve, terminale):
    t = commencer(eleve, terminale)
    reculer(t["id"], 10)  # commencée il y a 10 s
    premier = repondre(eleve, t["id"], "module", [0], 60_000).json()["temps_ms"]
    assert 10_000 <= premier <= 12_500  # 10 s écoulées + 2 s de tolérance d'horloge
    second = repondre(eleve, t["id"], "conjugue", [1], 60_000).json()["temps_ms"]
    assert premier + second <= 12_500


def test_temps_ne_recule_pas_et_se_complete_a_la_fin(eleve, terminale):
    t = commencer(eleve, terminale)
    reculer(t["id"], 60)
    repondre(eleve, t["id"], "module", [0], 8000)
    assert repondre(eleve, t["id"], "module", [0], 3000).json()["temps_ms"] == 8000
    # Question vue mais laissée sans réponse : le temps est transmis à la fin.
    terminer(eleve, t["id"], temps={"module": 9000, "reels": 5000})
    temps = {r.question.cle: (r.temps_ms, r.choix) for r in Reponse.objects.filter(tentative_id=t["id"])}
    # À la fin, chaque question a sa ligne, même jamais affichée (« conjugue »).
    assert temps == {"module": (9000, [0]), "reels": (5000, None), "conjugue": (0, None)}


def test_temps_seul_sans_reponse(eleve, terminale):
    t = commencer(eleve, terminale)
    reculer(t["id"], 30)
    r = repondre(eleve, t["id"], "conjugue", None, 7000)
    assert r.status_code == 200 and r.json()["choix"] is None and r.json()["temps_ms"] == 7000


# --- Échéance tenue par le serveur -------------------------------------------------------

def test_evaluation_chronometree(eleve, terminale):
    t = commencer(eleve, terminale, CHRONO)
    assert 299 <= t["secondes_restantes"] <= 300
    tentative = Tentative.objects.get(pk=t["id"])
    assert tentative.echeance - tentative.commencee_le == timedelta(minutes=5)


def test_reponse_apres_l_echeance_refusee_et_tentative_close(eleve, terminale):
    t = commencer(eleve, terminale, CHRONO)
    repondre(eleve, t["id"], "puissance", [0])
    reculer(t["id"], 320, echeance_dans=-20)  # échéance dépassée depuis 20 s
    r = repondre(eleve, t["id"], "argument", [0])
    assert r.status_code == 409
    d = eleve.get(f"/api/tentatives/{t['id']}/").json()
    assert (d["terminee"], d["fin"], d["score"]) == (True, "temps_ecoule", 1.0)
    assert "correction" in d


def test_reponse_dans_le_delai_de_grace_acceptee(eleve, terminale):
    t = commencer(eleve, terminale, CHRONO)
    reculer(t["id"], 302, echeance_dans=-2)
    assert repondre(eleve, t["id"], "puissance", [0]).status_code == 200


def test_tentative_echue_close_meme_sans_requete_de_l_eleve(eleve, terminale):
    """Le résumé de l'évaluation clôt une tentative dont le temps est écoulé."""
    t = commencer(eleve, terminale, CHRONO)
    reculer(t["id"], 400, echeance_dans=-100)
    d = eleve.get(url_eval(terminale, CHRONO)).json()
    assert d["en_cours"] is None and d["tentatives"][0]["fin"] == "temps_ecoule"


def test_terminer_apres_l_echeance_compte_temps_ecoule(eleve, terminale):
    t = commencer(eleve, terminale, CHRONO)
    reculer(t["id"], 400, echeance_dans=-100)
    assert terminer(eleve, t["id"]).json()["fin"] == "temps_ecoule"


# --- Entrées validées --------------------------------------------------------------------

@pytest.mark.parametrize("question,corps", [
    ("module", {"choix": [4]}),
    ("module", {"choix": [0, 1]}),          # choix unique
    ("reels", {"choix": [0, 0]}),
    ("module", {"choix": ["0"]}),
    ("module", {"choix": [True]}),
    ("module", {"choix": 0}),
    ("module", {"choix": [0], "temps_ms": -5}),
    ("module", {"choix": [0], "temps_ms": "1000"}),
    ("inconnue", {"choix": [0]}),
])
def test_reponses_invalides_refusees(eleve, terminale, question, corps):
    t = commencer(eleve, terminale)
    r = eleve.put(f"/api/tentatives/{t['id']}/reponses/{question}/", corps, format="json")
    assert r.status_code == 400
    assert not Reponse.objects.filter(tentative_id=t["id"], choix__isnull=False).exists()


# --- Droits --------------------------------------------------------------------------------

def test_non_connecte_refuse(client_api, demo, terminale):
    assert client_api.get(url_eval(terminale, QCM)).status_code == 403
    assert client_api.post(url_eval(terminale, QCM, "tentatives/")).status_code == 403


def test_tentative_d_un_autre_eleve_introuvable(client_api, demo, terminale, creer_eleve):
    from rest_framework.test import APIClient

    awa = connecter(client_api, creer_eleve(terminale))
    t = commencer(awa, terminale)
    moussa = connecter(APIClient(), creer_eleve(terminale))
    assert moussa.get(f"/api/tentatives/{t['id']}/").status_code == 404
    assert repondre(moussa, t["id"], "module", [0]).status_code == 404
    assert terminer(moussa, t["id"]).status_code == 404
    assert not Reponse.objects.filter(tentative_id=t["id"]).exists()


def test_eleve_d_une_autre_classe_ne_voit_pas_l_evaluation(client_api, demo, terminale, prepa, creer_eleve):
    autre = connecter(client_api, creer_eleve(prepa))
    assert autre.get(url_eval(terminale, QCM)).status_code == 404
    assert autre.post(url_eval(terminale, QCM, "tentatives/")).status_code == 404


def test_evaluation_d_une_etape_pas_encore_ouverte(eleve, demo, terminale):
    demo.ouverture = Rattachement.Ouverture.PROGRESSIVE
    demo.save()
    r = eleve.get(url_eval(terminale, QCM))
    assert r.status_code == 403 and r.json()["raison"] == "pas_encore_ouverte"
    assert eleve.post(url_eval(terminale, QCM, "tentatives/")).status_code == 403
    assert not Tentative.objects.exists()


def test_evaluation_d_une_version_brouillon_invisible(eleve, terminale, admin):
    """Une nouvelle version importée (brouillon) n'expose pas ses évaluations aux élèves."""
    qcm = copy.deepcopy(exemple.QCM_SORTIE)
    m = exemple.manifeste()
    m["parties"][0]["etapes"][0]["evaluations"][0]["cle"] = "nouvelle"
    fichiers = exemple.fichiers()
    fichiers["etapes/module-conjugue.html"] = fichiers["etapes/module-conjugue.html"].replace(QCM, "nouvelle")
    fichiers["evaluations/demo-qcm-sortie.json"] = json.dumps(qcm)
    importer_paquet(construire_paquet(m, fichiers))
    assert eleve.get(url_eval(terminale, "nouvelle")).status_code == 404


def test_eleve_retire_de_la_classe_perd_sa_tentative(eleve, terminale):
    t = commencer(eleve, terminale)
    Inscription.objects.filter(groupe=terminale).delete()
    assert eleve.get(f"/api/tentatives/{t['id']}/").status_code == 404
    assert repondre(eleve, t["id"], "module", [0]).status_code == 404


def test_une_tentative_continue_sur_sa_version(eleve, terminale):
    """Une nouvelle version publiée pendant la tentative ne change pas les questions corrigées."""
    t = commencer(eleve, terminale)
    qcm = copy.deepcopy(exemple.QCM_SORTIE)
    qcm["questions"][0]["bonnes"] = [1]  # la v2 change la bonne réponse
    importer_paquet(construire_paquet(exemple.manifeste(), {
        **exemple.fichiers(), "evaluations/demo-qcm-sortie.json": json.dumps(qcm)})).publier()
    repondre(eleve, t["id"], "module", [0])
    assert terminer(eleve, t["id"]).json()["correction"][0]["juste"] is True
    assert commencer(eleve, terminale)["id"] != t["id"]  # la suivante se passe sur la v2


def test_admin_django_montre_le_temps_par_question(client, admin, eleve, terminale):
    t = commencer(eleve, terminale)
    reculer(t["id"], 30)
    repondre(eleve, t["id"], "module", [0], 12_300)
    terminer(eleve, t["id"])
    client.force_login(admin)
    page = client.get(f"/gestion/evaluations/tentative/{t['id']}/change/").content.decode()
    assert "12.3" in page and "Temps (s)" in page
    assert client.get("/gestion/evaluations/tentative/").status_code == 200
    assert Tentative.objects.get(pk=t["id"]).score == Decimal(1)
