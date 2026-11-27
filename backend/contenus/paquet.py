"""Lecture et validation d'un paquet de parcours.

Un paquet est une archive ZIP produite par le moteur de parcours :

    manifeste.json
    etapes/<cle>.html          un fragment HTML par étape (sans <html>, <head>, <body>)
    evaluations/<cle>.json     format 2 : une évaluation en données (questions, bonnes réponses…)

Le contenu est du HTML statique. Les composants interactifs (graphes, scènes 3D, vidéos,
évaluations) sont décrits par des attributs data-* que l'application transforme en
composants. Un paquet ne contient donc jamais de script : un paquet compromis ne doit pas
pouvoir exécuter de code chez les élèves. Voir FORMAT_PAQUET.md.

Format 2 : les évaluations ne sont plus du HTML mais des données. Le fragment ne contient
qu'un emplacement <div data-composant="evaluation" data-cle="…">, et les bonnes réponses
restent sur le serveur jusqu'à la fin de la tentative de l'élève.
"""
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser

FORMAT_ACTUEL = 2
FORMATS_ACCEPTES = (1, 2)
CLE = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")
ACCES = {"public", "inscrit", "premium"}
CYCLES = {"lycee", "prepa", "universite"}

TAILLE_MAX_ARCHIVE = 25 * 1024 * 1024
TAILLE_MAX_DECOMPRESSEE = 40 * 1024 * 1024
TAILLE_MAX_ETAPE = 2 * 1024 * 1024
NOMBRE_MAX_FICHIERS = 1000

# Format 2 : évaluations
TAILLE_MAX_EVALUATION = 512 * 1024
ROLES_EVALUATION = {"entree", "sortie", "evaluation"}
TYPES_QUESTION = {"choix_unique", "choix_multiple"}
QUESTIONS_MAX = 200
CHOIX_MIN, CHOIX_MAX = 2, 12
POINTS_MAX = 100
TEXTE_HTML_MAX = 20_000
CHAMPS_EVALUATION = {"titre", "role", "consigne", "duree_min", "seuil", "questions"}
CHAMPS_QUESTION = {"cle", "type", "enonce", "choix", "bonnes", "points", "explication"}

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
class QuestionLue:
    cle: str
    type: str
    enonce: str
    choix: list
    bonnes: list          # indices (à partir de 0) des bonnes réponses, triés
    points: float
    explication: str


@dataclass
class EvaluationLue:
    cle: str
    titre: str
    role: str
    consigne: str
    duree_min: int | None
    seuil: float | None   # points à atteindre pour réussir ; None : pas de seuil
    questions: list = field(default_factory=list)

    @property
    def total(self):
        return sum(q.points for q in self.questions)


@dataclass
class EtapeLue:
    cle: str
    titre: str
    acces: str
    duree_min: int | None
    html: str
    evaluations: list = field(default_factory=list)


@dataclass
class PartieLue:
    cle: str
    titre: str
    etapes: list = field(default_factory=list)


@dataclass
class PaquetLu:
    empreinte: str
    format: int
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
        self.evaluations = []   # data-cle des emplacements <… data-composant="evaluation">

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
        attrs = {(n or "").lower(): (v or "") for n, v in attributs}
        if attrs.get("data-composant") == "evaluation":
            self.evaluations.append(attrs.get("data-cle", ""))

    handle_startendtag = handle_starttag


def _inspecter(html, fichier):
    inspecteur = _Inspecteur(fichier)
    inspecteur.feed(html)
    inspecteur.close()
    return inspecteur


def inspecter_html(html, fichier="fragment"):
    return _inspecter(html, fichier).problemes


def emplacements_evaluation(html):
    """Les data-cle des emplacements d'évaluation d'un fragment, dans l'ordre."""
    return _inspecter(html, "fragment").evaluations


def _html(valeur, nom, problemes, obligatoire=True):
    """Un morceau de HTML d'une évaluation (énoncé, choix, explication) : même contrôle qu'un fragment."""
    if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
        if obligatoire:
            problemes.append(f"{nom} manquant")
        return ""
    if not isinstance(valeur, str):
        problemes.append(f"{nom} doit être un texte (HTML)")
        return ""
    if len(valeur) > TEXTE_HTML_MAX:
        problemes.append(f"{nom} trop long ({len(valeur)} caractères, {TEXTE_HTML_MAX} au plus)")
    problemes.extend(inspecter_html(valeur, nom))
    return valeur.strip()


def _nombre(valeur):
    return isinstance(valeur, (int, float)) and not isinstance(valeur, bool)


def _quart(valeur):
    """Les points vont par quarts (0,25), comme les barèmes des évaluations."""
    return abs(valeur * 4 - round(valeur * 4)) < 1e-9


def _lire_question(qb, ou, problemes):
    if not isinstance(qb, dict):
        problemes.append(f"{ou} : doit être un objet")
        return None
    for inconnu in sorted(set(qb) - CHAMPS_QUESTION):
        problemes.append(f"{ou} : champ « {inconnu} » inconnu")
    cle = _texte(qb.get("cle"), f"{ou} : cle", problemes, 60)
    if cle and not CLE.match(cle):
        problemes.append(f"{ou} : cle « {cle} » invalide")
    ou = f"{ou} ({cle})" if cle else ou
    type_ = qb.get("type", "choix_unique")
    if type_ not in TYPES_QUESTION:
        problemes.append(f"{ou} : type « {type_} » invalide ({', '.join(sorted(TYPES_QUESTION))})")
    enonce = _html(qb.get("enonce"), f"{ou} : enonce", problemes)

    choix_bruts = qb.get("choix")
    choix = []
    if not isinstance(choix_bruts, list) or not CHOIX_MIN <= len(choix_bruts) <= CHOIX_MAX:
        problemes.append(f"{ou} : choix doit être une liste de {CHOIX_MIN} à {CHOIX_MAX} textes")
    else:
        choix = [_html(c, f"{ou} : choix {k + 1}", problemes) for k, c in enumerate(choix_bruts)]

    bonnes = qb.get("bonnes")
    if not isinstance(bonnes, list) or not bonnes or not all(isinstance(b, int) and not isinstance(b, bool) for b in bonnes):
        problemes.append(f"{ou} : bonnes doit être une liste non vide d'indices (à partir de 0)")
        bonnes = []
    else:
        if len(set(bonnes)) != len(bonnes):
            problemes.append(f"{ou} : bonnes contient un indice en double")
        if choix and any(not 0 <= b < len(choix) for b in bonnes):
            problemes.append(f"{ou} : bonnes désigne un choix qui n'existe pas ({len(choix)} choix, indices 0 à {len(choix) - 1})")
        if type_ == "choix_unique" and len(bonnes) != 1:
            problemes.append(f"{ou} : une question à choix unique a exactement une bonne réponse")
        if choix and type_ == "choix_multiple" and len(set(bonnes)) == len(choix):
            problemes.append(f"{ou} : tous les choix sont bons, la question ne mesure rien")
        bonnes = sorted(set(bonnes))

    points = qb.get("points", 1)
    if not _nombre(points) or not 0 < points <= POINTS_MAX or not _quart(points):
        problemes.append(f"{ou} : points doit être un nombre de 0,25 à {POINTS_MAX}, par quarts de point")
        points = 1
    explication = _html(qb.get("explication"), f"{ou} : explication", problemes, obligatoire=False)
    return QuestionLue(cle, type_, enonce, choix, bonnes, float(points), explication)


def _lire_evaluation(cle, brut, fichier, problemes):
    """Valide le contenu JSON d'une évaluation. Ajoute les problèmes trouvés à `problemes`."""
    if not isinstance(brut, dict):
        problemes.append(f"{fichier} : doit être un objet JSON")
        return None
    for inconnu in sorted(set(brut) - CHAMPS_EVALUATION):
        problemes.append(f"{fichier} : champ « {inconnu} » inconnu")
    titre = _texte(brut.get("titre"), f"{fichier} : titre", problemes)
    role = brut.get("role", "evaluation")
    if role not in ROLES_EVALUATION:
        problemes.append(f"{fichier} : role « {role} » invalide ({', '.join(sorted(ROLES_EVALUATION))})")
    consigne = _html(brut.get("consigne"), f"{fichier} : consigne", problemes, obligatoire=False)
    duree = brut.get("duree_min")
    if duree is not None and (not isinstance(duree, int) or isinstance(duree, bool) or not 0 < duree <= 600):
        problemes.append(f"{fichier} : duree_min doit être un entier entre 1 et 600")
        duree = None

    questions_brutes = brut.get("questions")
    if not isinstance(questions_brutes, list) or not questions_brutes:
        problemes.append(f"{fichier} : questions doit être une liste non vide")
        questions_brutes = []
    elif len(questions_brutes) > QUESTIONS_MAX:
        problemes.append(f"{fichier} : trop de questions ({len(questions_brutes)}, {QUESTIONS_MAX} au plus)")
    questions, cles = [], set()
    for k, qb in enumerate(questions_brutes, 1):
        q = _lire_question(qb, f"{fichier}, question {k}", problemes)
        if q is None:
            continue
        if q.cle and q.cle in cles:
            problemes.append(f"{fichier}, question {k} : cle « {q.cle} » en double dans l'évaluation")
        cles.add(q.cle)
        questions.append(q)

    evaluation = EvaluationLue(cle, titre, role, consigne, duree, None, questions)
    seuil = brut.get("seuil")
    if seuil is not None:
        if not _nombre(seuil) or not 0 < seuil <= evaluation.total or not _quart(seuil):
            problemes.append(f"{fichier} : seuil doit être un nombre de points entre 0,25 et le total ({evaluation.total:g})")
        else:
            evaluation.seuil = float(seuil)
    return evaluation


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


def _lire_evaluations_etape(eb, etape, ou, format_, archive, noms, cles_evaluations, problemes):
    """Format 2 : lit les évaluations déclarées par une étape et les relie à ses emplacements."""
    declarees = eb.get("evaluations")
    emplacements = emplacements_evaluation(etape.html) if etape.html else []
    if format_ < 2:
        if declarees is not None:
            problemes.append(f"{ou} : evaluations n'existe qu'à partir du format 2")
        return
    if declarees is None:
        declarees = []
    if not isinstance(declarees, list):
        problemes.append(f"{ou} : evaluations doit être une liste")
        declarees = []
    for k, db in enumerate(declarees, 1):
        ou_ev = f"{ou}, évaluation {k}"
        if not isinstance(db, dict):
            problemes.append(f"{ou_ev} : doit être un objet {{cle, fichier}}")
            continue
        cle = _texte(db.get("cle"), f"{ou_ev} : cle", problemes, 60)
        if cle and not CLE.match(cle):
            problemes.append(f"{ou_ev} : cle « {cle} » invalide")
        if cle in cles_evaluations:
            problemes.append(f"{ou_ev} : cle « {cle} » en double dans le parcours")
        cles_evaluations.add(cle)
        fichier = db.get("fichier") or ""
        if not isinstance(fichier, str) or not fichier.startswith("evaluations/") or not fichier.endswith(".json") \
                or ".." in fichier or "\\" in fichier:
            problemes.append(f"{ou_ev} : fichier « {fichier} » invalide (attendu evaluations/<nom>.json)")
            continue
        if fichier not in noms:
            problemes.append(f"{ou_ev} : fichier « {fichier} » absent de l'archive")
            continue
        if noms[fichier].file_size > TAILLE_MAX_EVALUATION:
            problemes.append(f"{ou_ev} : fichier « {fichier} » trop lourd (512 Ko au plus)")
            continue
        try:
            brut = json.loads(archive.read(fichier).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            problemes.append(f"{fichier} : JSON illisible : {e}")
            continue
        evaluation = _lire_evaluation(cle, brut, fichier, problemes)
        if evaluation is not None:
            etape.evaluations.append(evaluation)
        if cle and emplacements.count(cle) != 1:
            problemes.append(f"{ou_ev} : le fragment doit contenir exactement un emplacement "
                             f'<div data-composant="evaluation" data-cle="{cle}"> '
                             f"(trouvé : {emplacements.count(cle)})")
    connues = {e.cle for e in etape.evaluations} | {d.get("cle") for d in declarees if isinstance(d, dict)}
    for cle in emplacements:
        if cle not in connues:
            problemes.append(f"{ou} : emplacement d'évaluation « {cle} » sans évaluation déclarée dans l'étape")


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
    format_ = manifeste.get("format")
    if format_ not in FORMATS_ACCEPTES or isinstance(format_, bool):
        problemes.append(f"format {format_!r} non pris en charge (attendu : "
                         f"{' ou '.join(str(f) for f in FORMATS_ACCEPTES)})")
        format_ = FORMAT_ACTUEL

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

    parties, cles_parties, cles_etapes, cles_evaluations = [], set(), set(), set()
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
            etape = EtapeLue(cle_e, titre_e, acces, duree, html)
            _lire_evaluations_etape(eb, etape, ou, format_, archive, noms, cles_evaluations, problemes)
            partie.etapes.append(etape)
        parties.append(partie)

    if problemes:
        raise PaquetInvalide(problemes)
    return PaquetLu(
        empreinte=hashlib.sha256(donnees).hexdigest(),
        format=format_,
        manifeste=manifeste,
        slug=slug, titre=titre, matiere=matiere, cycle=cycle, description=description,
        parties=parties,
    )


# Entrées ZIP reproductibles : même contenu → mêmes octets, donc même empreinte (comme le moteur).
DATE_FIXE = (1980, 1, 1, 0, 0, 0)   # la plus petite date que le format ZIP sait écrire
SYSTEME_UNIX = 3
DROITS = 0o100644 << 16             # fichier ordinaire, rw-r--r--


def construire_paquet(manifeste: dict, fichiers: dict, compresser: bool = False) -> bytes:
    """Fabrique un paquet en mémoire (utilisé par les outils et les tests).

    L'archive est reproductible : chaque entrée a la même date, le même système et les mêmes
    droits, manifeste.json vient en premier et les autres fichiers suivent triés. Deux appels
    avec le même contenu donnent donc exactement les mêmes octets. Par défaut les entrées sont
    stockées sans compression, comme le fait le moteur ; `compresser=True` sert aux tests qui
    ont besoin d'une archive compressée (bombe de décompression).
    """
    contenus = {"manifeste.json": json.dumps(manifeste, ensure_ascii=False, indent=1), **fichiers}
    noms = sorted(contenus, key=lambda nom: (nom != "manifeste.json", nom))
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        for nom in noms:
            info = zipfile.ZipInfo(nom, date_time=DATE_FIXE)
            info.compress_type = zipfile.ZIP_DEFLATED if compresser else zipfile.ZIP_STORED
            info.create_system = SYSTEME_UNIX
            info.external_attr = DROITS
            z.writestr(info, contenus[nom])
    return tampon.getvalue()
