"""Qui peut lire quelle étape, dans quel groupe.

Une étape est lisible par un élève si :
1. le groupe fait partie de ses groupes visibles (compte actif, inscription validée) ;
2. le parcours est rattaché à ce groupe et a une version publiée ;
3. l'étape est ouverte (ouverture « tout », ou ouverte par le prof en ouverture progressive) ;
4. son niveau d'accès le permet (public et inscrit : oui ; premium : selon ses droits).

Le prof du groupe et l'admin lisent tout, y compris les étapes pas encore ouvertes.
"""
from organisations.acces import groupes_enseignes, groupes_visibles

from .models import Etape, Rattachement


def a_acces_premium(utilisateur, groupe, parcours):
    """Droits premium d'un élève. Branché sur les offres et abonnements à la phase 4.

    En attendant, seuls les profs du groupe et l'admin y accèdent.
    """
    return est_prof_ou_admin(utilisateur, groupe)


def est_prof_ou_admin(utilisateur, groupe):
    return groupes_enseignes(utilisateur).filter(pk=groupe.pk).exists()


def rattachements_lisibles(utilisateur, groupe):
    """Les parcours du groupe qui ont une version publiée, si le groupe est visible."""
    if not groupes_visibles(utilisateur).filter(pk=groupe.pk).exists():
        return Rattachement.objects.none()
    return (
        Rattachement.objects.filter(groupe=groupe, parcours__versions__statut="publiee")
        .select_related("parcours__matiere")
        .distinct()
    )


def etat_etape(utilisateur, groupe, rattachement, etape, *, privilegie=None, cles_ouvertes=None):
    """Renvoie (ouverte, accessible, raison). `raison` explique un refus à l'élève."""
    if privilegie is None:
        privilegie = est_prof_ou_admin(utilisateur, groupe)
    if privilegie:
        return True, True, None
    if rattachement.ouverture == Rattachement.Ouverture.PROGRESSIVE:
        if cles_ouvertes is None:
            cles_ouvertes = rattachement.cles_ouvertes()
        if etape.cle not in cles_ouvertes:
            return False, False, "pas_encore_ouverte"
    if etape.acces == Etape.Acces.PREMIUM and not a_acces_premium(utilisateur, groupe, rattachement.parcours):
        return True, False, "premium"
    return True, True, None
