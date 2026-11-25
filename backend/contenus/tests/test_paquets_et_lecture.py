import hashlib

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from comptes.models import JournalAudit
from conftest import connecter
from contenus.importation import PaquetDejaImporte, importer_paquet
from contenus.models import Rattachement, VersionParcours
from contenus.paquet import PaquetInvalide, construire_paquet, inspecter_html, lire_paquet
from progression.models import Progression

pytestmark = pytest.mark.django_db


def manifeste(**etapes_supplementaires):
    return {
        "format": 1,
        "parcours": {"slug": "nombres-complexes", "titre": "Nombres complexes", "matiere": "Mathématiques",
                     "cycle": "lycee", "description": "Terminale S2"},
        "parties": [
            {"cle": "algebrique", "titre": "La forme algébrique", "etapes": [
                {"cle": "carte", "titre": "La carte", "fichier": "etapes/carte.html", "acces": "public", "duree_min": 6},
                {"cle": "calcul", "titre": "Calculer", "fichier": "etapes/calcul.html"},
            ]},
            {"cle": "equations", "titre": "Les équations", "etapes": [
                {"cle": "racines", "titre": "Racines carrées", "fichier": "etapes/racines.html"},
                {"cle": "eval-p2", "titre": "Évaluation", "fichier": "etapes/eval-p2.html", "acces": "premium"},
            ]},
        ],
    }


FICHIERS = {
    "etapes/carte.html": "<p>La carte \\(z = a + ib\\)</p>",
    "etapes/calcul.html": '<p>Calcul</p><div class="graph" data-fig="puissances"></div>',
    "etapes/racines.html": "<p>Racines</p>",
    "etapes/eval-p2.html": "<p>Évaluation</p>",
}


def paquet(m=None, fichiers=None):
    return construire_paquet(m or manifeste(), fichiers or FICHIERS)


@pytest.fixture
def publie(admin):
    version = importer_paquet(paquet(), par=admin)
    version.publier()
    return version


@pytest.fixture
def rattache(publie, terminale):
    return Rattachement.objects.create(groupe=terminale, parcours=publie.parcours)


# --- Validation des paquets ------------------------------------------------------------

@pytest.mark.parametrize("html,attendu", [
    ("<script>alert(1)</script>", "balise <script>"),
    ('<img src="x.png" onerror="alert(1)">', "onerror"),
    ('<a href="  JavaScript:alert(1)">x</a>', "javascript:"),
    ('<a href="java&#x09;script:alert(1)">x</a>', "javascript:"),
    ('<iframe src="https://exemple.com"></iframe>', "<iframe>"),
    ('<object data="data:text/html;base64,PHNjcmlwdD4="></object>', "<object>"),
    ('<a href="data:text/html,<script>alert(1)</script>">x</a>', "data:"),
    ("<style>body{display:none}</style>", "<style>"),
    ('<svg><a xlink:href="javascript:alert(1)">x</a></svg>', "javascript:"),
    ('<div style="background:url(javascript:alert(1))">x</div>', "style dangereux"),
    ('<form action="/api/x"><input name="a"></form>', "<form>"),
])
def test_html_dangereux_detecte(html, attendu):
    problemes = inspecter_html(html, "etapes/x.html")
    assert problemes and any(attendu in p for p in problemes), problemes


def test_html_du_cours_accepte():
    html = (
        '<h3>Le conjugué</h3><div class="retenir"><p>\\(\\bar z = a - ib\\)</p></div>'
        '<figure class="graphfig"><div class="graph" data-fig="plan"></div></figure>'
        '<figure class="video"><video controls preload="none" src="v-quotient.mp4"></video></figure>'
        '<img src="data:image/png;base64,iVBORw0KGgo=" alt=""><details><summary>Voir</summary><p>x</p></details>'
    )
    assert inspecter_html(html) == []


def test_paquet_valide_lu():
    lu = lire_paquet(paquet())
    assert lu.slug == "nombres-complexes"
    assert [e.cle for p in lu.parties for e in p.etapes] == ["carte", "calcul", "racines", "eval-p2"]
    assert lu.empreinte == hashlib.sha256(paquet()).hexdigest()


def test_paquet_refuse_liste_tous_les_problemes():
    m = manifeste()
    m["parcours"]["slug"] = "Nombres Complexes"
    m["parties"][0]["etapes"][1]["cle"] = "carte"  # doublon
    m["parties"][1]["etapes"][0]["fichier"] = "../etc/passwd.html"
    m["parties"][1]["etapes"][1]["acces"] = "vip"
    fichiers = dict(FICHIERS, **{"etapes/carte.html": "<script>x</script>"})
    with pytest.raises(PaquetInvalide) as e:
        lire_paquet(paquet(m, fichiers))
    texte = " | ".join(e.value.problemes)
    for attendu in ["parcours.slug", "en double", "../etc/passwd.html", "acces « vip »", "<script>"]:
        assert attendu in texte, texte


def test_fichier_absent_et_format_inconnu():
    m = manifeste()
    m["format"] = 2
    fichiers = {k: v for k, v in FICHIERS.items() if k != "etapes/racines.html"}
    with pytest.raises(PaquetInvalide) as e:
        lire_paquet(paquet(m, fichiers))
    texte = " | ".join(e.value.problemes)
    assert "format 2" in texte and "absent de l'archive" in texte


def test_remontee_de_dossier_refusee_meme_sous_etapes():
    m = manifeste()
    m["parties"][0]["etapes"][0]["fichier"] = "etapes/../carte.html"
    with pytest.raises(PaquetInvalide) as e:
        lire_paquet(paquet(m, dict(FICHIERS, **{"etapes/../carte.html": "<p>x</p>"})))
    assert any("etapes/../carte.html" in p and "invalide" in p for p in e.value.problemes)


def test_rattachements_lisibles_vide_hors_perimetre(rattache, terminale, prepa, creer_eleve):
    """Défense en profondeur : la fonction refuse d'elle-même un groupe non visible."""
    from contenus.acces import rattachements_lisibles

    eleve_prepa = creer_eleve(prepa)
    assert not rattachements_lisibles(eleve_prepa, terminale).exists()
    assert rattachements_lisibles(creer_eleve(terminale), terminale).count() == 1


def test_pas_une_archive():
    with pytest.raises(PaquetInvalide):
        lire_paquet(b"pas un zip")


def test_bombe_de_decompression_refusee():
    enorme = {"etapes/carte.html": "a" * (41 * 1024 * 1024)}
    with pytest.raises(PaquetInvalide) as e:
        lire_paquet(construire_paquet(manifeste(), {**FICHIERS, **enorme}))
    assert "décompressée" in e.value.problemes[0]


# --- Import, versions, publication -------------------------------------------------------

def test_import_cree_une_version_brouillon_invisible(client_api, admin, terminale, creer_eleve):
    v = importer_paquet(paquet(), par=admin)
    assert (v.numero, v.statut, v.etapes.count()) == (1, "brouillon", 4)
    Rattachement.objects.create(groupe=terminale, parcours=v.parcours)
    connecter(client_api, creer_eleve(terminale))
    assert client_api.get(f"/api/groupes/{terminale.id}/parcours/").data == []  # rien de publié


def test_meme_paquet_refuse_nouveau_paquet_nouvelle_version(admin):
    importer_paquet(paquet(), par=admin)
    with pytest.raises(PaquetDejaImporte):
        importer_paquet(paquet(), par=admin)
    v2 = importer_paquet(paquet(fichiers=dict(FICHIERS, **{"etapes/racines.html": "<p>Corrigé</p>"})), par=admin)
    assert v2.numero == 2


def test_publier_archive_la_version_precedente(client_api, admin):
    v1 = importer_paquet(paquet(), par=admin)
    v1.publier()
    v2 = importer_paquet(paquet(fichiers=dict(FICHIERS, **{"etapes/racines.html": "<p>v2</p>"})), par=admin)
    connecter(client_api, admin)
    assert client_api.post(f"/api/admin/contenus/versions/{v2.id}/publier/").status_code == 200
    v1.refresh_from_db()
    assert v1.statut == "archivee"
    assert VersionParcours.objects.filter(statut="publiee").count() == 1


def test_import_par_l_admin_via_l_api(client_api, admin):
    connecter(client_api, admin)
    fichier = SimpleUploadedFile("paquet.zip", paquet(), content_type="application/zip")
    r = client_api.post("/api/admin/contenus/import/", {"paquet": fichier}, format="multipart")
    assert r.status_code == 201, r.data
    assert r.data["statut"] == "brouillon" and r.data["nombre_etapes"] == 4
    r = client_api.post("/api/admin/contenus/import/", {"paquet": SimpleUploadedFile("p.zip", paquet())}, format="multipart")
    assert r.status_code == 409


def test_import_refuse_renvoie_les_problemes(client_api, admin):
    connecter(client_api, admin)
    mauvais = paquet(fichiers=dict(FICHIERS, **{"etapes/calcul.html": '<img src=x onerror="vol()">'}))
    r = client_api.post("/api/admin/contenus/import/", {"paquet": SimpleUploadedFile("p.zip", mauvais)}, format="multipart")
    assert r.status_code == 400
    assert any("onerror" in p for p in r.data["problemes"])
    assert not VersionParcours.objects.exists()  # rien n'est écrit


def test_import_par_cle_de_deploiement(client_api, settings):
    cle = "cle-secrete-du-moteur-de-parcours"
    settings.CLE_DEPLOIEMENT_SHA256 = hashlib.sha256(cle.encode()).hexdigest()
    url = "/api/admin/contenus/import/"
    sans = client_api.post(url, {"paquet": SimpleUploadedFile("p.zip", paquet())}, format="multipart")
    assert sans.status_code == 403
    fausse = client_api.post(url, {"paquet": SimpleUploadedFile("p.zip", paquet())}, format="multipart",
                             HTTP_AUTHORIZATION="Cle-Deploiement mauvaise-cle")
    assert fausse.status_code == 403
    bonne = client_api.post(url, {"paquet": SimpleUploadedFile("p.zip", paquet())}, format="multipart",
                            HTTP_AUTHORIZATION=f"Cle-Deploiement {cle}")
    assert bonne.status_code == 201
    assert JournalAudit.objects.get(action="paquet_importe").details["source"] == "cle_deploiement"


def test_cle_de_deploiement_inactive_si_non_configuree(client_api, settings):
    settings.CLE_DEPLOIEMENT_SHA256 = ""
    r = client_api.post("/api/admin/contenus/import/", {"paquet": SimpleUploadedFile("p.zip", paquet())},
                        format="multipart", HTTP_AUTHORIZATION="Cle-Deploiement ")
    assert r.status_code == 403


def test_les_eleves_ne_peuvent_ni_importer_ni_publier(client_api, terminale, creer_eleve, admin):
    v = importer_paquet(paquet(), par=admin)
    connecter(client_api, creer_eleve(terminale))
    assert client_api.post("/api/admin/contenus/import/", {"paquet": SimpleUploadedFile("p.zip", paquet())},
                           format="multipart").status_code == 403
    assert client_api.post(f"/api/admin/contenus/versions/{v.id}/publier/").status_code == 403
    assert client_api.get(f"/api/admin/contenus/versions/{v.id}/etapes/carte/").status_code == 403


# --- Lecture par l'élève -------------------------------------------------------------------

def test_l_eleve_voit_le_sommaire_de_sa_classe(client_api, rattache, terminale, creer_eleve):
    connecter(client_api, creer_eleve(terminale))
    liste = client_api.get(f"/api/groupes/{terminale.id}/parcours/").data
    assert [p["slug"] for p in liste] == ["nombres-complexes"]
    assert liste[0]["avancement"] == {"validees": 0, "total": 4}
    s = client_api.get(f"/api/groupes/{terminale.id}/parcours/nombres-complexes/").data
    etats = {e["cle"]: (e["accessible"], e["raison"]) for p in s["parties"] for e in p["etapes"]}
    assert etats == {"carte": (True, None), "calcul": (True, None), "racines": (True, None),
                     "eval-p2": (False, "premium")}


def test_l_eleve_lit_une_etape_et_sa_progression_est_notee(client_api, rattache, terminale, creer_eleve):
    eleve = creer_eleve(terminale)
    connecter(client_api, eleve)
    base = f"/api/groupes/{terminale.id}/parcours/nombres-complexes/etapes"
    r = client_api.get(f"{base}/calcul/")
    assert r.status_code == 200
    assert 'data-fig="puissances"' in r.data["html"]
    assert (r.data["precedente"], r.data["suivante"]) == ("carte", "racines")
    assert Progression.objects.get(utilisateur=eleve, cle_etape="calcul").validee_le is None
    assert client_api.post(f"{base}/calcul/valider/").data["validee"] is True
    s = client_api.get(f"/api/groupes/{terminale.id}/parcours/nombres-complexes/").data
    assert s["avancement"] == {"validees": 1, "total": 4}


def test_etape_premium_refusee_a_l_eleve(client_api, rattache, terminale, creer_eleve):
    connecter(client_api, creer_eleve(terminale))
    r = client_api.get(f"/api/groupes/{terminale.id}/parcours/nombres-complexes/etapes/eval-p2/")
    assert r.status_code == 403 and r.data["raison"] == "premium"
    r = client_api.post(f"/api/groupes/{terminale.id}/parcours/nombres-complexes/etapes/eval-p2/valider/")
    assert r.status_code == 403


def test_parcours_non_rattache_ou_autre_classe_invisible(client_api, publie, terminale, prepa, creer_eleve):
    Rattachement.objects.create(groupe=prepa, parcours=publie.parcours)
    connecter(client_api, creer_eleve(terminale))
    assert client_api.get(f"/api/groupes/{terminale.id}/parcours/nombres-complexes/").status_code == 404
    assert client_api.get(f"/api/groupes/{prepa.id}/parcours/nombres-complexes/").status_code == 404
    assert client_api.get(f"/api/groupes/{prepa.id}/parcours/nombres-complexes/etapes/carte/").status_code == 404


def test_progression_survit_a_une_nouvelle_version(client_api, admin, rattache, terminale, creer_eleve):
    eleve = creer_eleve(terminale)
    connecter(client_api, eleve)
    client_api.post(f"/api/groupes/{terminale.id}/parcours/nombres-complexes/etapes/carte/valider/")
    v2 = importer_paquet(paquet(fichiers=dict(FICHIERS, **{"etapes/carte.html": "<p>Nouvelle carte</p>"})), par=admin)
    v2.publier()
    s = client_api.get(f"/api/groupes/{terminale.id}/parcours/nombres-complexes/").data
    assert s["version"] == 2 and s["avancement"]["validees"] == 1
    r = client_api.get(f"/api/groupes/{terminale.id}/parcours/nombres-complexes/etapes/carte/")
    assert "Nouvelle carte" in r.data["html"] and r.data["validee"] is True


# --- Ouverture progressive par le prof ----------------------------------------------------

def test_ouverture_progressive(client_api, rattache, terminale, creer_eleve):
    from rest_framework.test import APIClient

    rattache.ouverture = "progressive"
    rattache.save()
    eleve, prof = creer_eleve(terminale), creer_eleve(terminale, role="prof")
    client_eleve = connecter(APIClient(), eleve)
    url = f"/api/groupes/{terminale.id}/parcours/nombres-complexes"
    r = client_eleve.get(f"{url}/etapes/calcul/")
    assert r.status_code == 403 and r.data["raison"] == "pas_encore_ouverte"

    connecter(client_api, prof)
    assert client_api.get(f"{url}/etapes/calcul/").status_code == 200  # le prof voit tout
    assert client_eleve.post(f"{url}/ouverture/", {"etapes": ["calcul"]}, format="json").status_code == 404
    r = client_api.post(f"{url}/ouverture/", {"etapes": ["carte", "calcul"]}, format="json")
    assert r.data["ouvertes"] == ["calcul", "carte"]
    assert client_eleve.get(f"{url}/etapes/calcul/").status_code == 200
    assert client_api.post(f"{url}/ouverture/", {"etapes": ["inconnue"]}, format="json").status_code == 400
    client_api.post(f"{url}/ouverture/", {"etapes": ["calcul"], "ouvrir": False}, format="json")
    assert client_eleve.get(f"{url}/etapes/calcul/").status_code == 403


def test_tableau_de_progression_du_prof(client_api, rattache, terminale, prepa, creer_eleve):
    from rest_framework.test import APIClient

    e1, e2 = creer_eleve(terminale), creer_eleve(terminale)
    creer_eleve(prepa)
    url = f"/api/groupes/{terminale.id}/parcours/nombres-complexes"
    connecter(APIClient(), e1).post(f"{url}/etapes/carte/valider/")
    connecter(client_api, creer_eleve(terminale, role="prof"))
    r = client_api.get(f"{url}/progression/")
    assert r.status_code == 200
    par_eleve = {x["utilisateur"]: x["validees"] for x in r.data["eleves"]}
    assert par_eleve == {str(e1.id): ["carte"], str(e2.id): []}
    connecter(client_api, e2)
    assert client_api.get(f"{url}/progression/").status_code == 404  # un élève ne voit pas le tableau


# --- Vitrine publique -----------------------------------------------------------------------

def test_etape_publique_lisible_sans_compte(client_api, publie):
    assert client_api.get("/api/public/parcours/nombres-complexes/etapes/carte/").status_code == 200
    assert client_api.get("/api/public/parcours/nombres-complexes/etapes/calcul/").status_code == 404
    assert client_api.get("/api/public/parcours/nombres-complexes/etapes/eval-p2/").status_code == 404


def test_etape_publique_d_un_brouillon_invisible(client_api, admin):
    importer_paquet(paquet(), par=admin)
    assert client_api.get("/api/public/parcours/nombres-complexes/etapes/carte/").status_code == 404


# --- Rattachement par l'admin ----------------------------------------------------------------

def test_admin_rattache_et_detache(client_api, admin, publie, terminale, creer_eleve):
    connecter(client_api, admin)
    r = client_api.post(f"/api/admin/groupes/{terminale.id}/parcours/",
                        {"parcours": "nombres-complexes", "ouverture": "progressive"}, format="json")
    assert r.status_code == 201 and r.data["ouverture"] == "progressive"
    assert client_api.post(f"/api/admin/groupes/{terminale.id}/parcours/",
                           {"parcours": "nombres-complexes", "ouverture": "nimporte"}, format="json").status_code == 400
    assert client_api.delete(f"/api/admin/groupes/{terminale.id}/parcours/nombres-complexes/").status_code == 204
    assert not Rattachement.objects.exists()
