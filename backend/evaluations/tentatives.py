"""Les règles d'une tentative : commencer, répondre, mesurer le temps, terminer, corriger.

Tout ce qui compte se décide ici, côté serveur :
- l'échéance (le navigateur n'affiche qu'un compte à rebours) ;
- le temps retenu par question (le navigateur mesure, le serveur plafonne) ;
- le score (les bonnes réponses ne quittent jamais le serveur avant la fin).
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Question, Reponse, Tentative

# Délai accordé après l'échéance pour une réponse partie juste avant la fin (réseau lent).
GRACE = timedelta(seconds=5)
# Écart toléré entre l'horloge du navigateur et celle du serveur sur le temps total.
TOLERANCE_MS = 2000


class TentativeClose(Exception):
    """La tentative est terminée (par l'élève ou par l'échéance) : plus de réponse possible."""


class ReponseInvalide(Exception):
    pass


def commencer(utilisateur, groupe, evaluation, maintenant=None):
    """Renvoie (tentative, creee). Une tentative en cours est reprise au lieu d'en ouvrir une autre."""
    maintenant = maintenant or timezone.now()
    en_cours = Tentative.objects.filter(
        utilisateur=utilisateur, groupe=groupe, parcours=evaluation.version.parcours,
        cle_evaluation=evaluation.cle, terminee_le__isnull=True,
    ).first()
    if en_cours is not None:
        en_cours = clore_si_echue(en_cours, maintenant)
        if not en_cours.terminee:
            return en_cours, False
    tentative = Tentative.objects.create(
        utilisateur=utilisateur, groupe=groupe, parcours=evaluation.version.parcours,
        cle_evaluation=evaluation.cle, evaluation=evaluation, commencee_le=maintenant,
        echeance=maintenant + timedelta(minutes=evaluation.duree_min) if evaluation.duree_min else None,
        total=evaluation.total,
    )
    return tentative, True


def secondes_restantes(tentative, maintenant=None):
    if tentative.echeance is None or tentative.terminee:
        return None
    reste = (tentative.echeance - (maintenant or timezone.now())).total_seconds()
    return max(0, int(reste))


def echue(tentative, maintenant):
    return tentative.echeance is not None and maintenant > tentative.echeance + GRACE


def clore_si_echue(tentative, maintenant=None):
    """Termine une tentative dont l'échéance est passée (on n'a pas besoin de tâche planifiée :
    la clôture se fait à la prochaine requête qui la touche). Renvoie la tentative à jour."""
    maintenant = maintenant or timezone.now()
    if not tentative.terminee and echue(tentative, maintenant):
        return terminer(tentative, maintenant=maintenant, fin=Tentative.Fin.TEMPS_ECOULE)
    return tentative


def _valider_choix(question, choix):
    """Liste d'indices distincts et existants ; None ou [] : pas de réponse."""
    if choix is None or choix == []:
        return None
    if not isinstance(choix, list) or not all(isinstance(c, int) and not isinstance(c, bool) for c in choix):
        raise ReponseInvalide("choix doit être une liste d'indices (à partir de 0).")
    if len(set(choix)) != len(choix) or any(not 0 <= c < len(question.choix) for c in choix):
        raise ReponseInvalide("choix désigne un choix qui n'existe pas, ou deux fois le même.")
    if question.type == Question.Type.CHOIX_UNIQUE and len(choix) > 1:
        raise ReponseInvalide("Une seule réponse possible à cette question.")
    return sorted(choix)


def _valider_temps(temps_ms):
    if temps_ms is None:
        return 0
    if not isinstance(temps_ms, int) or isinstance(temps_ms, bool) or temps_ms < 0:
        raise ReponseInvalide("temps_ms doit être un entier positif (millisecondes).")
    return temps_ms


def _ecoule_ms(tentative, maintenant):
    fin = maintenant if tentative.echeance is None else min(maintenant, tentative.echeance)
    return max(0, int((fin - tentative.commencee_le).total_seconds() * 1000))


def _retenir_temps(tentative, reponse, temps_client, maintenant):
    """Le temps d'une question ne recule jamais, et la somme des temps de la tentative ne dépasse
    pas le temps réellement écoulé depuis le début (plus une petite tolérance d'horloge)."""
    autres = sum(tentative.reponses.exclude(pk=reponse.pk).values_list("temps_ms", flat=True))
    plafond = max(0, _ecoule_ms(tentative, maintenant) + TOLERANCE_MS - autres)
    return min(max(reponse.temps_ms, temps_client), plafond)


@transaction.atomic
def repondre(tentative, cle_question, choix, temps_ms, maintenant=None):
    """Enregistre (ou modifie) la réponse à une question. `choix` vide : seulement le temps."""
    maintenant = maintenant or timezone.now()
    tentative = clore_si_echue(Tentative.objects.select_for_update().get(pk=tentative.pk), maintenant)
    if tentative.terminee:
        raise TentativeClose()
    try:
        question = tentative.evaluation.questions.get(cle=cle_question)
    except Question.DoesNotExist:
        raise ReponseInvalide(f"Question « {cle_question} » inconnue dans cette évaluation.")
    choix = _valider_choix(question, choix)
    temps_ms = _valider_temps(temps_ms)

    reponse, _ = Reponse.objects.get_or_create(tentative=tentative, question=question)
    reponse.temps_ms = _retenir_temps(tentative, reponse, temps_ms, maintenant)
    if choix is not None or reponse.choix is not None:
        if choix != reponse.choix:
            if reponse.choix is not None:
                reponse.modifications += 1
            reponse.choix = choix
            reponse.premiere_reponse_le = reponse.premiere_reponse_le or maintenant
            reponse.derniere_reponse_le = maintenant
    reponse.save()
    return reponse


@transaction.atomic
def terminer(tentative, temps=None, maintenant=None, fin=Tentative.Fin.TERMINEE):
    """Clôt la tentative et la corrige. `temps` : derniers temps mesurés {cle_question: ms}."""
    maintenant = maintenant or timezone.now()
    tentative = Tentative.objects.select_for_update().get(pk=tentative.pk)
    if tentative.terminee:
        return tentative
    if fin == Tentative.Fin.TERMINEE and echue(tentative, maintenant):
        fin = Tentative.Fin.TEMPS_ECOULE

    if temps and fin == Tentative.Fin.TERMINEE:
        if not isinstance(temps, dict):
            raise ReponseInvalide("temps doit être un objet {question: millisecondes}.")
        questions = {q.cle: q for q in tentative.evaluation.questions.all()}
        for cle, ms in temps.items():
            if cle not in questions:
                raise ReponseInvalide(f"Question « {cle} » inconnue dans cette évaluation.")
            reponse, _ = Reponse.objects.get_or_create(tentative=tentative, question=questions[cle])
            reponse.temps_ms = _retenir_temps(tentative, reponse, _valider_temps(ms), maintenant)
            reponse.save(update_fields=["temps_ms"])

    reponses = {r.question_id: r for r in tentative.reponses.all()}
    score = Decimal(0)
    for question in tentative.evaluation.questions.all():
        reponse = reponses.get(question.id) or Reponse(tentative=tentative, question=question)
        reponse.juste = question.est_juste(reponse.choix)
        reponse.points = question.points if reponse.juste else Decimal(0)
        reponse.save()
        score += reponse.points

    seuil = tentative.evaluation.seuil
    tentative.score = score
    tentative.reussie = None if seuil is None else score >= seuil
    tentative.terminee_le = min(maintenant, tentative.echeance) if fin == Tentative.Fin.TEMPS_ECOULE else maintenant
    tentative.fin = fin
    tentative.save()
    return tentative
