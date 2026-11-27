from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

from contenus import exemple
from contenus.importation import importer_paquet
from contenus.models import VersionParcours
from contenus.paquet import PaquetInvalide, construire_paquet
from evaluations.models import Evaluation, Question

pytestmark = pytest.mark.django_db

INITIAUX = Path(__file__).resolve().parents[2] / "contenus_initiaux"


def test_import_format_2_enregistre_les_evaluations():
    version = importer_paquet(exemple.paquet_exemple())
    qcm, chrono = Evaluation.objects.filter(version=version).order_by("etape__ordre")
    assert (qcm.cle, qcm.etape.cle, qcm.role, qcm.seuil, qcm.total, qcm.duree_min) == (
        "demo-qcm-sortie", "module-conjugue", "sortie", Decimal(2), Decimal(3), None)
    assert (chrono.duree_min, chrono.total, chrono.seuil) == (5, Decimal(4), Decimal(3))
    assert list(qcm.questions.values_list("cle", "type", "bonnes")) == [
        ("module", "choix_unique", [0]), ("conjugue", "choix_unique", [1]), ("reels", "choix_multiple", [0, 2])]
    assert chrono.questions.get(cle="proprietes").points == Decimal(2)


def test_le_manifeste_garde_en_base_ne_contient_aucune_reponse():
    version = importer_paquet(exemple.paquet_exemple())
    assert "bonnes" not in str(version.manifeste)


@pytest.mark.parametrize("nom", ["nombres-complexes.zip", "etude-de-fonction.zip"])
def test_les_paquets_au_format_1_s_importent_toujours(nom):
    version = importer_paquet((INITIAUX / nom).read_bytes())
    assert version.manifeste["format"] == 1
    assert version.etapes.count() > 0 and version.evaluations.count() == 0


def test_paquet_refuse_n_ecrit_rien():
    fichiers = exemple.fichiers()
    fichiers["evaluations/demo-evaluation-chrono.json"] = '{"titre": "x", "questions": []}'
    with pytest.raises(PaquetInvalide):
        importer_paquet(construire_paquet(exemple.manifeste(), fichiers))
    assert not VersionParcours.objects.exists() and not Question.objects.exists()


def test_commandes_paquet_exemple_et_importer_paquet(tmp_path):
    chemin = tmp_path / "exemple.zip"
    call_command("paquet_exemple", str(chemin), stdout=StringIO())
    assert chemin.read_bytes() == exemple.paquet_exemple()
    sortie = StringIO()
    call_command("importer_paquet", str(chemin), "--publier", stdout=sortie)
    assert "demo-evaluations v1 (Publiée) : 2 étapes, 2 évaluations" in sortie.getvalue()
