"""API des évaluations.

Sécurité :
- l'évaluation se trouve par le même chemin que la lecture d'une étape (groupe visible,
  parcours rattaché, version publiée, étape ouverte et accessible) : contenus.vues._contexte
  et contenus.acces.etat_etape ;
- une tentative n'est visible que de son auteur (404 sinon), tant qu'il est dans le groupe ;
- avant la fin : énoncés, choix, points, durée — jamais `bonnes`, `explication`, `juste` ni score.
"""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from contenus.acces import etat_etape
from contenus.vues import _contexte
from organisations.acces import groupes_visibles

from . import tentatives as regles
from .models import Evaluation, Tentative

MESSAGES_REFUS = {
    "pas_encore_ouverte": "Cette étape n'est pas encore ouverte par ton prof.",
    "premium": "Cette étape fait partie de l'offre Premium.",
}


def _nombre(decimal):
    return None if decimal is None else float(decimal)


def _resume_evaluation(e):
    return {
        "cle": e.cle, "titre": e.titre, "role": e.role, "consigne": e.consigne, "duree_min": e.duree_min,
        "seuil": _nombre(e.seuil), "total": _nombre(e.total), "nombre_questions": e.questions.count(),
    }


def _resume_tentative(t):
    return {
        "id": str(t.id), "commencee_le": t.commencee_le, "terminee_le": t.terminee_le, "fin": t.fin or None,
        "score": _nombre(t.score), "total": _nombre(t.total), "reussie": t.reussie,
    }


def etat_tentative(t, maintenant=None):
    """Ce que reçoit le navigateur. La correction n'y figure que si la tentative est terminée."""
    questions = list(t.evaluation.questions.all())
    reponses = {r.question_id: r for r in t.reponses.all()}
    etat = {
        **_resume_tentative(t),
        "evaluation": _resume_evaluation(t.evaluation),
        "echeance": t.echeance,
        "secondes_restantes": regles.secondes_restantes(t, maintenant),
        "terminee": t.terminee,
        "questions": [
            {"cle": q.cle, "type": q.type, "enonce": q.enonce, "choix": q.choix, "points": _nombre(q.points)}
            for q in questions
        ],
        "reponses": {
            q.cle: {"choix": reponses[q.id].choix, "temps_ms": reponses[q.id].temps_ms}
            for q in questions if q.id in reponses
        },
    }
    if t.terminee:
        etat["correction"] = [
            {
                "cle": q.cle, "bonnes": q.bonnes, "explication": q.explication,
                "juste": reponses[q.id].juste if q.id in reponses else False,
                "points_obtenus": _nombre(reponses[q.id].points) if q.id in reponses else 0.0,
            }
            for q in questions
        ]
    return etat


def _evaluation_accessible(request, pk, slug, cle):
    """L'évaluation publiée, si l'étape qui la contient est lisible par ce compte ; 404 ou 403 sinon."""
    groupe, rattachement, version = _contexte(request, pk, slug)
    evaluation = get_object_or_404(
        Evaluation.objects.select_related("etape", "version__parcours"), version=version, cle=cle
    )
    _, accessible, raison = etat_etape(request.user, groupe, rattachement, evaluation.etape)
    if not accessible:
        raise PermissionDenied({"detail": MESSAGES_REFUS[raison], "raison": raison})
    return groupe, evaluation


def _ma_tentative(request, tentative_id):
    """Sa propre tentative, dans un groupe qu'il voit encore ; 404 pour toute autre."""
    tentative = get_object_or_404(
        Tentative.objects.select_related("evaluation"), pk=tentative_id, utilisateur=request.user
    )
    if not groupes_visibles(request.user).filter(pk=tentative.groupe_id).exists():
        raise Tentative.DoesNotExist  # transformé en 404 par la vue
    return regles.clore_si_echue(tentative)


class DetailEvaluation(APIView):
    """Présentation de l'évaluation (sans les questions) et les tentatives de l'élève."""

    def get(self, request, pk, slug, cle):
        groupe, evaluation = _evaluation_accessible(request, pk, slug, cle)
        les_miennes = Tentative.objects.filter(
            utilisateur=request.user, groupe=groupe, parcours=evaluation.version.parcours, cle_evaluation=cle
        ).select_related("evaluation")
        for t in les_miennes.filter(terminee_le__isnull=True):
            regles.clore_si_echue(t)  # une tentative dont le temps est écoulé se termine ici
        les_miennes = list(les_miennes)
        en_cours = next((t for t in les_miennes if not t.terminee), None)
        return Response({
            **_resume_evaluation(evaluation),
            "en_cours": str(en_cours.id) if en_cours else None,
            "tentatives": [_resume_tentative(t) for t in les_miennes if t.terminee],
        })


class CommencerTentative(APIView):
    def post(self, request, pk, slug, cle):
        groupe, evaluation = _evaluation_accessible(request, pk, slug, cle)
        tentative, creee = regles.commencer(request.user, groupe, evaluation)
        return Response(etat_tentative(tentative), status=status.HTTP_201_CREATED if creee else status.HTTP_200_OK)


class _VueTentative(APIView):
    def handle_exception(self, exc):
        if isinstance(exc, Tentative.DoesNotExist):
            return Response({"detail": "Tentative introuvable."}, status=status.HTTP_404_NOT_FOUND)
        if isinstance(exc, regles.TentativeClose):
            return Response({"detail": "Cette tentative est terminée.", "raison": "terminee"},
                            status=status.HTTP_409_CONFLICT)
        if isinstance(exc, regles.ReponseInvalide):
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().handle_exception(exc)


class DetailTentative(_VueTentative):
    """Reprendre une tentative (après un rechargement), ou relire sa correction."""

    def get(self, request, tentative_id):
        return Response(etat_tentative(_ma_tentative(request, tentative_id)))


class Repondre(_VueTentative):
    """PUT {"choix": [indices], "temps_ms": n} — enregistré à chaque choix, modifiable jusqu'à la fin."""

    def put(self, request, tentative_id, cle):
        tentative = _ma_tentative(request, tentative_id)
        maintenant = timezone.now()
        reponse = regles.repondre(
            tentative, cle, request.data.get("choix"), request.data.get("temps_ms"), maintenant=maintenant
        )
        return Response({
            "question": cle, "choix": reponse.choix, "temps_ms": reponse.temps_ms,
            "secondes_restantes": regles.secondes_restantes(tentative, maintenant),
        })


class Terminer(_VueTentative):
    """POST {"temps": {question: ms}} — clôt la tentative et renvoie la correction."""

    def post(self, request, tentative_id):
        tentative = _ma_tentative(request, tentative_id)
        tentative = regles.terminer(tentative, temps=request.data.get("temps"))
        return Response(etat_tentative(tentative))
