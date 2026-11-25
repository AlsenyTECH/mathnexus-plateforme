from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import JournalAudit, SessionAppareil, Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    ordering = ["nom", "prenom"]
    list_display = ["prenom", "nom", "telephone", "statut", "date_joined"]
    list_filter = ["statut", "is_staff"]
    search_fields = ["prenom", "nom", "telephone", "email"]
    fieldsets = [
        (None, {"fields": ["telephone", "password"]}),
        ("Identité", {"fields": ["prenom", "nom", "email", "etablissement_frequente", "niveau_declare", "telephone_parent"]}),
        ("Compte", {"fields": ["statut", "doit_changer_mot_de_passe", "cgu_acceptees_le", "dernier_groupe"]}),
        ("Droits", {"fields": ["is_active", "is_staff", "is_superuser", "groups", "user_permissions"]}),
    ]
    add_fieldsets = [(None, {"classes": ["wide"], "fields": ["telephone", "prenom", "nom", "password1", "password2"]})]


@admin.register(JournalAudit)
class JournalAuditAdmin(admin.ModelAdmin):
    list_display = ["cree_le", "acteur", "action", "cible"]
    list_filter = ["action"]

    def has_change_permission(self, request, obj=None):
        return False  # le journal ne se modifie pas

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(SessionAppareil)
