#!/usr/bin/env python3
"""Convertit un parcours HTML « cahier » existant en paquet pour la plateforme.

    python3 outils/convertir_parcours.py nombres-complexes.html \\
        --slug nombres-complexes --titre "Nombres complexes" \\
        --matiere Mathématiques --cycle lycee -o nombres-complexes.zip

Chaque <section class="lesson"> devient une étape : son id donne la clé, data-title le titre,
data-part la partie, « N min » la durée. Le corps (div.lbody) devient le fragment HTML.

Le CSS et les scripts de la page ne sont pas repris : l'application les fournit. Les boutons et
cases à cocher des évaluations sont gardés sous forme d'éléments neutres (data-composant), que
l'application transformera en composants.

C'est un outil de transition : le moteur de parcours unifié produira les paquets directement.
"""
import argparse
import html
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

SECTION = re.compile(r'<section class="lesson"(?P<attrs>[^>]*)>(?P<corps>.*?)</section>', re.S)
ATTR = re.compile(r'([\w-]+)="([^"]*)"')
CORPS = re.compile(r'<div class="lbody">(?P<html>.*)</div>\s*$', re.S)
DUREE = re.compile(r'<span class="meta">\s*(\d+)\s*min')


def cle_de(texte):
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60] or "partie"


def neutraliser(fragment):
    """Remplace ce qui est interdit dans un paquet par des éléments neutres."""
    fragment = re.sub(
        r"<button\b([^>]*)>(.*?)</button>",
        lambda m: f'<span role="button" data-composant="bouton"{m.group(1).replace(" type=\"button\"", "")}>{m.group(2)}</span>',
        fragment, flags=re.S,
    )
    fragment = re.sub(r'<input\b([^>]*?)type="checkbox"([^>]*)>', r'<span data-composant="case"\1\2></span>', fragment)
    fragment = re.sub(r"<script\b.*?</script>", "", fragment, flags=re.S)
    fragment = re.sub(r"<style\b.*?</style>", "", fragment, flags=re.S)
    fragment = re.sub(r"\s(on[a-z]+)=\"[^\"]*\"", "", fragment)
    fragment = re.sub(r"</ex>", "", fragment)  # balises orphelines des pages d'origine
    return fragment.strip() + "\n"


def convertir(source, slug, titre, matiere, cycle, description="", publiques=(), premium_prefixe="eval-"):
    sections = list(SECTION.finditer(source))
    if not sections:
        raise ValueError("Aucune <section class=\"lesson\"> trouvée.")
    parties, fichiers, index_parties = [], {}, {}
    for s in sections:
        attrs = {k: html.unescape(v) for k, v in ATTR.findall(s.group("attrs"))}
        cle = attrs.get("id", "")
        titre_etape = attrs.get("data-title", cle)
        libelle_partie = attrs.get("data-part", "").strip()
        m = CORPS.search(s.group("corps"))
        if not cle or not m:
            continue
        if libelle_partie:
            numero, _, nom = libelle_partie.partition(" · ")
            cle_partie, titre_partie = cle_de(numero), (nom or numero)
        else:
            cle_partie, titre_partie = "introduction", "Bienvenue"
        if cle_partie not in index_parties:
            index_parties[cle_partie] = {"cle": cle_partie, "titre": titre_partie, "etapes": []}
            parties.append(index_parties[cle_partie])
        duree = DUREE.search(s.group("corps"))
        if cle in publiques or cle_partie == "introduction":
            acces = "public"
        elif premium_prefixe and cle.startswith(premium_prefixe):
            acces = "premium"
        else:
            acces = "inscrit"
        etape = {"cle": cle, "titre": titre_etape, "fichier": f"etapes/{cle}.html", "acces": acces}
        if duree:
            etape["duree_min"] = int(duree.group(1))
        index_parties[cle_partie]["etapes"].append(etape)
        fichiers[etape["fichier"]] = neutraliser(m.group("html"))
    manifeste = {
        "format": 1,
        "parcours": {"slug": slug, "titre": titre, "matiere": matiere, "cycle": cycle, "description": description},
        "parties": parties,
    }
    return manifeste, fichiers


def ecrire_zip(manifeste, fichiers, sortie):
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifeste.json", json.dumps(manifeste, ensure_ascii=False, indent=1))
        for nom, contenu in sorted(fichiers.items()):
            z.writestr(nom, contenu)


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("source")
    a.add_argument("--slug", required=True)
    a.add_argument("--titre", required=True)
    a.add_argument("--matiere", required=True)
    a.add_argument("--cycle", required=True, choices=["lycee", "prepa", "universite"])
    a.add_argument("--description", default="")
    a.add_argument("--public", action="append", default=[], help="clé d'une étape à mettre en vitrine")
    a.add_argument("--premium-prefixe", default="eval-")
    a.add_argument("-o", "--sortie", required=True)
    args = a.parse_args()
    manifeste, fichiers = convertir(
        Path(args.source).read_text(encoding="utf-8"), args.slug, args.titre, args.matiere, args.cycle,
        args.description, args.public, args.premium_prefixe,
    )
    ecrire_zip(manifeste, fichiers, args.sortie)
    n = sum(len(p["etapes"]) for p in manifeste["parties"])
    print(f"{args.sortie} : {len(manifeste['parties'])} parties, {n} étapes", file=sys.stderr)


if __name__ == "__main__":
    main()
