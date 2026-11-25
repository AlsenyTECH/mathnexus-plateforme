from django.contrib import admin

from .models import Progression


@admin.register(Progression)
class ProgressionAdmin(admin.ModelAdmin):
    list_display = ["utilisateur", "parcours", "cle_etape", "validee_le", "derniere_ouverture_le"]
    list_filter = ["parcours"]
