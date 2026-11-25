from django.contrib import admin

from .models import Etape, Matiere, Parcours, Partie, Rattachement, VersionParcours


@admin.register(VersionParcours)
class VersionAdmin(admin.ModelAdmin):
    list_display = ["parcours", "numero", "statut", "importee_le", "publiee_le"]
    list_filter = ["statut", "parcours"]
    readonly_fields = ["empreinte", "manifeste", "importee_par", "importee_le", "publiee_le"]


@admin.register(Rattachement)
class RattachementAdmin(admin.ModelAdmin):
    list_display = ["parcours", "groupe", "ordre", "ouverture"]
    list_filter = ["groupe", "ouverture"]


admin.site.register(Matiere)
admin.site.register(Parcours)
admin.site.register(Partie)
admin.site.register(Etape)
