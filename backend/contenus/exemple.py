"""Un petit parcours au format 2, pour les tests et pour essayer la plateforme en local.

    python manage.py paquet_exemple exemple-format2.zip

Deux étapes sur les nombres complexes : un QCM de sortie (correction à la fin, seuil) et une
évaluation chronométrée de 5 minutes avec une question à choix multiple notée sur 2 points.
"""
import json

from .paquet import construire_paquet

QCM_SORTIE = {
    "titre": "Test de sortie — module et conjugué",
    "role": "sortie",
    "consigne": "<p>Réponds aux trois questions, puis termine pour voir la correction.</p>",
    "seuil": 2,
    "questions": [
        {
            "cle": "module",
            "type": "choix_unique",
            "enonce": r"<p>Le module de \(z = 3 + 4i\) vaut :</p>",
            "choix": [r"\(5\)", r"\(7\)", r"\(25\)", r"\(\sqrt{7}\)"],
            "bonnes": [0],
            "explication": r"<p>\(|z| = \sqrt{3^2 + 4^2} = \sqrt{25} = 5\).</p>",
        },
        {
            "cle": "conjugue",
            "type": "choix_unique",
            "enonce": r"<p>Le conjugué de \(z = 2 - 5i\) est :</p>",
            "choix": [r"\(-2 + 5i\)", r"\(2 + 5i\)", r"\(-2 - 5i\)", r"\(5 - 2i\)"],
            "bonnes": [1],
            "explication": "<p>On garde la partie réelle et on change le signe de la partie imaginaire.</p>",
        },
        {
            "cle": "reels",
            "type": "choix_multiple",
            "enonce": "<p>Parmi ces nombres, lesquels sont <b>réels</b> ? (plusieurs réponses)</p>",
            "choix": [r"\(i^2\)", r"\(i^3\)", r"\((1 + i)(1 - i)\)", r"\(1 + i\)"],
            "bonnes": [0, 2],
            "explication": r"<p>\(i^2 = -1\) et \((1 + i)(1 - i) = 1 - i^2 = 2\) ; \(i^3 = -i\) et \(1 + i\) ne sont pas réels.</p>",
        },
    ],
}

EVALUATION_CHRONO = {
    "titre": "Évaluation chronométrée — calculs dans ℂ",
    "role": "evaluation",
    "consigne": "<p>5 minutes. Tu peux revenir sur une question tant que tu n'as pas terminé.</p>",
    "duree_min": 5,
    "seuil": 3,
    "questions": [
        {
            "cle": "puissance",
            "enonce": r"<p>\(i^{4}\) vaut :</p>",
            "choix": [r"\(1\)", r"\(-1\)", r"\(i\)", r"\(-i\)"],
            "bonnes": [0],
            "explication": r"<p>\(i^4 = (i^2)^2 = (-1)^2 = 1\).</p>",
        },
        {
            "cle": "argument",
            "enonce": r"<p>Un argument de \(z = 1 + i\) est :</p>",
            "choix": [r"\(\frac{\pi}{4}\)", r"\(\frac{\pi}{2}\)", r"\(\pi\)", r"\(-\frac{\pi}{4}\)"],
            "bonnes": [0],
            "explication": r"<p>\(z = \sqrt{2}\left(\cos\frac{\pi}{4} + i \sin\frac{\pi}{4}\right)\).</p>",
        },
        {
            "cle": "proprietes",
            "type": "choix_multiple",
            "points": 2,
            "enonce": r"<p>Pour <b>tout</b> nombre complexe \(z\), lesquelles sont vraies ?</p>",
            "choix": [
                r"\(z\,\overline{z} = |z|^2\)",
                r"\(|z|^2 = z^2\)",
                r"\(z + \overline{z}\) est réel",
                r"\(z - \overline{z}\) est réel",
            ],
            "bonnes": [0, 2],
            "explication": r"<p>\(z + \overline{z} = 2\,\mathrm{Re}(z)\) est réel, mais \(z - \overline{z} = 2i\,\mathrm{Im}(z)\) "
                           r"est imaginaire pur ; \(z^2\) n'est pas réel en général (\(i^2 = -1 \ne 1 = |i|^2\)).</p>",
        },
    ],
}


def manifeste():
    return {
        "format": 2,
        "parcours": {
            "slug": "demo-evaluations",
            "titre": "Démonstration des évaluations",
            "matiere": "Mathématiques",
            "cycle": "lycee",
            "description": "Parcours d'essai du format 2 : un QCM de sortie et une évaluation chronométrée.",
        },
        "parties": [
            {
                "cle": "complexes",
                "titre": "Nombres complexes",
                "etapes": [
                    {
                        "cle": "module-conjugue", "titre": "Module et conjugué", "fichier": "etapes/module-conjugue.html",
                        "acces": "inscrit", "duree_min": 10,
                        "evaluations": [{"cle": "demo-qcm-sortie", "fichier": "evaluations/demo-qcm-sortie.json"}],
                    },
                    {
                        "cle": "evaluation-c", "titre": "Évaluation chronométrée", "fichier": "etapes/evaluation-c.html",
                        "duree_min": 5,
                        "evaluations": [{"cle": "demo-evaluation-chrono", "fichier": "evaluations/demo-evaluation-chrono.json"}],
                    },
                ],
            }
        ],
    }


def fichiers():
    return {
        "etapes/module-conjugue.html": (
            "<h2>Module et conjugué</h2>"
            r"<p>Pour \(z = a + ib\), le module est \(|z| = \sqrt{a^2 + b^2}\) et le conjugué \(\overline{z} = a - ib\).</p>"
            '<div data-composant="evaluation" data-cle="demo-qcm-sortie"></div>'
        ),
        "etapes/evaluation-c.html": (
            "<h2>Évaluation chronométrée</h2>"
            "<p>Lance l'évaluation quand tu es prêt : le temps commence au premier clic.</p>"
            '<div data-composant="evaluation" data-cle="demo-evaluation-chrono"></div>'
        ),
        "evaluations/demo-qcm-sortie.json": json.dumps(QCM_SORTIE, ensure_ascii=False, indent=1),
        "evaluations/demo-evaluation-chrono.json": json.dumps(EVALUATION_CHRONO, ensure_ascii=False, indent=1),
    }


def paquet_exemple() -> bytes:
    return construire_paquet(manifeste(), fichiers())
