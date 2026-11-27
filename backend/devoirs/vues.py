"""API des devoirs : le prof donne du travail et corrige, l'élève rend et lit sa correction.

Sécurité (voir regles.py) : tout passe par les classes du compte ; hors périmètre, 404.
Un élève ne voit que ses propres rendus ; la correction n'est modifiable que par un prof de la
classe ; une copie corrigée ne se modifie plus.
"""
from datetime import datetime, time

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.models import JournalAudit, Utilisateur
from contenus.models import Rattachement
from evaluations.models import Evaluation
from organisations.acces import groupes_enseignes

from . import photos as regles_photos
from .models import Devoir, Photo, Rendu
from .regles import devoirs_de_l_eleve, devoirs_du_prof, eleves_concernes, etat, nombre

# --- Représentations -------------------------------------------------------------------


def _resume_devoir(d):
    return {
        "id": str(d.id), "groupe": str(d.groupe_id), "groupe_nom": d.groupe.nom, "type": d.type,
        "titre": d.titre, "consigne": d.consigne, "date_limite": d.date_limite, "note_sur": nombre(d.note_sur),
        "parcours": d.parcours.slug if d.parcours_id else None,
        "parcours_titre": d.parcours.titre if d.parcours_id else None,
        "cle_etape": d.cle_etape or None, "cle_evaluation": d.cle_evaluation or None,
        "eleve": str(d.eleve_id) if d.eleve_id else None,
        "eleve_nom": f"{d.eleve.prenom} {d.eleve.nom}" if d.eleve_id else None,
        "cree_le": d.cree_le,
    }


def _photos(rendu, cote):
    return [
        {"id": str(p.id), "taille": p.taille, "url": f"/api/photos/{p.id}/"}
        for p in rendu.photos.all() if p.cote == cote
    ] if rendu else []


def _rendu(rendu):
    if rendu is None:
        return None
    return {
        "texte": rendu.texte, "rendu_le": rendu.rendu_le, "note": nombre(rendu.note),
        "commentaire": rendu.commentaire if rendu.corrige_le else "",
        "correction": rendu.correction if rendu.corrige_le else "",
        "corrige_le": rendu.corrige_le,
        "photos": _photos(rendu, Photo.Cote.ELEVE),
        "photos_correction": _photos(rendu, Photo.Cote.CORRECTION) if rendu.corrige_le else [],
    }


def _rendu_prof(rendu):
    """Le prof voit aussi son brouillon de correction."""
    if rendu is None:
        return None
    donnees = _rendu(rendu)
    donnees.update(
        commentaire=rendu.commentaire, correction=rendu.correction,
        photos_correction=_photos(rendu, Photo.Cote.CORRECTION),
    )
    return donnees


def _rendus_par_eleve(devoir):
    return {r.eleve_id: r for r in devoir.rendus.prefetch_related("photos")}


# --- Le prof ----------------------------------------------------------------------------


class DevoirSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=Devoir.Type.choices)
    titre = serializers.CharField(max_length=200, required=False, allow_blank=True)
    consigne = serializers.CharField(required=False, allow_blank=True, max_length=10_000)
    eleve = serializers.UUIDField(required=False, allow_null=True)
    parcours = serializers.SlugField(required=False, allow_blank=True, allow_null=True)
    cle_etape = serializers.CharField(required=False, allow_blank=True, max_length=60)
    cle_evaluation = serializers.CharField(required=False, allow_blank=True, max_length=60)
    date_limite = serializers.DateTimeField(required=False, allow_null=True)
    note_sur = serializers.DecimalField(max_digits=6, decimal_places=2, required=False, min_value=1, max_value=1000)


def _preparer(groupe, donnees):
    """Vérifie un devoir (élève de la classe, étape ou évaluation publiée et rattachée) ; renvoie les champs."""
    champs = {"type": donnees["type"], "consigne": donnees.get("consigne", ""), "date_limite": donnees.get("date_limite")}
    if "note_sur" in donnees:
        champs["note_sur"] = donnees["note_sur"]
    titre = (donnees.get("titre") or "").strip()
    if donnees.get("eleve"):
        eleve = Utilisateur.objects.filter(
            pk=donnees["eleve"], inscriptions__groupe=groupe, inscriptions__role="eleve", inscriptions__statut="validee"
        ).first()
        if eleve is None:
            raise ValidationError({"eleve": "Cet élève n'est pas dans la classe."})
        champs["eleve"] = eleve
    else:
        champs["eleve"] = None
    if donnees["type"] == Devoir.Type.LIBRE:
        if not titre:
            raise ValidationError({"titre": "Donne un titre au travail."})
        champs.update(parcours=None, cle_etape="", cle_evaluation="", titre=titre)
        return champs
    rattachement = Rattachement.objects.filter(groupe=groupe, parcours__slug=donnees.get("parcours") or "").select_related("parcours").first()
    if rattachement is None:
        raise ValidationError({"parcours": "Ce parcours n'est pas rattaché à la classe."})
    version = rattachement.parcours.version_publiee()
    if version is None:
        raise ValidationError({"parcours": "Ce parcours n'a pas de version publiée."})
    champs["parcours"] = rattachement.parcours
    if donnees["type"] == Devoir.Type.ETAPE:
        etape = version.etapes.filter(cle=donnees.get("cle_etape") or "").first()
        if etape is None:
            raise ValidationError({"cle_etape": "Étape introuvable dans ce parcours."})
        champs.update(cle_etape=etape.cle, cle_evaluation="", titre=titre or etape.titre)
    else:
        evaluation = version.evaluations.filter(cle=donnees.get("cle_evaluation") or "").select_related("etape").first()
        if evaluation is None:
            raise ValidationError({"cle_evaluation": "Évaluation introuvable dans ce parcours."})
        champs.update(cle_etape=evaluation.etape.cle, cle_evaluation=evaluation.cle, titre=titre or evaluation.titre)
        if "note_sur" not in donnees:
            champs["note_sur"] = evaluation.total
    return champs


def _date_limite_par_defaut():
    """Ce soir, 23 h 59 (heure de Dakar)."""
    return timezone.make_aware(datetime.combine(timezone.localdate(), time(23, 59)))


class DevoirsDuGroupe(APIView):
    """Le prof : la liste des devoirs d'une classe, avec l'avancement ; et donner un nouveau devoir."""

    def get(self, request, pk):
        groupe = get_object_or_404(groupes_enseignes(request.user), pk=pk)
        resultat = []
        for d in groupe.devoirs.select_related("groupe", "parcours", "eleve").prefetch_related("rendus"):
            eleves = list(eleves_concernes(d))
            rendus = {r.eleve_id: r for r in d.rendus.all()}
            etats = [etat(d, e, rendus.get(e.id))["statut"] for e in eleves]
            resultat.append({
                **_resume_devoir(d),
                "effectif": len(eleves),
                "a_corriger": etats.count("rendu"),
                "termines": sum(s in ("rendu", "fait", "corrige") for s in etats),
                "corriges": etats.count("corrige"),
            })
        return Response(resultat)

    @transaction.atomic
    def post(self, request, pk):
        groupe = get_object_or_404(groupes_enseignes(request.user), pk=pk)
        s = DevoirSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        champs = _preparer(groupe, s.validated_data)
        if not champs.get("date_limite"):
            champs["date_limite"] = _date_limite_par_defaut()
        devoir = Devoir.objects.create(groupe=groupe, cree_par=request.user, **champs)
        JournalAudit.noter(request, "devoir_donne", devoir.id, groupe=str(groupe.id), type=devoir.type)
        return Response(_resume_devoir(devoir), status=status.HTTP_201_CREATED)


class EvaluationsDuParcours(APIView):
    """Le prof : les évaluations d'un parcours rattaché, pour les donner en devoir."""

    def get(self, request, pk, slug):
        groupe = get_object_or_404(groupes_enseignes(request.user), pk=pk)
        rattachement = get_object_or_404(Rattachement, groupe=groupe, parcours__slug=slug)
        version = rattachement.parcours.version_publiee()
        if version is None:
            return Response([])
        return Response([
            {"cle": e.cle, "titre": e.titre, "cle_etape": e.etape.cle, "etape_titre": e.etape.titre,
             "duree_min": e.duree_min, "total": nombre(e.total)}
            for e in Evaluation.objects.filter(version=version).select_related("etape").order_by("etape__ordre", "cle")
        ])


class DetailDevoir(APIView):
    """Un devoir : vu par le prof (suivi de chaque élève) ou par l'élève (sa copie et sa correction)."""

    def _devoir_prof(self, request, pk):
        return devoirs_du_prof(request.user).select_related("groupe", "parcours", "eleve").filter(pk=pk).first()

    def get(self, request, pk):
        devoir = self._devoir_prof(request, pk)
        if devoir is not None:
            rendus = _rendus_par_eleve(devoir)
            return Response({
                **_resume_devoir(devoir), "vue": "prof",
                "eleves": [
                    {"eleve": str(e.id), "prenom": e.prenom, "nom": e.nom, **etat(devoir, e, rendus.get(e.id))}
                    for e in eleves_concernes(devoir)
                ],
            })
        devoir = get_object_or_404(devoirs_de_l_eleve(request.user).select_related("groupe", "parcours", "eleve"), pk=pk)
        rendu = devoir.rendus.filter(eleve=request.user).prefetch_related("photos").first()
        return Response({**_resume_devoir(devoir), "vue": "eleve", **etat(devoir, request.user, rendu), "rendu": _rendu(rendu)})

    def patch(self, request, pk):
        devoir = self._devoir_prof(request, pk)
        if devoir is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        s = DevoirSerializer(data={"type": devoir.type, **request.data}, partial=True)
        s.is_valid(raise_exception=True)
        for champ in ("titre", "consigne", "date_limite", "note_sur"):
            if champ in s.validated_data:
                setattr(devoir, champ, s.validated_data[champ])
        devoir.save()
        return Response(_resume_devoir(devoir))

    def delete(self, request, pk):
        devoir = self._devoir_prof(request, pk)
        if devoir is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        JournalAudit.noter(request, "devoir_supprime", devoir.id, titre=devoir.titre)
        devoir.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MesDevoirs(APIView):
    """L'élève : tous ses devoirs (ou ceux d'une classe), du plus urgent au plus ancien."""

    def get(self, request):
        devoirs = devoirs_de_l_eleve(request.user).select_related("groupe", "parcours", "eleve")
        groupe = request.query_params.get("groupe")
        if groupe:
            devoirs = devoirs.filter(groupe_id=groupe)
        rendus = {r.devoir_id: r for r in Rendu.objects.filter(eleve=request.user, devoir__in=devoirs)}
        resultat = [{**_resume_devoir(d), **etat(d, request.user, rendus.get(d.id))} for d in devoirs]
        ordre = {"en_retard": 0, "a_faire": 1, "rendu": 2, "fait": 3, "corrige": 4}
        resultat.sort(key=lambda x: (ordre[x["statut"]], x["date_limite"] or timezone.now()))
        return Response(resultat)


class RenduSerializer(serializers.Serializer):
    texte = serializers.CharField(required=False, allow_blank=True, max_length=20_000)
    envoyer = serializers.BooleanField(required=False, default=False)


def _rendu_modifiable(request, pk):
    devoir = get_object_or_404(devoirs_de_l_eleve(request.user), pk=pk)
    rendu, _ = Rendu.objects.get_or_create(devoir=devoir, eleve=request.user)
    if rendu.corrige_le:
        raise ValidationError({"detail": "Cette copie est déjà corrigée : elle ne se modifie plus."})
    return devoir, rendu


class RendreDevoir(APIView):
    """L'élève : enregistre sa réponse (brouillon), puis l'envoie au prof (envoyer = true)."""

    def post(self, request, pk):
        s = RenduSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        with transaction.atomic():
            devoir, rendu = _rendu_modifiable(request, pk)
            if "texte" in s.validated_data:
                rendu.texte = s.validated_data["texte"]
            if s.validated_data["envoyer"]:
                if not rendu.texte.strip() and not rendu.photos.exists():
                    raise ValidationError({"detail": "Écris ta réponse ou ajoute une photo de ta copie avant d'envoyer."})
                rendu.rendu_le = timezone.now()
            rendu.save()
        return Response({**etat(devoir, request.user, rendu), "rendu": _rendu(rendu)})


class PhotosDuRendu(APIView):
    """L'élève : ajoute une photo de sa copie."""

    def post(self, request, pk):
        try:
            donnees, mime = regles_photos.verifier(request.FILES.get("photo"))
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            devoir, rendu = _rendu_modifiable(request, pk)
            if rendu.photos.filter(cote=Photo.Cote.ELEVE).count() >= regles_photos.NOMBRE_MAX:
                return Response({"detail": f"Au plus {regles_photos.NOMBRE_MAX} photos."}, status=status.HTTP_400_BAD_REQUEST)
            Photo.objects.create(rendu=rendu, cote=Photo.Cote.ELEVE, type_mime=mime, taille=len(donnees), donnees=donnees)
        return Response({"rendu": _rendu(rendu)}, status=status.HTTP_201_CREATED)


# --- La correction ------------------------------------------------------------------------


def _devoir_et_eleve(request, pk, eleve_id):
    devoir = get_object_or_404(devoirs_du_prof(request.user).select_related("groupe", "parcours"), pk=pk)
    eleve = get_object_or_404(eleves_concernes(devoir), pk=eleve_id)
    return devoir, eleve


class CorrectionSerializer(serializers.Serializer):
    note = serializers.DecimalField(max_digits=6, decimal_places=2, required=False, allow_null=True, min_value=0)
    commentaire = serializers.CharField(required=False, allow_blank=True, max_length=10_000)
    correction = serializers.CharField(required=False, allow_blank=True, max_length=50_000)
    rendre = serializers.BooleanField(required=False, default=False, help_text="Rendre la copie corrigée à l'élève")


class CopieEleve(APIView):
    """Le prof : la copie d'un élève (texte, photos, score de l'évaluation), et sa correction."""

    def get(self, request, pk, eleve_id):
        devoir, eleve = _devoir_et_eleve(request, pk, eleve_id)
        rendu = devoir.rendus.filter(eleve=eleve).prefetch_related("photos").first()
        return Response({
            "devoir": _resume_devoir(devoir), "eleve": {"id": str(eleve.id), "prenom": eleve.prenom, "nom": eleve.nom},
            **etat(devoir, eleve, rendu), "rendu": _rendu_prof(rendu),
        })

    def post(self, request, pk, eleve_id):
        devoir, eleve = _devoir_et_eleve(request, pk, eleve_id)
        s = CorrectionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data
        if v.get("note") is not None and v["note"] > devoir.note_sur:
            raise ValidationError({"note": f"La note ne peut pas dépasser {nombre(devoir.note_sur):g}."})
        with transaction.atomic():
            rendu, _ = Rendu.objects.select_for_update().get_or_create(devoir=devoir, eleve=eleve)
            for champ in ("note", "commentaire", "correction"):
                if champ in v:
                    setattr(rendu, champ, v[champ])
            if v["rendre"]:
                rendu.corrige_le = timezone.now()
                rendu.corrige_par = request.user
            rendu.save()
        if v["rendre"]:
            JournalAudit.noter(request, "copie_corrigee", rendu.id, devoir=str(devoir.id), eleve=str(eleve.id))
        return Response({**etat(devoir, eleve, rendu), "rendu": _rendu_prof(rendu)})


class PhotosCorrection(APIView):
    """Le prof : ajoute une photo à la correction (copie annotée, corrigé manuscrit)."""

    def post(self, request, pk, eleve_id):
        devoir, eleve = _devoir_et_eleve(request, pk, eleve_id)
        try:
            donnees, mime = regles_photos.verifier(request.FILES.get("photo"))
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        rendu, _ = Rendu.objects.get_or_create(devoir=devoir, eleve=eleve)
        if rendu.photos.filter(cote=Photo.Cote.CORRECTION).count() >= regles_photos.NOMBRE_MAX:
            return Response({"detail": f"Au plus {regles_photos.NOMBRE_MAX} photos."}, status=status.HTTP_400_BAD_REQUEST)
        Photo.objects.create(rendu=rendu, cote=Photo.Cote.CORRECTION, type_mime=mime, taille=len(donnees), donnees=donnees)
        return Response({"rendu": _rendu_prof(rendu)}, status=status.HTTP_201_CREATED)


class ACorriger(APIView):
    """Le prof : toutes les copies envoyées et pas encore corrigées, des plus anciennes aux plus récentes."""

    def get(self, request):
        rendus = (
            Rendu.objects.filter(devoir__in=devoirs_du_prof(request.user), rendu_le__isnull=False, corrige_le__isnull=True)
            .select_related("devoir__groupe", "eleve")
            .order_by("rendu_le")
        )
        return Response([
            {"devoir": str(r.devoir_id), "titre": r.devoir.titre, "groupe": str(r.devoir.groupe_id),
             "groupe_nom": r.devoir.groupe.nom, "eleve": str(r.eleve_id), "prenom": r.eleve.prenom,
             "nom": r.eleve.nom, "rendu_le": r.rendu_le}
            for r in rendus
        ])


class DetailPhoto(APIView):
    """Une photo : visible de l'élève qui l'a envoyée (ou à qui elle est rendue) et des profs de la classe."""

    def _photo(self, request, pk):
        photo = get_object_or_404(Photo.objects.select_related("rendu__devoir"), pk=pk)
        rendu = photo.rendu
        est_prof = devoirs_du_prof(request.user).filter(pk=rendu.devoir_id).exists()
        est_auteur = rendu.eleve_id == request.user.id and devoirs_de_l_eleve(request.user).filter(pk=rendu.devoir_id).exists()
        if photo.cote == Photo.Cote.CORRECTION and not rendu.corrige_le:
            est_auteur = False  # la correction n'est visible qu'une fois rendue
        if not (est_prof or est_auteur):
            return None, False
        return photo, est_prof

    def get(self, request, pk):
        photo, _ = self._photo(request, pk)
        if photo is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        reponse = HttpResponse(bytes(photo.donnees), content_type=photo.type_mime)
        reponse["Cache-Control"] = "private, max-age=3600"
        reponse["X-Content-Type-Options"] = "nosniff"
        reponse["Content-Disposition"] = "inline"
        return reponse

    def delete(self, request, pk):
        photo, est_prof = self._photo(request, pk)
        if photo is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        rendu = photo.rendu
        if photo.cote == Photo.Cote.ELEVE and (est_prof or rendu.corrige_le or rendu.eleve_id != request.user.id):
            return Response({"detail": "Seul l'élève peut retirer sa photo, avant la correction."}, status=status.HTTP_403_FORBIDDEN)
        if photo.cote == Photo.Cote.CORRECTION and not est_prof:
            return Response(status=status.HTTP_404_NOT_FOUND)
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
