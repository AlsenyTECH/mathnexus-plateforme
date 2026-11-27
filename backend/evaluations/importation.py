"""Enregistre les évaluations lues dans un paquet (format 2), à l'import d'une version."""
from decimal import Decimal

from .models import Evaluation, Question


def _decimal(nombre):
    return Decimal(str(nombre)) if nombre is not None else None


def enregistrer_evaluations(etape, evaluations_lues):
    """Crée les évaluations d'une étape importée. Appelé dans la transaction de l'import."""
    for el in evaluations_lues:
        evaluation = Evaluation.objects.create(
            version=etape.version, etape=etape, cle=el.cle, titre=el.titre, role=el.role,
            consigne=el.consigne, duree_min=el.duree_min, seuil=_decimal(el.seuil), total=_decimal(el.total),
        )
        Question.objects.bulk_create([
            Question(
                evaluation=evaluation, cle=q.cle, ordre=i, type=q.type, enonce=q.enonce, choix=q.choix,
                bonnes=q.bonnes, points=_decimal(q.points), explication=q.explication,
            )
            for i, q in enumerate(el.questions, 1)
        ])
