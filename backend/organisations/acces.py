"""Le périmètre de chaque compte, calculé côté serveur.

Toutes les vues passent par ces fonctions : un élève ne voit que les groupes où son
inscription est validée, un prof que les groupes où il enseigne, l'admin voit tout.
"""
from .models import Groupe, Inscription


def groupes_visibles(utilisateur):
    if not utilisateur.is_authenticated:
        return Groupe.objects.none()
    if utilisateur.est_admin:
        return Groupe.objects.filter(archive=False)
    if utilisateur.statut != utilisateur.Statut.ACTIF:
        return Groupe.objects.none()
    return Groupe.objects.filter(
        archive=False,
        inscriptions__utilisateur=utilisateur,
        inscriptions__statut=Inscription.Statut.VALIDEE,
    ).distinct()


def groupes_enseignes(utilisateur):
    """Groupes dont le compte peut voir les élèves et leur progression."""
    if utilisateur.est_admin:
        return Groupe.objects.filter(archive=False)
    return groupes_visibles(utilisateur).filter(
        inscriptions__utilisateur=utilisateur,
        inscriptions__role=Inscription.Role.PROF,
        inscriptions__statut=Inscription.Statut.VALIDEE,
    ).distinct()


def destination_apres_connexion(utilisateur):
    """Où envoyer le compte quand il se connecte.

    Renvoie un dictionnaire que l'application React traduit en écran.
    """
    if utilisateur.est_admin:
        return {"type": "admin"}
    if utilisateur.statut == utilisateur.Statut.EN_ATTENTE:
        return {"type": "attente"}
    if utilisateur.doit_changer_mot_de_passe:
        return {"type": "changer_mot_de_passe"}
    if groupes_enseignes(utilisateur).exists():
        return {"type": "prof"}
    groupes = list(groupes_visibles(utilisateur))
    if not groupes:
        return {"type": "aucun_groupe"}
    if len(groupes) == 1:
        return {"type": "groupe", "groupe": str(groupes[0].id)}
    dernier = utilisateur.dernier_groupe_id
    if dernier and any(g.id == dernier for g in groupes):
        return {"type": "groupe", "groupe": str(dernier)}
    return {"type": "choix_groupe", "groupes": [str(g.id) for g in groupes]}
