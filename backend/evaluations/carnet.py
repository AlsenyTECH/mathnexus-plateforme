"""Le carnet d'erreurs : rempli à partir des évaluations terminées, révisé à intervalles croissants."""
from datetime import timedelta

from django.utils import timezone

from .models import EntreeCarnet, Reponse

INTERVALLES_JOURS = (1, 3, 7)  # après 1, 2, 3 bonnes réponses de suite
MAITRISE = len(INTERVALLES_JOURS)


def synchroniser(utilisateur):
    """Ajoute au carnet les questions ratées des évaluations terminées qui n'y sont pas encore.

    Appelé à la lecture (pas de tâche planifiée sur l'hébergement actuel) ; une question déjà dans le
    carnet n'est pas ajoutée deux fois, même ratée dans une autre tentative.
    """
    deja = set(EntreeCarnet.objects.filter(utilisateur=utilisateur).values_list("question_id", flat=True))
    ratees = (
        Reponse.objects.filter(tentative__utilisateur=utilisateur, tentative__terminee_le__isnull=False)
        .exclude(juste=True)
        .select_related("tentative")
        .order_by("tentative__terminee_le")
    )
    nouvelles = {}
    for r in ratees:
        if r.question_id in deja or r.question_id in nouvelles:
            continue
        nouvelles[r.question_id] = EntreeCarnet(
            utilisateur=utilisateur, groupe_id=r.tentative.groupe_id, question_id=r.question_id,
            tentative=r.tentative, ajoutee_le=r.tentative.terminee_le, a_revoir_le=r.tentative.terminee_le,
        )
    EntreeCarnet.objects.bulk_create(nouvelles.values(), ignore_conflicts=True)


def a_revoir(utilisateur, groupe=None, maintenant=None):
    """Les entrées dues (pas maîtrisées, date de révision passée)."""
    qs = EntreeCarnet.objects.filter(utilisateur=utilisateur, maitrisee_le__isnull=True,
                                     a_revoir_le__lte=maintenant or timezone.now())
    return qs.filter(groupe=groupe) if groupe is not None else qs


def enregistrer_revision(entree, juste, maintenant=None):
    maintenant = maintenant or timezone.now()
    entree.revisions += 1
    entree.revue_le = maintenant
    if juste:
        entree.reussites_de_suite += 1
        if entree.reussites_de_suite >= MAITRISE:
            entree.maitrisee_le = maintenant
        else:
            entree.a_revoir_le = maintenant + timedelta(days=INTERVALLES_JOURS[entree.reussites_de_suite - 1])
    else:
        entree.reussites_de_suite = 0
        entree.a_revoir_le = maintenant + timedelta(days=1)
    entree.save()
    return entree
