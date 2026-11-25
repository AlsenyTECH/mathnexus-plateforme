from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.sessions.models import Session
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from organisations.acces import destination_apres_connexion, groupes_visibles
from organisations.models import Groupe, Inscription

from .models import JournalAudit, SessionAppareil, Utilisateur
from .permissions import EstAdmin
from .serializers import (
    ChangementMotDePasseSerializer,
    CompteEnAttenteSerializer,
    ConnexionSerializer,
    InscriptionSerializer,
    MoiSerializer,
)


def _reponse_session(utilisateur, code=status.HTTP_200_OK):
    return Response(
        {"utilisateur": MoiSerializer(utilisateur).data, "destination": destination_apres_connexion(utilisateur)},
        status=code,
    )


def _ouvrir_session(request, utilisateur):
    """Connecte le compte et garde au plus MAX_SESSIONS_PAR_COMPTE appareils actifs."""
    login(request, utilisateur, backend="django.contrib.auth.backends.ModelBackend")
    SessionAppareil.objects.create(
        utilisateur=utilisateur,
        cle_session=request.session.session_key,
        navigateur=request.META.get("HTTP_USER_AGENT", "")[:255],
    )
    en_trop = list(utilisateur.appareils.order_by("-cree_le")[settings.MAX_SESSIONS_PAR_COMPTE:])
    for appareil in en_trop:
        Session.objects.filter(session_key=appareil.cle_session).delete()
        appareil.delete()


@method_decorator(ensure_csrf_cookie, name="get")
class JetonCsrf(APIView):
    """À appeler au chargement de l'application : pose le cookie CSRF."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"ok": True})


@method_decorator(csrf_protect, name="post")
class Inscription_(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "inscription"

    def post(self, request):
        s = InscriptionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        groupe = d.get("code_classe")
        automatique = bool(groupe and groupe.validation_automatique)
        with transaction.atomic():
            utilisateur = Utilisateur.objects.create_user(
                telephone=d["telephone"],
                password=d["mot_de_passe"],
                prenom=d["prenom"].strip(),
                nom=d["nom"].strip(),
                email=d.get("email", ""),
                niveau_declare=d.get("niveau_declare", ""),
                etablissement_frequente=d.get("etablissement_frequente", ""),
                telephone_parent=d.get("telephone_parent", ""),
                cgu_acceptees_le=timezone.now(),
                statut=Utilisateur.Statut.ACTIF if automatique else Utilisateur.Statut.EN_ATTENTE,
            )
            if groupe:
                inscription = Inscription.objects.create(utilisateur=utilisateur, groupe=groupe)
                if automatique:
                    inscription.valider(par=None)
            JournalAudit.noter(request, "inscription", utilisateur.id, groupe=str(groupe.id) if groupe else None)
        _ouvrir_session(request, utilisateur)
        return _reponse_session(utilisateur, status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name="post")
class Connexion(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "connexion"

    def post(self, request):
        s = ConnexionSerializer(data=request.data)
        if not s.is_valid():
            return Response({"detail": "Identifiants incorrects."}, status=status.HTTP_400_BAD_REQUEST)
        utilisateur = authenticate(
            request, telephone=s.validated_data["telephone"], password=s.validated_data["mot_de_passe"]
        )
        if utilisateur is None:
            return Response({"detail": "Identifiants incorrects."}, status=status.HTTP_400_BAD_REQUEST)
        if not utilisateur.peut_utiliser:
            return Response({"detail": "Ce compte est suspendu. Contacte ton prof."}, status=status.HTTP_403_FORBIDDEN)
        _ouvrir_session(request, utilisateur)
        return _reponse_session(utilisateur)


class Deconnexion(APIView):
    def post(self, request):
        cle = request.session.session_key
        SessionAppareil.objects.filter(cle_session=cle).delete()
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class Moi(APIView):
    def get(self, request):
        return _reponse_session(request.user)


class ChangerMotDePasse(APIView):
    def post(self, request):
        s = ChangementMotDePasseSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        u = request.user
        u.set_password(s.validated_data["nouveau"])
        u.doit_changer_mot_de_passe = False
        u.save(update_fields=["password", "doit_changer_mot_de_passe"])
        update_session_auth_hash(request, u)
        # Les autres appareils sont déconnectés.
        autres = u.appareils.exclude(cle_session=request.session.session_key)
        Session.objects.filter(session_key__in=autres.values_list("cle_session", flat=True)).delete()
        autres.delete()
        SessionAppareil.objects.filter(utilisateur=u).update(cle_session=request.session.session_key)
        JournalAudit.noter(request, "mot_de_passe_change", u.id)
        return _reponse_session(u)


class GroupeCourant(APIView):
    """L'élève inscrit dans plusieurs groupes choisit celui où il travaille."""

    def post(self, request):
        groupe = get_object_or_404(groupes_visibles(request.user), id=request.data.get("groupe"))
        request.user.dernier_groupe = groupe
        request.user.save(update_fields=["dernier_groupe"])
        return _reponse_session(request.user)


# --- Administration des comptes ----------------------------------------------

class ComptesEnAttente(APIView):
    permission_classes = [EstAdmin]

    def get(self, request):
        comptes = Utilisateur.objects.filter(statut=Utilisateur.Statut.EN_ATTENTE).order_by("date_joined")
        return Response(CompteEnAttenteSerializer(comptes, many=True).data)


class ValiderCompte(APIView):
    """Valide un compte et ses demandes d'inscription.

    Sans code de classe, l'admin choisit le groupe dans `groupe`.
    """

    permission_classes = [EstAdmin]

    def post(self, request, pk):
        utilisateur = get_object_or_404(Utilisateur, pk=pk, statut=Utilisateur.Statut.EN_ATTENTE)
        groupe_id = request.data.get("groupe")
        with transaction.atomic():
            if groupe_id:
                groupe = get_object_or_404(Groupe, pk=groupe_id, archive=False)
                Inscription.objects.get_or_create(utilisateur=utilisateur, groupe=groupe)
            en_attente = list(utilisateur.inscriptions.filter(statut=Inscription.Statut.EN_ATTENTE))
            if not en_attente and not utilisateur.inscriptions.filter(statut=Inscription.Statut.VALIDEE).exists():
                return Response(
                    {"groupe": "Choisis la classe de cet élève avant de valider."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for inscription in en_attente:
                inscription.valider(par=request.user)
            utilisateur.statut = Utilisateur.Statut.ACTIF
            utilisateur.save(update_fields=["statut"])
            JournalAudit.noter(
                request, "compte_valide", utilisateur.id, groupes=[str(i.groupe_id) for i in en_attente]
            )
        return Response(MoiSerializer(utilisateur).data)


class RefuserCompte(APIView):
    """Un compte refusé est supprimé avec ses données."""

    permission_classes = [EstAdmin]

    def post(self, request, pk):
        utilisateur = get_object_or_404(Utilisateur, pk=pk, statut=Utilisateur.Statut.EN_ATTENTE)
        identifiant = utilisateur.id
        utilisateur.delete()
        JournalAudit.noter(request, "compte_refuse", identifiant)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SuspendreCompte(APIView):
    permission_classes = [EstAdmin]

    def post(self, request, pk):
        utilisateur = get_object_or_404(Utilisateur, pk=pk)
        if utilisateur.est_admin:
            return Response({"detail": "Impossible de suspendre un admin."}, status=status.HTTP_400_BAD_REQUEST)
        utilisateur.statut = Utilisateur.Statut.SUSPENDU
        utilisateur.save(update_fields=["statut"])
        cles = utilisateur.appareils.values_list("cle_session", flat=True)
        Session.objects.filter(session_key__in=list(cles)).delete()
        utilisateur.appareils.all().delete()
        JournalAudit.noter(request, "compte_suspendu", utilisateur.id, motif=request.data.get("motif", ""))
        return Response(MoiSerializer(utilisateur).data)


class ReactiverCompte(APIView):
    permission_classes = [EstAdmin]

    def post(self, request, pk):
        utilisateur = get_object_or_404(Utilisateur, pk=pk, statut=Utilisateur.Statut.SUSPENDU)
        utilisateur.statut = Utilisateur.Statut.ACTIF
        utilisateur.save(update_fields=["statut"])
        JournalAudit.noter(request, "compte_reactive", utilisateur.id)
        return Response(MoiSerializer(utilisateur).data)
