import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from convertir_parcours import convertir  # noqa: E402
from contenus.paquet import construire_paquet, lire_paquet  # noqa: E402

PAGE = """
<style>body{}</style>
<section class="lesson" id="accueil" data-part="" data-title="Comment utiliser ce parcours" hidden>
<header class="lhead"><p class="eyebrow">Bienvenue</p></header><div class="lbody"><p>Bonjour</p></div></section>
<section class="lesson" id="carte" data-part="Partie 1 · La forme alg&#xe9;brique" data-title="La carte d&#x27;un exercice" hidden>
<header class="lhead"><p class="eyebrow">Partie 1 · Étape 1<span class="meta">6 min</span></p></header>
<div class="lbody"><p>\\(i^2=-1\\)</p><div class="graph" data-fig="plan"></div></div></section>
<section class="lesson" id="eval-p1" data-part="Partie 1 · La forme alg&#xe9;brique" data-title="Évaluation" hidden>
<header class="lhead"><p class="eyebrow">x<span class="meta">45 min</span></p></header>
<div class="lbody"><div class="eval"><button type="button" class="btn ev-go">Commencer</button>
<label><input type="checkbox" data-p="1"><span>1 pt</span></label></ex></div></div></section>
<script>alert(1)</script>
"""


def test_conversion_d_un_parcours_cahier():
    manifeste, fichiers = convertir(PAGE, "nombres-complexes", "Nombres complexes", "Mathématiques", "lycee",
                                    publiques=["carte"])
    parties = manifeste["parties"]
    assert [(p["cle"], p["titre"]) for p in parties] == [("introduction", "Bienvenue"), ("partie-1", "La forme algébrique")]
    etapes = {e["cle"]: e for p in parties for e in p["etapes"]}
    assert etapes["carte"]["titre"] == "La carte d'un exercice"
    assert (etapes["carte"]["acces"], etapes["carte"]["duree_min"]) == ("public", 6)
    assert etapes["eval-p1"]["acces"] == "premium"
    evaluation = fichiers["etapes/eval-p1.html"]
    assert "<button" not in evaluation and 'data-composant="bouton"' in evaluation
    assert "<input" not in evaluation and 'data-composant="case"' in evaluation and 'data-p="1"' in evaluation
    # Le paquet produit passe la validation de sécurité de la plateforme.
    lu = lire_paquet(construire_paquet(manifeste, fichiers))
    assert sum(len(p.etapes) for p in lu.parties) == 3
