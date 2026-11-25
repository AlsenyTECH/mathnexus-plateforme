from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from contenus.acces import est_prof_ou_admin, etat_etape
from contenus.vues import _contexte
from organisations.acces import groupes_enseignes
from organisations.models import Inscription

from .models import Progression


class ValiderEtape(APIView):
    """« J'ai compris, étape suivante » : l'élève valide l'étape."""

    def post(self, request, pk, slug, cle):
        groupe, rattachement, version = _contexte(request, pk, slug)
        etape = get_object_or_404(version.etapes, cle=cle)
        if est_prof_ou_admin(request.user, groupe):
            return Response({"validee": False, "detail": "Seule la progression des élèves est enregistrée."})
        _, accessible, raison = etat_etape(request.user, groupe, rattachement, etape, privilegie=False)
        if not accessible:
            return Response({"raison": raison}, status=status.HTTP_403_FORBIDDEN)
        prog, _ = Progression.objects.get_or_create(
            utilisateur=request.user, parcours=rattachement.parcours, cle_etape=etape.cle
        )
        if prog.validee_le is None:
            prog.validee_le = timezone.now()
            prog.save(update_fields=["validee_le", "derniere_ouverture_le"])
        return Response({"validee": True, "validee_le": prog.validee_le})


class ProgressionDuGroupe(APIView):
    """Le tableau du prof : chaque élève et les étapes qu'il a validées."""

    def get(self, request, pk, slug):
        groupe = get_object_or_404(groupes_enseignes(request.user), pk=pk)
        _, rattachement, version = _contexte(request, pk, slug)
        etapes = list(version.etapes.values("cle", "titre"))
        eleves = (
            Inscription.objects.filter(groupe=groupe, role=Inscription.Role.ELEVE, statut=Inscription.Statut.VALIDEE)
            .select_related("utilisateur")
            .order_by("utilisateur__nom", "utilisateur__prenom")
        )
        progressions = {}
        for p in Progression.objects.filter(parcours=rattachement.parcours, utilisateur__in=[i.utilisateur for i in eleves]):
            progressions.setdefault(p.utilisateur_id, []).append(p)
        lignes = []
        for i in eleves:
            props = progressions.get(i.utilisateur_id, [])
            lignes.append({
                "utilisateur": str(i.utilisateur_id), "prenom": i.utilisateur.prenom, "nom": i.utilisateur.nom,
                "validees": sorted(p.cle_etape for p in props if p.validee_le),
                "derniere_activite": max((p.derniere_ouverture_le for p in props), default=None),
            })
        return Response({"etapes": etapes, "eleves": lignes})
