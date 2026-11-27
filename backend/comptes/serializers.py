from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from organisations.models import Groupe

from .models import Utilisateur
from .telephone import normaliser_telephone


def _telephone(valeur):
    try:
        return normaliser_telephone(valeur)
    except DjangoValidationError as e:
        raise serializers.ValidationError(e.messages)


class InscriptionSerializer(serializers.Serializer):
    """Le formulaire public d'inscription.

    Avec un code de classe valide, l'élève est rattaché au bon groupe ; sinon il choisit
    seulement son niveau, et c'est l'admin qui l'affecte en validant le compte.
    """

    prenom = serializers.CharField(max_length=80)
    nom = serializers.CharField(max_length=80)
    telephone = serializers.CharField(max_length=30)
    email = serializers.EmailField(required=False, allow_blank=True)
    mot_de_passe = serializers.CharField(write_only=True, trim_whitespace=False)
    niveau_declare = serializers.CharField(max_length=80, required=False, allow_blank=True)
    etablissement_frequente = serializers.CharField(max_length=150, required=False, allow_blank=True)
    est_mineur = serializers.BooleanField()
    telephone_parent = serializers.CharField(max_length=30, required=False, allow_blank=True)
    code_classe = serializers.CharField(max_length=24, required=False, allow_blank=True)
    accepte_conditions = serializers.BooleanField()

    def validate_telephone(self, valeur):
        tel = _telephone(valeur)
        if Utilisateur.objects.filter(telephone=tel).exists():
            raise serializers.ValidationError("Un compte existe déjà avec ce numéro.")
        return tel

    def validate_accepte_conditions(self, valeur):
        if not valeur:
            raise serializers.ValidationError("Il faut accepter les conditions d'utilisation.")
        return valeur

    def validate_code_classe(self, valeur):
        valeur = (valeur or "").strip().upper()
        if not valeur:
            return None
        groupe = Groupe.objects.filter(code_inscription=valeur, archive=False, inscriptions_ouvertes=True).first()
        if groupe is None:
            raise serializers.ValidationError("Code de classe inconnu ou fermé.")
        return groupe

    def validate(self, donnees):
        if donnees["est_mineur"]:
            if not donnees.get("telephone_parent"):
                raise serializers.ValidationError({"telephone_parent": "Obligatoire pour un élève mineur."})
            donnees["telephone_parent"] = _telephone(donnees["telephone_parent"])
        elif donnees.get("telephone_parent"):
            donnees["telephone_parent"] = _telephone(donnees["telephone_parent"])
        provisoire = Utilisateur(
            telephone=donnees["telephone"], prenom=donnees["prenom"], nom=donnees["nom"],
            email=donnees.get("email", ""),
        )
        try:
            password_validation.validate_password(donnees["mot_de_passe"], provisoire)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"mot_de_passe": e.messages})
        return donnees


class ConnexionSerializer(serializers.Serializer):
    telephone = serializers.CharField(max_length=30)
    mot_de_passe = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_telephone(self, valeur):
        try:
            return normaliser_telephone(valeur)
        except DjangoValidationError:
            # Même message qu'un mauvais mot de passe : on ne révèle pas si le compte existe.
            raise serializers.ValidationError("Identifiants incorrects.")


class ChangementMotDePasseSerializer(serializers.Serializer):
    actuel = serializers.CharField(write_only=True, trim_whitespace=False)
    nouveau = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, donnees):
        utilisateur = self.context["request"].user
        if not utilisateur.check_password(donnees["actuel"]):
            raise serializers.ValidationError({"actuel": "Mot de passe actuel incorrect."})
        try:
            password_validation.validate_password(donnees["nouveau"], utilisateur)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"nouveau": e.messages})
        return donnees


class MoiSerializer(serializers.ModelSerializer):
    classes_eleve = serializers.SerializerMethodField()
    enseigne = serializers.SerializerMethodField()

    class Meta:
        model = Utilisateur
        fields = [
            "id", "prenom", "nom", "telephone", "email", "statut", "doit_changer_mot_de_passe", "est_admin",
            "classes_eleve", "enseigne",
        ]
        read_only_fields = fields

    def get_classes_eleve(self, u):
        """Les classes où le compte travaille comme élève : sert au bouton « Espace élève »."""
        from devoirs.regles import groupes_comme_eleve

        return [{"id": str(g.id), "nom": g.nom} for g in groupes_comme_eleve(u)]

    def get_enseigne(self, u):
        from organisations.acces import groupes_enseignes

        return u.est_admin or groupes_enseignes(u).exists()


class CompteEnAttenteSerializer(serializers.ModelSerializer):
    demandes = serializers.SerializerMethodField()

    class Meta:
        model = Utilisateur
        fields = [
            "id", "prenom", "nom", "telephone", "email", "niveau_declare",
            "etablissement_frequente", "telephone_parent", "date_joined", "demandes",
        ]

    def get_demandes(self, obj):
        return [
            {"inscription": str(i.id), "groupe": str(i.groupe_id), "groupe_nom": str(i.groupe)}
            for i in obj.inscriptions.filter(statut="en_attente").select_related("groupe__annee")
        ]
