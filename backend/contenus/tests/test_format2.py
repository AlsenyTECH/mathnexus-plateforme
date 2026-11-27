"""Format 2 : les évaluations en données (FORMAT_PAQUET.md).

Ces tests ne touchent pas la base : ils ne vérifient que la lecture du paquet.
"""
import copy
import json

import pytest

from contenus import exemple
from contenus.paquet import FORMAT_ACTUEL, PaquetInvalide, construire_paquet, emplacements_evaluation, lire_paquet

QCM = "evaluations/demo-qcm-sortie.json"
CHRONO = "evaluations/demo-evaluation-chrono.json"


def lire(manifeste=None, fichiers=None):
    return lire_paquet(construire_paquet(manifeste or exemple.manifeste(), fichiers or exemple.fichiers()))


def problemes(manifeste=None, fichiers=None):
    with pytest.raises(PaquetInvalide) as e:
        lire(manifeste, fichiers)
    return " | ".join(e.value.problemes)


def avec_qcm(modifier):
    """Les fichiers de l'exemple, avec le QCM de sortie modifié par `modifier(qcm)`."""
    qcm = copy.deepcopy(exemple.QCM_SORTIE)
    modifier(qcm)
    return {**exemple.fichiers(), QCM: json.dumps(qcm)}


# --- Ce qui est accepté ----------------------------------------------------------------

def test_format_actuel_est_2():
    assert FORMAT_ACTUEL == 2


def test_paquet_exemple_lu():
    lu = lire()
    assert lu.format == 2
    etape1, etape2 = lu.parties[0].etapes
    qcm = etape1.evaluations[0]
    assert (qcm.cle, qcm.role, qcm.seuil, qcm.duree_min, qcm.total) == ("demo-qcm-sortie", "sortie", 2, None, 3)
    assert [q.cle for q in qcm.questions] == ["module", "conjugue", "reels"]
    assert qcm.questions[0].type == "choix_unique" and qcm.questions[0].bonnes == [0]
    assert qcm.questions[2].type == "choix_multiple" and qcm.questions[2].bonnes == [0, 2]
    chrono = etape2.evaluations[0]
    assert (chrono.duree_min, chrono.total, chrono.seuil) == (5, 4, 3)
    assert chrono.questions[0].type == "choix_unique"  # type par défaut


def test_paquet_exemple_reproductible():
    assert exemple.paquet_exemple() == exemple.paquet_exemple()


def test_format_2_sans_evaluation_accepte():
    m = exemple.manifeste()
    for e in m["parties"][0]["etapes"]:
        del e["evaluations"]
    fichiers = {
        "etapes/module-conjugue.html": "<p>Cours</p>",
        "etapes/evaluation-c.html": "<p>Cours</p>",
    }
    assert lire(m, fichiers).parties[0].etapes[0].evaluations == []


def test_bonnes_triees_et_points_par_quarts():
    def modifier(qcm):
        qcm["questions"][2]["bonnes"] = [2, 0]
        qcm["questions"][2]["points"] = 1.25
    lu = lire(fichiers=avec_qcm(modifier))
    q = lu.parties[0].etapes[0].evaluations[0].questions[2]
    assert q.bonnes == [0, 2] and q.points == 1.25


def test_emplacements_releves():
    html = '<p>x</p><div data-composant="evaluation" data-cle="a"></div><span data-composant="evaluation" data-cle="b">'
    assert emplacements_evaluation(html) == ["a", "b"]


# --- Format 1 toujours accepté, mais sans évaluations ------------------------------------

def test_format_1_refuse_les_evaluations():
    m = exemple.manifeste()
    m["format"] = 1
    assert "evaluations n'existe qu'à partir du format 2" in problemes(m)


# --- Ce qui est refusé -------------------------------------------------------------------

@pytest.mark.parametrize("modifier,attendu", [
    (lambda q: q["questions"][0].update(bonnes=[4]), "désigne un choix qui n'existe pas"),
    (lambda q: q["questions"][0].update(bonnes=[0, 1]), "exactement une bonne réponse"),
    (lambda q: q["questions"][0].update(bonnes=[]), "liste non vide d'indices"),
    (lambda q: q["questions"][0].update(bonnes=["0"]), "liste non vide d'indices"),
    (lambda q: q["questions"][2].update(bonnes=[0, 0]), "indice en double"),
    (lambda q: q["questions"][2].update(bonnes=[0, 1, 2, 3]), "tous les choix sont bons"),
    (lambda q: q["questions"][0].update(choix=["\\(5\\)"]), "liste de 2 à 12"),
    (lambda q: q["questions"][0].update(choix=["a"] * 13), "liste de 2 à 12"),
    (lambda q: q["questions"][0].update(points=0.3), "par quarts de point"),
    (lambda q: q["questions"][0].update(points=0), "par quarts de point"),
    (lambda q: q["questions"][0].update(type="libre"), "type « libre » invalide"),
    (lambda q: q["questions"][1].update(cle="module"), "en double dans l'évaluation"),
    (lambda q: q["questions"][1].update(cle="Mauvaise Clé"), "invalide"),
    (lambda q: q["questions"][0].pop("enonce"), "enonce manquant"),
    (lambda q: q["questions"][0].update(bonne=0), "champ « bonne » inconnu"),
    (lambda q: q.update(seuil=4), "seuil doit être un nombre de points"),
    (lambda q: q.update(role="final"), "role « final » invalide"),
    (lambda q: q.update(duree_min=0), "duree_min doit être un entier"),
    (lambda q: q.update(questions=[]), "questions doit être une liste non vide"),
    (lambda q: q.update(corrige="…"), "champ « corrige » inconnu"),
    (lambda q: q.pop("titre"), "titre manquant"),
])
def test_evaluation_mal_formee_refusee(modifier, attendu):
    assert attendu in problemes(fichiers=avec_qcm(modifier))


@pytest.mark.parametrize("champ,valeur", [
    ("enonce", '<p>Question</p><img src="x" onerror="alert(1)">'),
    ("explication", "<script>alert(1)</script>"),
    ("choix", ["<a href=\"javascript:alert(1)\">a</a>", "b"]),
])
def test_html_dangereux_dans_une_evaluation_refuse(champ, valeur):
    texte = problemes(fichiers=avec_qcm(lambda q: q["questions"][0].update({champ: valeur})))
    assert "demo-qcm-sortie.json" in texte
    assert "interdit" in texte or "interdite" in texte


def test_tous_les_problemes_sont_listes():
    def modifier(qcm):
        qcm["questions"][0]["bonnes"] = [9]
        qcm["questions"][1]["points"] = -1
        qcm["seuil"] = 100
    texte = problemes(fichiers=avec_qcm(modifier))
    assert "n'existe pas" in texte and "quarts" in texte and "seuil" in texte


def test_json_illisible_refuse():
    assert "JSON illisible" in problemes(fichiers={**exemple.fichiers(), QCM: "{pas du json"})


def test_fichier_d_evaluation_absent_ou_mal_place():
    fichiers = {k: v for k, v in exemple.fichiers().items() if k != QCM}
    assert "absent de l'archive" in problemes(fichiers=fichiers)
    m = exemple.manifeste()
    m["parties"][0]["etapes"][0]["evaluations"][0]["fichier"] = "etapes/../qcm.json"
    assert "attendu evaluations/<nom>.json" in problemes(m)


def test_emplacement_manquant_refuse():
    fichiers = {**exemple.fichiers(), "etapes/module-conjugue.html": "<p>Sans emplacement</p>"}
    assert "exactement un emplacement" in problemes(fichiers=fichiers)


def test_emplacement_en_double_refuse():
    div = '<div data-composant="evaluation" data-cle="demo-qcm-sortie"></div>'
    fichiers = {**exemple.fichiers(), "etapes/module-conjugue.html": "<p>x</p>" + div + div}
    assert "(trouvé : 2)" in problemes(fichiers=fichiers)


def test_emplacement_sans_evaluation_refuse():
    fichiers = exemple.fichiers()
    fichiers["etapes/module-conjugue.html"] += '<div data-composant="evaluation" data-cle="inconnue"></div>'
    assert "« inconnue » sans évaluation déclarée" in problemes(fichiers=fichiers)


def test_emplacement_dans_une_autre_etape_refuse():
    """L'emplacement doit être dans l'étape qui déclare l'évaluation."""
    fichiers = exemple.fichiers()
    fichiers["etapes/module-conjugue.html"], fichiers["etapes/evaluation-c.html"] = (
        fichiers["etapes/evaluation-c.html"], fichiers["etapes/module-conjugue.html"])
    texte = problemes(fichiers=fichiers)
    assert "exactement un emplacement" in texte and "sans évaluation déclarée" in texte


def test_cle_d_evaluation_en_double_dans_le_parcours():
    m = exemple.manifeste()
    m["parties"][0]["etapes"][1]["evaluations"][0]["cle"] = "demo-qcm-sortie"
    assert "« demo-qcm-sortie » en double dans le parcours" in problemes(m)


def test_evaluation_trop_lourde_refusee():
    fichiers = {**exemple.fichiers(), QCM: json.dumps({**exemple.QCM_SORTIE, "consigne": "a" * 600_000})}
    assert "trop lourd (512 Ko au plus)" in problemes(fichiers=fichiers)
