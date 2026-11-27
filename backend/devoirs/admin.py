from django.contrib import admin

from .models import Devoir, Rendu


@admin.register(Devoir)
class DevoirAdmin(admin.ModelAdmin):
    list_display = ["titre", "groupe", "eleve", "type", "date_limite", "cree_le"]
    list_filter = ["type", "groupe"]


@admin.register(Rendu)
class RenduAdmin(admin.ModelAdmin):
    list_display = ["devoir", "eleve", "rendu_le", "note", "corrige_le"]
    exclude = []
    readonly_fields = ["devoir", "eleve", "rendu_le"]
