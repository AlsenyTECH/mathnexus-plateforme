from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.models import JournalAudit
from comptes.permissions import EstAdmin
from organisations.acces import groupes_enseignes, groupes_visibles
from organisations.models import Groupe
from progression.models import Progression

from .acces import est_prof_ou_admin, etat_etape, rattachements_lisibles
from .importation import PaquetDejaImporte, importer_paquet
from .models import Etape, EtapeOuverte, Parcours, Rattachement, VersionParcours
from .paquet import PaquetInvalide
from .permissions import EstAdminOuCleDeploiement

# --- Administration des contenus ----------------------------------------------------


def _resume_version(v):
    return {
        "id": str(v.id), "parcours": v.parcours.slug, "numero": v.numero, "statut": v.statut,
        "importee_le": v.importee_le, "publiee_le": v.publiee_le,
        "nombre_etapes": v.etapes.count(),
    }


class ImporterPaquet(APIView):
    """Reçoit un paquet du moteur (clé de déploiement) ou de l'admin, et crée une version en brouillon."""

    permission_classes = [EstAdminOuCleDeploiement]

    def post(self, request):
        fichier = request.FILES.get("paquet")
        if fichier is None:
            return Response({"paquet": "Fichier « paquet » manquant."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            version = importer_paquet(fichier.read(), par=request.user)
        except PaquetInvalide as e:
            return Response({"detail": "Paquet refusé.", "problemes": e.problemes}, status=status.HTTP_400_BAD_REQUEST)
        except PaquetDejaImporte as e:
            return Response({"detail": str(e), "version": _resume_version(e.version)}, status=status.HTTP_409_CONFLICT)
        JournalAudit.noter(
            request, "paquet_importe", version.id, parcours=version.parcours.slug, numero=version.numero,
            source="admin" if request.user.is_authenticated else "cle_deploiement",
        )
        return Response(_resume_version(version), status=status.HTTP_201_CREATED)


class ParcoursAdmin(APIView):
    permission_classes = [EstAdmin]

    def get(self, request):
        return Response([
            {
                "slug": p.slug, "titre": p.titre, "matiere": p.matiere.nom, "cycle": p.cycle,
                "versions": [_resume_version(v) for v in p.versions.all()],
                "groupes": [str(r.groupe_id) for r in p.rattachements.all()],
            }
            for p in Parcours.objects.select_related("matiere").prefetch_related("versions", "rattachements")
        ])


class VersionAdmin(APIView):
    """Aperçu d'une version (brouillon compris) : sa structure, sans le HTML."""

    permission_classes = [EstAdmin]

    def get(self, request, pk):
        v = get_object_or_404(VersionParcours.objects.select_related("parcours"), pk=pk)
        donnees = _resume_version(v)
        donnees["parties"] = [
            {"cle": p.cle, "titre": p.titre,
             "etapes": [{"cle": e.cle, "titre": e.titre, "acces": e.acces, "duree_min": e.duree_min} for e in p.etapes.all()]}
            for p in v.parties.prefetch_related("etapes")
        ]
        return Response(donnees)


class EtapeVersionAdmin(APIView):
    """Lire une étape d'une version, même en brouillon : l'aperçu « comme un élève »."""

    permission_classes = [EstAdmin]

    def get(self, request, pk, cle):
        e = get_object_or_404(Etape, version_id=pk, cle=cle)
        return Response({"cle": e.cle, "titre": e.titre, "acces": e.acces, "html": e.html})


class PublierVersion(APIView):
    permission_classes = [EstAdmin]

    def post(self, request, pk):
        with transaction.atomic():
            v = get_object_or_404(VersionParcours.objects.select_for_update(), pk=pk)
            if v.statut == VersionParcours.Statut.PUBLIEE:
                return Response({"detail": "Cette version est déjà publiée."}, status=status.HTTP_400_BAD_REQUEST)
            v.publier()
        JournalAudit.noter(request, "version_publiee", v.id, parcours=v.parcours.slug, numero=v.numero)
        return Response(_resume_version(v))


class RattacherParcours(APIView):
    """Rend un parcours disponible dans un groupe, ou change son ordre et son mode d'ouverture."""

    permission_classes = [EstAdmin]

    def post(self, request, pk):
        groupe = get_object_or_404(Groupe, pk=pk, archive=False)
        parcours = get_object_or_404(Parcours, slug=request.data.get("parcours"))
        ouverture = request.data.get("ouverture", Rattachement.Ouverture.TOUT)
        if ouverture not in Rattachement.Ouverture.values:
            return Response({"ouverture": "Valeur invalide."}, status=status.HTTP_400_BAD_REQUEST)
        r, cree = Rattachement.objects.update_or_create(
            groupe=groupe, parcours=parcours,
            defaults={"ordre": int(request.data.get("ordre", 0)), "ouverture": ouverture},
        )
        JournalAudit.noter(request, "parcours_rattache", groupe.id, parcours=parcours.slug, ouverture=ouverture)
        return Response(
            {"id": str(r.id), "parcours": parcours.slug, "ordre": r.ordre, "ouverture": r.ouverture},
            status=status.HTTP_201_CREATED if cree else status.HTTP_200_OK,
        )


class DetacherParcours(APIView):
    """Retire un parcours d'un groupe. La progression des élèves est conservée."""

    permission_classes = [EstAdmin]

    def delete(self, request, pk, slug):
        r = get_object_or_404(Rattachement, groupe_id=pk, parcours__slug=slug)
        r.delete()
        JournalAudit.noter(request, "parcours_detache", pk, parcours=slug)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Côté élève et prof --------------------------------------------------------------


def _contexte(request, groupe_id, slug):
    """Groupe visible, rattachement lisible et version publiée, ou 404."""
    groupe = get_object_or_404(groupes_visibles(request.user), pk=groupe_id)
    rattachement = get_object_or_404(rattachements_lisibles(request.user, groupe), parcours__slug=slug)
    version = rattachement.parcours.version_publiee()
    return groupe, rattachement, version


def _sommaire(request, groupe, rattachement, version):
    privilegie = est_prof_ou_admin(request.user, groupe)
    cles_ouvertes = rattachement.cles_ouvertes()
    validees = set(
        Progression.objects.filter(
            utilisateur=request.user, parcours=rattachement.parcours, validee_le__isnull=False
        ).values_list("cle_etape", flat=True)
    )
    parties, total, faites = [], 0, 0
    for partie in version.parties.prefetch_related("etapes"):
        etapes = []
        for e in partie.etapes.all():
            ouverte, accessible, raison = etat_etape(
                request.user, groupe, rattachement, e, privilegie=privilegie, cles_ouvertes=cles_ouvertes
            )
            total += 1
            faites += e.cle in validees
            etapes.append({
                "cle": e.cle, "titre": e.titre, "duree_min": e.duree_min, "acces": e.acces,
                "ouverte": ouverte, "accessible": accessible, "raison": raison, "validee": e.cle in validees,
                # Ce que voient les élèves (le prof, lui, voit tout ouvert).
                "ouverte_eleves": rattachement.ouverture == Rattachement.Ouverture.TOUT or e.cle in cles_ouvertes,
            })
        parties.append({"cle": partie.cle, "titre": partie.titre, "etapes": etapes})
    p = rattachement.parcours
    return {
        "slug": p.slug, "titre": p.titre, "matiere": p.matiere.nom, "description": p.description,
        "ouverture": rattachement.ouverture, "version": version.numero,
        "avancement": {"validees": faites, "total": total}, "parties": parties,
    }


class ParcoursDuGroupe(APIView):
    def get(self, request, pk):
        groupe = get_object_or_404(groupes_visibles(request.user), pk=pk)
        resultat = []
        for r in rattachements_lisibles(request.user, groupe):
            s = _sommaire(request, groupe, r, r.parcours.version_publiee())
            s.pop("parties")
            resultat.append(s)
        return Response(resultat)


class SommaireParcours(APIView):
    def get(self, request, pk, slug):
        groupe, rattachement, version = _contexte(request, pk, slug)
        return Response(_sommaire(request, groupe, rattachement, version))


class LireEtape(APIView):
    def get(self, request, pk, slug, cle):
        groupe, rattachement, version = _contexte(request, pk, slug)
        etape = get_object_or_404(version.etapes.select_related("partie"), cle=cle)
        privilegie = est_prof_ou_admin(request.user, groupe)
        _, accessible, raison = etat_etape(request.user, groupe, rattachement, etape, privilegie=privilegie)
        if not accessible:
            messages = {
                "pas_encore_ouverte": "Cette étape n'est pas encore ouverte par ton prof.",
                "premium": "Cette étape fait partie de l'offre Premium.",
            }
            return Response({"detail": messages[raison], "raison": raison}, status=status.HTTP_403_FORBIDDEN)

        validee = False
        if not privilegie:
            prog, _ = Progression.objects.get_or_create(
                utilisateur=request.user, parcours=rattachement.parcours, cle_etape=etape.cle
            )
            prog.save(update_fields=["derniere_ouverture_le"])
            validee = prog.validee_le is not None
            if request.user.dernier_groupe_id != groupe.id:
                request.user.dernier_groupe = groupe
                request.user.save(update_fields=["dernier_groupe"])

        cles = list(version.etapes.values_list("cle", flat=True))
        i = cles.index(etape.cle)
        return Response({
            "cle": etape.cle, "titre": etape.titre, "partie": etape.partie.titre,
            "duree_min": etape.duree_min, "acces": etape.acces, "html": etape.html, "validee": validee,
            "precedente": cles[i - 1] if i > 0 else None,
            "suivante": cles[i + 1] if i + 1 < len(cles) else None,
        })


class OuvrirEtapes(APIView):
    """En ouverture progressive, le prof ouvre (ou referme) des étapes pour son groupe."""

    def post(self, request, pk, slug):
        groupe = get_object_or_404(groupes_enseignes(request.user), pk=pk)
        rattachement = get_object_or_404(Rattachement, groupe=groupe, parcours__slug=slug)
        version = rattachement.parcours.version_publiee()
        cles = request.data.get("etapes") or []
        if not isinstance(cles, list) or not cles:
            return Response({"etapes": "Liste de clés d'étapes attendue."}, status=status.HTTP_400_BAD_REQUEST)
        connues = set(version.etapes.values_list("cle", flat=True)) if version else set()
        inconnues = [c for c in cles if c not in connues]
        if inconnues:
            return Response({"etapes": f"Étapes inconnues : {', '.join(map(str, inconnues))}"}, status=status.HTTP_400_BAD_REQUEST)
        if request.data.get("ouvrir", True):
            for cle in cles:
                EtapeOuverte.objects.get_or_create(
                    rattachement=rattachement, cle_etape=cle, defaults={"ouverte_par": request.user}
                )
        else:
            rattachement.ouvertures.filter(cle_etape__in=cles).delete()
        return Response({"ouvertes": sorted(rattachement.cles_ouvertes())})


class EtapePublique(APIView):
    """La vitrine : les étapes marquées « public » se lisent sans compte."""

    permission_classes = [AllowAny]

    def get(self, request, slug, cle):
        etape = get_object_or_404(
            Etape.objects.select_related("version__parcours"),
            version__parcours__slug=slug, version__statut="publiee", cle=cle, acces=Etape.Acces.PUBLIC,
        )
        return Response({
            "parcours": etape.version.parcours.titre, "cle": etape.cle, "titre": etape.titre, "html": etape.html,
        })
