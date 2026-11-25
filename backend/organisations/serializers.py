from rest_framework import serializers

from comptes.telephone import normaliser_telephone

from .models import AnneeScolaire, Groupe, Inscription, Organisation


class GroupeSerializer(serializers.ModelSerializer):
    organisation_nom = serializers.CharField(source="organisation.nom", read_only=True)
    annee_libelle = serializers.CharField(source="annee.libelle", read_only=True)
    mon_role = serializers.SerializerMethodField()

    class Meta:
        model = Groupe
        fields = ["id", "nom", "cycle", "organisation", "organisation_nom", "annee", "annee_libelle", "mon_role"]
        read_only_fields = fields

    def get_mon_role(self, groupe):
        request = self.context.get("request")
        if not request:
            return None
        if request.user.est_admin:
            return "admin"
        inscription = groupe.inscriptions.filter(utilisateur=request.user, statut="validee").first()
        return inscription.role if inscription else None


class GroupeAdminSerializer(serializers.ModelSerializer):
    """Ce que l'admin voit et règle sur un groupe, code d'inscription compris."""

    organisation = serializers.PrimaryKeyRelatedField(queryset=Organisation.objects.all())
    annee = serializers.PrimaryKeyRelatedField(queryset=AnneeScolaire.objects.all())
    effectif = serializers.SerializerMethodField()

    class Meta:
        model = Groupe
        fields = [
            "id", "nom", "cycle", "organisation", "annee", "code_inscription",
            "inscriptions_ouvertes", "validation_automatique", "archive", "effectif",
        ]
        read_only_fields = ["id", "code_inscription", "effectif"]

    def get_effectif(self, groupe):
        return groupe.inscriptions.filter(role="eleve", statut="validee").count()


class MembreSerializer(serializers.ModelSerializer):
    prenom = serializers.CharField(source="utilisateur.prenom")
    nom = serializers.CharField(source="utilisateur.nom")
    utilisateur = serializers.UUIDField(source="utilisateur.id")

    class Meta:
        model = Inscription
        fields = ["utilisateur", "prenom", "nom", "role", "valide_le"]


class LigneImportSerializer(serializers.Serializer):
    prenom = serializers.CharField(max_length=80)
    nom = serializers.CharField(max_length=80)
    telephone = serializers.CharField(max_length=30)

    def validate_telephone(self, valeur):
        from django.core.exceptions import ValidationError

        try:
            return normaliser_telephone(valeur)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)


class ImportSerializer(serializers.Serializer):
    eleves = LigneImportSerializer(many=True, allow_empty=False)
