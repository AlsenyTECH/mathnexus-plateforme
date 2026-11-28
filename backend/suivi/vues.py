"""Le suivi : la séance du jour de l'élève, le tableau de classe et la fiche élève du prof, le bilan parent.

Rien n'est stocké ici : tout est calculé à la demande à partir des devoirs, des tentatives, de la
progression et du carnet d'erreurs. Accès : un élève ne voit que sa séance ; un prof ne voit que
les élèves validés de ses classes (hors périmètre : 404).
"""
from datetime import timedelta

from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.models import Utilisateur
from contenus.acces import etat_etape, rattachements_lisibles
from devoirs.models import Devoir, Rendu
from devoirs.regles import devoirs_de_l_eleve, etat, groupes_comme_eleve, nombre, sujet_visible
from evaluations import carnet as regles_carnet
from evaluations.models import EntreeCarnet, Tentative
from organisations.acces import groupes_enseignes
from organisations.models import Inscription
from progression.models import Progression

# --- Outils communs ---------------------------------------------------------------------


def _eleves(groupe):
    return Utilisateur.objects.filter(
        inscriptions__groupe=groupe, inscriptions__role=Inscription.Role.ELEVE,
        inscriptions__statut=Inscription.Statut.VALIDEE,
    ).order_by("nom", "prenom").distinct()


def _devoirs_pour(groupe, eleve):
    from django.db.models import Q

    return Devoir.objects.filter(groupe=groupe).filter(Q(eleve__isnull=True) | Q(eleve=eleve)).select_related("parcours")


def _etats(groupe, eleve, maintenant):
    devoirs = list(_devoirs_pour(groupe, eleve))
    rendus = {r.devoir_id: r for r in Rendu.objects.filter(eleve=eleve, devoir__in=devoirs)}
    return [(d, etat(d, eleve, rendus.get(d.id), maintenant)) for d in devoirs]


def _sur_20(d, e):
    """La note d'un devoir ramenée sur 20 : celle du prof, sinon le score de l'évaluation."""
    if e["note"] is not None and d.note_sur:
        return 20 * e["note"] / float(d.note_sur)
    if e["score"] is not None and e["total"]:
        return 20 * e["score"] / e["total"]
    return None


def _progression(groupe, eleve):
    """Par parcours de la classe : étapes validées / total, et la dernière ouverture."""
    resultat = []
    for r in rattachements_lisibles(eleve, groupe):
        version = r.parcours.version_publiee()
        cles = list(version.etapes.values_list("cle", flat=True)) if version else []
        validees = Progression.objects.filter(
            utilisateur=eleve, parcours=r.parcours, cle_etape__in=cles, validee_le__isnull=False
        ).count()
        derniere = Progression.objects.filter(utilisateur=eleve, parcours=r.parcours).aggregate(m=Max("derniere_ouverture_le"))["m"]
        resultat.append({"slug": r.parcours.slug, "titre": r.parcours.titre, "validees": validees,
                         "total": len(cles), "derniere_ouverture": derniere})
    return resultat


def _derniere_activite(eleve):
    dates = [
        eleve.last_login,
        Progression.objects.filter(utilisateur=eleve).aggregate(m=Max("derniere_ouverture_le"))["m"],
        Rendu.objects.filter(eleve=eleve).aggregate(m=Max("modifie_le"))["m"],
        Tentative.objects.filter(utilisateur=eleve).aggregate(m=Max("commencee_le"))["m"],
    ]
    dates = [d for d in dates if d]
    return max(dates) if dates else None


def _eleve_du_prof(request, pk, eleve_id):
    groupe = get_object_or_404(groupes_enseignes(request.user), pk=pk)
    eleve = get_object_or_404(_eleves(groupe), pk=eleve_id)
    return groupe, eleve


def _resume_eleve(groupe, eleve, maintenant):
    etats = _etats(groupe, eleve, maintenant)
    notes = [n for n in (_sur_20(d, e) for d, e in etats) if n is not None]
    regles_carnet.synchroniser(eleve)
    carnet = EntreeCarnet.objects.filter(utilisateur=eleve, groupe=groupe)
    progression = _progression(groupe, eleve)
    return {
        "eleve": str(eleve.id), "prenom": eleve.prenom, "nom": eleve.nom,
        "devoirs": len(etats),
        "termines": sum(e["statut"] in ("rendu", "fait", "corrige") for _, e in etats),
        "en_retard": sum(e["statut"] == "en_retard" for _, e in etats),
        "a_corriger": sum(e["statut"] == "rendu" for _, e in etats),
        "moyenne": round(sum(notes) / len(notes), 2) if notes else None,
        "etapes_validees": sum(p["validees"] for p in progression),
        "etapes_total": sum(p["total"] for p in progression),
        "carnet_a_revoir": regles_carnet.a_revoir(eleve, groupe, maintenant).count(),
        "carnet_maitrisees": carnet.filter(maitrisee_le__isnull=False).count(),
        "derniere_activite": _derniere_activite(eleve),
    }


# --- L'élève : sa séance du jour ----------------------------------------------------------


class SeanceDuJour(APIView):
    """Ce que l'élève a à faire aujourd'hui dans une classe : devoirs, étapes suivantes, révisions."""

    def get(self, request, pk):
        groupe = get_object_or_404(groupes_comme_eleve(request.user), pk=pk)
        maintenant = timezone.now()
        fin_du_jour = timezone.localtime(maintenant).replace(hour=23, minute=59, second=59)

        devoirs = []
        rendus = {r.devoir_id: r for r in Rendu.objects.filter(eleve=request.user, devoir__groupe=groupe)}
        for d in devoirs_de_l_eleve(request.user).filter(groupe=groupe).select_related("parcours"):
            e = etat(d, request.user, rendus.get(d.id), maintenant)
            if e["statut"] in ("a_faire", "en_retard"):
                devoirs.append({
                    "id": str(d.id), "titre": d.titre, "type": d.type, "date_limite": d.date_limite,
                    "duree_min": d.duree_min, "statut": e["statut"], "commence_le": e["commence_le"],
                    "pour_aujourd_hui": bool(d.date_limite and d.date_limite <= fin_du_jour),
                    "sujet_masque": not sujet_visible(d, rendus.get(d.id), maintenant),
                })
        devoirs.sort(key=lambda x: (x["statut"] != "en_retard", x["date_limite"] or fin_du_jour + timedelta(days=365)))

        # Les étapes suivantes : la première étape accessible et pas encore validée de chaque parcours,
        # en commençant par les parcours ouverts le plus récemment.
        etapes = []
        for r in rattachements_lisibles(request.user, groupe):
            version = r.parcours.version_publiee()
            if version is None:
                continue
            progres = {p.cle_etape: p for p in Progression.objects.filter(utilisateur=request.user, parcours=r.parcours)}
            cles_ouvertes = r.cles_ouvertes()
            for partie in version.parties.prefetch_related("etapes"):
                suivante = None
                for e in partie.etapes.all():
                    p = progres.get(e.cle)
                    if p and p.validee_le:
                        continue
                    _, accessible, _ = etat_etape(request.user, groupe, r, e, privilegie=False, cles_ouvertes=cles_ouvertes)
                    if accessible:
                        suivante = e
                        break
                if suivante:
                    derniere = max((p.derniere_ouverture_le for p in progres.values()), default=None)
                    etapes.append({
                        "parcours": r.parcours.slug, "parcours_titre": r.parcours.titre, "cle": suivante.cle,
                        "titre": suivante.titre, "duree_min": suivante.duree_min, "partie": partie.titre,
                        "commencee": suivante.cle in progres, "derniere_ouverture": derniere,
                    })
                    break
        etapes.sort(key=lambda x: (x["derniere_ouverture"] is None, -(x["derniere_ouverture"].timestamp() if x["derniere_ouverture"] else 0)))

        regles_carnet.synchroniser(request.user)
        dues = regles_carnet.a_revoir(request.user, groupe, maintenant)
        # Deux parcours au plus : ceux en cours ; si aucun n'est commencé, le premier seulement.
        nombre_etapes = 2 if any(e["derniere_ouverture"] for e in etapes) else 1
        return Response({
            "date": timezone.localdate(),
            "devoirs": devoirs,
            "etapes": etapes[:nombre_etapes],
            "autres_parcours": max(0, len(etapes) - nombre_etapes),
            "revisions": dues.count(),
        })


# --- Le prof : tableau de classe, fiche élève, bilan ------------------------------------------


class TableauDeClasse(APIView):
    """Le prof : une ligne par élève (devoirs, retards, moyenne, étapes, carnet, dernière activité)."""

    def get(self, request, pk):
        groupe = get_object_or_404(groupes_enseignes(request.user), pk=pk)
        maintenant = timezone.now()
        return Response([_resume_eleve(groupe, e, maintenant) for e in _eleves(groupe)])


class FicheEleve(APIView):
    """Le prof : tout sur un élève de sa classe."""

    def get(self, request, pk, eleve_id):
        groupe, eleve = _eleve_du_prof(request, pk, eleve_id)
        maintenant = timezone.now()
        etats = _etats(groupe, eleve, maintenant)
        etats.sort(key=lambda de: de[0].cree_le, reverse=True)
        tentatives = (
            Tentative.objects.filter(utilisateur=eleve, groupe=groupe, terminee_le__isnull=False)
            .select_related("evaluation", "parcours").order_by("-terminee_le")[:30]
        )
        return Response({
            **_resume_eleve(groupe, eleve, maintenant),
            "telephone": eleve.telephone, "telephone_parent": eleve.telephone_parent,
            "derniere_connexion": eleve.last_login,
            "liste_devoirs": [
                {"id": str(d.id), "titre": d.titre, "type": d.type, "date_limite": d.date_limite,
                 "note_sur": nombre(d.note_sur), "sur_20": _sur_20(d, e), **e}
                for d, e in etats
            ],
            "evaluations": [
                {"titre": t.evaluation.titre, "parcours_titre": t.parcours.titre, "score": nombre(t.score),
                 "total": nombre(t.total), "terminee_le": t.terminee_le, "reussie": t.reussie}
                for t in tentatives
            ],
            "progression": _progression(groupe, eleve),
        })


def _bilan(groupe, eleve, jours, maintenant):
    debut = maintenant - timedelta(days=jours)
    etats = [(d, e) for d, e in _etats(groupe, eleve, maintenant) if d.cree_le >= debut or (d.date_limite and d.date_limite >= debut)]
    faits = [(d, e) for d, e in etats if e["statut"] in ("rendu", "fait", "corrige")]
    retards = [d for d, e in etats if e["statut"] == "en_retard"]
    notes = [(d, _sur_20(d, e)) for d, e in etats if _sur_20(d, e) is not None]
    etapes = Progression.objects.filter(utilisateur=eleve, validee_le__gte=debut).count()
    regles_carnet.synchroniser(eleve)
    maitrisees = EntreeCarnet.objects.filter(utilisateur=eleve, groupe=groupe, maitrisee_le__gte=debut).count()

    def note(x):
        return f"{x:.1f}".replace(".0", "").replace(".", ",")

    lignes = [
        f"Bonjour, voici le bilan des {jours} derniers jours de {eleve.prenom} ({groupe.nom}) :",
        f"• Travaux : {len(faits)} fait{'s' if len(faits) > 1 else ''} sur {len(etats)} donné{'s' if len(etats) > 1 else ''}"
        + (f", {len(retards)} en retard" if retards else "") + ".",
    ]
    if notes:
        moyenne = sum(n for _, n in notes) / len(notes)
        lignes.append(f"• Notes : " + " ; ".join(f"{d.titre} : {note(n)}/20" for d, n in notes[:6]) + f" (moyenne {note(moyenne)}/20).")
    if etapes:
        lignes.append(f"• Cours : {etapes} étape{'s' if etapes > 1 else ''} terminée{'s' if etapes > 1 else ''}.")
    if maitrisees:
        lignes.append(f"• Erreurs corrigées et maîtrisées : {maitrisees}.")
    if retards:
        lignes.append("• À rattraper : " + " ; ".join(d.titre for d in retards[:5]) + ".")
    lignes.append("Mathnexus")
    return {
        "jours": jours, "texte": "\n".join(lignes), "telephone_parent": eleve.telephone_parent,
        "telephone": eleve.telephone, "travaux_faits": len(faits), "travaux_donnes": len(etats),
        "en_retard": len(retards), "etapes": etapes,
        "moyenne": round(sum(n for _, n in notes) / len(notes), 2) if notes else None,
    }


class BilanParent(APIView):
    """Le prof : le bilan de la période, prêt à envoyer au parent (WhatsApp ou SMS) après relecture."""

    def get(self, request, pk, eleve_id):
        groupe, eleve = _eleve_du_prof(request, pk, eleve_id)
        try:
            jours = min(max(int(request.query_params.get("jours", 7)), 1), 90)
        except ValueError:
            jours = 7
        return Response(_bilan(groupe, eleve, jours, timezone.now()))
