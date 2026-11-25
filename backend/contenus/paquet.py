"""Lecture et validation d'un paquet de parcours.

Un paquet est une archive ZIP produite par le moteur de parcours :

    manifeste.json
    etapes/<cle>.html      un fragment HTML par étape (sans <html>, <head>, <body>)

Le contenu est du HTML statique. Les composants interactifs (graphes, scènes 3D, vidéos,
évaluations) sont décrits par des attributs data-* que l'application transforme en
composants. Un paquet ne contient donc jamais de script : un paquet compromis ne doit pas
pouvoir exécuter de code chez les élèves. Voir FORMAT_PAQUET.md.
"""
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser

FORMAT_ACTUEL = 1
CLE = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")
ACCES = {"public", "inscrit", "premium"}
CYCLES = {"lycee", "prepa", "universite"}

TAILLE_MAX_ARCHIVE = 25 * 1024 * 1024
TAILLE_MAX_DECOMPRESSEE = 40 * 1024 * 1024
TAILLE_MAX_ETAPE = 2 * 1024 * 1024
NOMBRE_MAX_FICHIERS = 1000

BALISES_INTERDITES = {
    "script", "iframe", "frame", "frameset", "object", "embed", "applet", "form", "input",
    "button", "textarea", "select", "base", "meta", "link", "style", "html", "head", "body",
}
ATTRIBUTS_URL = {"href", "src", "poster", "action", "formaction", "xlink:href", "background", "cite", "data"}


class PaquetInvalide(Exception):
    def __init__(self, problemes):
        self.problemes = list(problemes)
        super().__init__("; ".join(self.problemes))


@dataclass
class EtapeLue:
    cle: str
    titre: str
    acces: str
    duree_min: int | None
    html: str


@dataclass
class PartieLue:
    cle: str
    titre: str
    etapes: list = field(default_factory=list)


@dataclass
class PaquetLu:
    empreinte: str
    manifeste: dict
    slug: str
    titre: str
    matiere: str
    cycle: str
    description: str
    parties: list


class _Inspecteur(HTMLParser):
    """Relève ce qui pourrait exécuter du code dans un fragment HTML."""

    def __init__(self, fichier):
        super().__init__(convert_charrefs=True)
        self.fichier = fichier
        self.problemes = []

    def _noter(self, message):
        ligne, _ = self.getpos()
        self.problemes.append(f"{self.fichier}, ligne {ligne} : {message}")

    def handle_starttag(self, balise, attributs):
        if balise in BALISES_INTERDITES:
            self._noter(f"balise <{balise}> interdite")
        for nom, valeur in attributs:
            nom = (nom or "").lower()
            valeur = (valeur or "").strip()
            if nom.startswith("on"):
                self._noter(f"attribut {nom} interdit (gestionnaire d'événement)")
            elif nom == "srcdoc":
                self._noter("attribut srcdoc interdit")
            elif nom in ATTRIBUTS_URL:
                compact = re.sub(r"[\s\x00-\x1f]", "", valeur).lower()
                if compact.startswith(("javascript:", "vbscript:")):
                    self._noter(f"URL {compact.split(':')[0]}: interdite dans {nom}")
                elif compact.startswith("data:") and not compact.startswith("data:image/"):
                    self._noter(f"URL data: interdite dans {nom} (seules les images sont permises)")
            elif nom == "style" and re.search(r"expression\s*\(|url\s*\(\s*['\"]?\s*javascript:", valeur, re.I):
                self._noter("style dangereux")

    handle_startendtag = handle_starttag


def inspecter_html(html, fichier="fragment"):
    inspecteur = _Inspecteur(fichier)
    inspecteur.feed(html)
    inspecteur.close()
    return inspecteur.problemes


def _texte(valeur, nom, problemes, maximum=200, obligatoire=True):
    if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
        if obligatoire:
            problemes.append(f"{nom} manquant")
        return ""
    if not isinstance(valeur, str):
        problemes.append(f"{nom} doit être un texte")
        return ""
    if len(valeur) > maximum:
        problemes.append(f"{nom} trop long ({len(valeur)} caractères, {maximum} au plus)")
    return valeur.strip()


def lire_paquet(donnees: bytes) -> PaquetLu:
    """Lit et valide un paquet. Lève PaquetInvalide avec la liste de tous les problèmes trouvés."""
    if len(donnees) > TAILLE_MAX_ARCHIVE:
        raise PaquetInvalide([f"archive trop lourde ({len(donnees) // 1024 // 1024} Mo, 25 Mo au plus)"])
    try:
        archive = zipfile.ZipFile(io.BytesIO(donnees))
    except zipfile.BadZipFile:
        raise PaquetInvalide(["ce fichier n'est pas une archive ZIP"])

    infos = archive.infolist()
    if len(infos) > NOMBRE_MAX_FICHIERS:
        raise PaquetInvalide([f"trop de fichiers dans l'archive ({len(infos)})"])
    if sum(i.file_size for i in infos) > TAILLE_MAX_DECOMPRESSEE:
        raise PaquetInvalide(["archive trop volumineuse une fois décompressée"])
    noms = {i.filename: i for i in infos if not i.is_dir()}

    if "manifeste.json" not in noms:
        raise PaquetInvalide(["manifeste.json absent de la racine de l'archive"])
    try:
        manifeste = json.loads(archive.read("manifeste.json").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise PaquetInvalide([f"manifeste.json illisible : {e}"])
    if not isinstance(manifeste, dict):
        raise PaquetInvalide(["manifeste.json doit être un objet JSON"])

    problemes = []
    if manifeste.get("format") != FORMAT_ACTUEL:
        problemes.append(f"format {manifeste.get('format')!r} non pris en charge (attendu : {FORMAT_ACTUEL})")

    p = manifeste.get("parcours") or {}
    if not isinstance(p, dict):
        p, _ = {}, problemes.append("parcours doit être un objet")
    slug = _texte(p.get("slug"), "parcours.slug", problemes, 60)
    if slug and not CLE.match(slug):
        problemes.append(f"parcours.slug « {slug} » invalide (minuscules, chiffres et tirets)")
    titre = _texte(p.get("titre"), "parcours.titre", problemes)
    matiere = _texte(p.get("matiere"), "parcours.matiere", problemes, 80)
    cycle = _texte(p.get("cycle"), "parcours.cycle", problemes, 20)
    if cycle and cycle not in CYCLES:
        problemes.append(f"parcours.cycle « {cycle} » invalide ({', '.join(sorted(CYCLES))})")
    description = _texte(p.get("description"), "parcours.description", problemes, 2000, obligatoire=False)

    parties_brutes = manifeste.get("parties")
    if not isinstance(parties_brutes, list) or not parties_brutes:
        problemes.append("parties doit être une liste non vide")
        parties_brutes = []

    parties, cles_parties, cles_etapes = [], set(), set()
    for i, pb in enumerate(parties_brutes, 1):
        if not isinstance(pb, dict):
            problemes.append(f"partie {i} : doit être un objet")
            continue
        cle_p = _texte(pb.get("cle"), f"partie {i} : cle", problemes, 60)
        if cle_p and not CLE.match(cle_p):
            problemes.append(f"partie {i} : cle « {cle_p} » invalide")
        if cle_p in cles_parties:
            problemes.append(f"partie {i} : cle « {cle_p} » en double")
        cles_parties.add(cle_p)
        partie = PartieLue(cle_p, _texte(pb.get("titre"), f"partie {cle_p or i} : titre", problemes))
        etapes_brutes = pb.get("etapes")
        if not isinstance(etapes_brutes, list) or not etapes_brutes:
            problemes.append(f"partie {cle_p or i} : etapes doit être une liste non vide")
            etapes_brutes = []
        for j, eb in enumerate(etapes_brutes, 1):
            ou = f"partie {cle_p or i}, étape {j}"
            if not isinstance(eb, dict):
                problemes.append(f"{ou} : doit être un objet")
                continue
            cle_e = _texte(eb.get("cle"), f"{ou} : cle", problemes, 60)
            if cle_e and not CLE.match(cle_e):
                problemes.append(f"{ou} : cle « {cle_e} » invalide")
            if cle_e in cles_etapes:
                problemes.append(f"{ou} : cle « {cle_e} » en double dans le parcours")
            cles_etapes.add(cle_e)
            titre_e = _texte(eb.get("titre"), f"{ou} : titre", problemes)
            acces = eb.get("acces", "inscrit")
            if acces not in ACCES:
                problemes.append(f"{ou} : acces « {acces} » invalide ({', '.join(sorted(ACCES))})")
            duree = eb.get("duree_min")
            if duree is not None and (not isinstance(duree, int) or isinstance(duree, bool) or not 0 < duree <= 600):
                problemes.append(f"{ou} : duree_min doit être un entier entre 1 et 600")
                duree = None
            fichier = eb.get("fichier") or ""
            html = ""
            if not isinstance(fichier, str) or not fichier.startswith("etapes/") or not fichier.endswith(".html") \
                    or ".." in fichier or "\\" in fichier:
                problemes.append(f"{ou} : fichier « {fichier} » invalide (attendu etapes/<nom>.html)")
            elif fichier not in noms:
                problemes.append(f"{ou} : fichier « {fichier} » absent de l'archive")
            elif noms[fichier].file_size > TAILLE_MAX_ETAPE:
                problemes.append(f"{ou} : fichier « {fichier} » trop lourd (2 Mo au plus)")
            else:
                try:
                    html = archive.read(fichier).decode("utf-8")
                except UnicodeDecodeError:
                    problemes.append(f"{fichier} : doit être encodé en UTF-8")
                problemes.extend(inspecter_html(html, fichier))
            partie.etapes.append(EtapeLue(cle_e, titre_e, acces, duree, html))
        parties.append(partie)

    if problemes:
        raise PaquetInvalide(problemes)
    return PaquetLu(
        empreinte=hashlib.sha256(donnees).hexdigest(),
        manifeste=manifeste,
        slug=slug, titre=titre, matiere=matiere, cycle=cycle, description=description,
        parties=parties,
    )


def construire_paquet(manifeste: dict, fichiers: dict) -> bytes:
    """Fabrique un paquet en mémoire (utilisé par les outils et les tests)."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifeste.json", json.dumps(manifeste, ensure_ascii=False, indent=1))
        for nom, contenu in sorted(fichiers.items()):
            z.writestr(nom, contenu)
    return tampon.getvalue()
