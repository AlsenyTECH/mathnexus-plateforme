import secrets

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.models import JournalAudit, Utilisateur
from comptes.permissions import EstAdmin

from .acces import groupes_enseignes, groupes_visibles
from .models import Groupe, Inscription
from .serializers import GroupeAdminSerializer, GroupeSerializer, ImportSerializer, MembreSerializer

_ALPHABET_MDP = "abcdefghjkmnpqrstuvwxyz23456789"


def mot_de_passe_provisoire(longueur=10):
    return "".join(secrets.choice(_ALPHABET_MDP) for _ in range(longueur))


# --- Côté élève et prof --------------------------------------------------------

class MesGroupes(generics.ListAPIView):
    serializer_class = GroupeSerializer
    pagination_class = None

    def get_queryset(self):
        return groupes_visibles(self.request.user).select_related("organisation", "annee")


class DetailGroupe(generics.RetrieveAPIView):
    """Un groupe hors du périmètre répond 404, pas 403 : on ne révèle pas qu'il existe."""

    serializer_class = GroupeSerializer

    def get_queryset(self):
        return groupes_visibles(self.request.user).select_related("organisation", "annee")


class MembresGroupe(APIView):
    """La liste des élèves d'un groupe : réservée à ses profs et à l'admin."""

    def get(self, request, pk):
        groupe = get_object_or_404(groupes_enseignes(request.user), pk=pk)
        membres = groupe.inscriptions.filter(statut=Inscription.Statut.VALIDEE).select_related("utilisateur")
        return Response(MembreSerializer(membres, many=True).data)


# --- Côté admin ----------------------------------------------------------------

class GroupesAdmin(generics.ListCreateAPIView):
    permission_classes = [EstAdmin]
    serializer_class = GroupeAdminSerializer
    pagination_class = None
    queryset = Groupe.objects.select_related("organisation", "annee").all()

    def perform_create(self, serializer):
        groupe = serializer.save()
        JournalAudit.noter(self.request, "groupe_cree", groupe.id, nom=groupe.nom)


class GroupeAdmin(generics.RetrieveUpdateAPIView):
    permission_classes = [EstAdmin]
    serializer_class = GroupeAdminSerializer
    queryset = Groupe.objects.all()


class RegenererCode(APIView):
    """À utiliser si un code de classe a circulé hors de la classe."""

    permission_classes = [EstAdmin]

    def post(self, request, pk):
        groupe = get_object_or_404(Groupe, pk=pk)
        groupe.regenerer_code()
        JournalAudit.noter(request, "code_regenere", groupe.id)
        return Response({"code_inscription": groupe.code_inscription})


class ImporterEleves(APIView):
    """Crée en une fois les comptes d'une liste de classe.

    Les comptes sont actifs et rattachés au groupe ; chacun reçoit un mot de passe
    provisoire, renvoyé UNE SEULE FOIS dans la réponse, à changer à la première connexion.
    Un numéro qui a déjà un compte est simplement rattaché au groupe.
    """

    permission_classes = [EstAdmin]

    def post(self, request, pk):
        groupe = get_object_or_404(Groupe, pk=pk, archive=False)
        s = ImportSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        resultats = []
        with transaction.atomic():
            for ligne in s.validated_data["eleves"]:
                existant = Utilisateur.objects.filter(telephone=ligne["telephone"]).first()
                if existant:
                    inscription, _ = Inscription.objects.get_or_create(utilisateur=existant, groupe=groupe)
                    if inscription.statut != Inscription.Statut.VALIDEE:
                        inscription.valider(par=request.user)
                    if existant.statut == Utilisateur.Statut.EN_ATTENTE:
                        # L'admin a mis cet élève sur sa liste : cela vaut validation du compte.
                        existant.statut = Utilisateur.Statut.ACTIF
                        existant.save(update_fields=["statut"])
                    resultats.append({"telephone": existant.telephone, "etat": "rattache"})
                    continue
                mdp = mot_de_passe_provisoire()
                compte = Utilisateur.objects.create_user(
                    telephone=ligne["telephone"], password=mdp, prenom=ligne["prenom"], nom=ligne["nom"],
                    statut=Utilisateur.Statut.ACTIF, doit_changer_mot_de_passe=True,
                )
                Inscription.objects.create(utilisateur=compte, groupe=groupe).valider(par=request.user)
                resultats.append({"telephone": compte.telephone, "etat": "cree", "mot_de_passe_provisoire": mdp})
            JournalAudit.noter(request, "import_eleves", groupe.id, nombre=len(resultats))
        return Response({"resultats": resultats}, status=status.HTTP_201_CREATED)


class AjouterProf(APIView):
    permission_classes = [EstAdmin]

    def post(self, request, pk):
        groupe = get_object_or_404(Groupe, pk=pk, archive=False)
        prof = get_object_or_404(Utilisateur, pk=request.data.get("utilisateur"), statut=Utilisateur.Statut.ACTIF)
        inscription, _ = Inscription.objects.update_or_create(
            utilisateur=prof, groupe=groupe, defaults={"role": Inscription.Role.PROF}
        )
        inscription.valider(par=request.user)
        JournalAudit.noter(request, "prof_ajoute", groupe.id, prof=str(prof.id))
        return Response(MembreSerializer(inscription).data, status=status.HTTP_201_CREATED)
