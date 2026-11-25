from django.contrib import admin

from .models import AnneeScolaire, Groupe, Inscription, Organisation


class InscriptionEnLigne(admin.TabularInline):
    model = Inscription
    extra = 0
    fk_name = "groupe"
    raw_id_fields = ["utilisateur", "valide_par"]


@admin.register(Groupe)
class GroupeAdmin(admin.ModelAdmin):
    list_display = ["nom", "annee", "organisation", "cycle", "code_inscription", "inscriptions_ouvertes"]
    list_filter = ["annee", "organisation", "cycle"]
    readonly_fields = ["code_inscription"]
    inlines = [InscriptionEnLigne]


admin.site.register(Organisation)
admin.site.register(AnneeScolaire)
admin.site.register(Inscription)
