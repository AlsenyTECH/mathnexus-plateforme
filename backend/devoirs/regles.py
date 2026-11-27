"""Les règles des devoirs : qui voit quoi, et où en est chaque élève.

Comme ailleurs dans la plateforme, tout part de organisations.acces : un prof ne voit que les
devoirs des classes où il enseigne, un élève que ceux de ses classes (et seulement ceux qui lui
sont destinés). Hors périmètre : 404.
"""
from django.db.models import Q
from django.utils import timezone

from evaluations.models import Tentative
from organisations.acces import groupes_enseignes
from organisations.models import Groupe, Inscription
from progression.models import Progression

from .models import Devoir


def groupes_comme_eleve(utilisateur):
    """Les classes où le compte est inscrit comme élève (l'admin aussi, s'il s'est inscrit dans une classe)."""
    if not utilisateur.is_authenticated or not utilisateur.peut_utiliser:
        return Groupe.objects.none()
    return Groupe.objects.filter(
        archive=False,
        inscriptions__utilisateur=utilisateur,
        inscriptions__role=Inscription.Role.ELEVE,
        inscriptions__statut=Inscription.Statut.VALIDEE,
    ).distinct()


def devoirs_de_l_eleve(utilisateur):
    return Devoir.objects.filter(groupe__in=groupes_comme_eleve(utilisateur)).filter(
        Q(eleve__isnull=True) | Q(eleve=utilisateur)
    )


def devoirs_du_prof(utilisateur):
    return Devoir.objects.filter(groupe__in=groupes_enseignes(utilisateur))


def eleves_concernes(devoir):
    """Les élèves validés à qui le devoir est destiné."""
    from comptes.models import Utilisateur

    eleves = Utilisateur.objects.filter(
        inscriptions__groupe=devoir.groupe,
        inscriptions__role=Inscription.Role.ELEVE,
        inscriptions__statut=Inscription.Statut.VALIDEE,
    )
    if devoir.eleve_id:
        eleves = eleves.filter(pk=devoir.eleve_id)
    return eleves.order_by("nom", "prenom").distinct()


def tentative_du_devoir(devoir, eleve):
    """La dernière tentative terminée de l'évaluation, commencée après que le devoir a été donné."""
    if devoir.type != Devoir.Type.EVALUATION or not devoir.parcours_id:
        return None
    return (
        Tentative.objects.filter(
            utilisateur=eleve, groupe=devoir.groupe, parcours=devoir.parcours,
            cle_evaluation=devoir.cle_evaluation, terminee_le__isnull=False, commencee_le__gte=devoir.cree_le,
        )
        .order_by("-terminee_le")
        .first()
    )


def etape_validee(devoir, eleve):
    if devoir.type != Devoir.Type.ETAPE or not devoir.parcours_id:
        return False
    return Progression.objects.filter(
        utilisateur=eleve, parcours=devoir.parcours, cle_etape=devoir.cle_etape, validee_le__isnull=False
    ).exists()


def nombre(decimal):
    return None if decimal is None else float(decimal)


def etat(devoir, eleve, rendu=None, maintenant=None):
    """Où en est un élève sur un devoir.

    statut : corrige > rendu (envoyé, à corriger) > fait (évaluation terminée ou étape validée,
    sans copie envoyée) > en_retard > a_faire.
    """
    maintenant = maintenant or timezone.now()
    tentative = tentative_du_devoir(devoir, eleve)
    if rendu is not None and rendu.corrige_le:
        statut = "corrige"
    elif rendu is not None and rendu.rendu_le:
        statut = "rendu"
    elif tentative is not None or etape_validee(devoir, eleve):
        statut = "fait"
    elif devoir.en_retard(maintenant):
        statut = "en_retard"
    else:
        statut = "a_faire"
    return {
        "statut": statut,
        "rendu_le": rendu.rendu_le if rendu else None,
        "note": nombre(rendu.note) if rendu else None,
        "corrige_le": rendu.corrige_le if rendu else None,
        "score": nombre(tentative.score) if tentative else None,
        "total": nombre(tentative.total) if tentative else None,
        "tentative_terminee_le": tentative.terminee_le if tentative else None,
    }
