"""Dans l'admin Django : les évaluations importées et les tentatives, avec le temps par question.

Tout est en lecture seule : une évaluation vient d'un paquet, une tentative vient d'un élève.
"""
from django.contrib import admin

from .models import Evaluation, Question, Reponse, Tentative


class LectureSeule:
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class QuestionEnLigne(LectureSeule, admin.TabularInline):
    model = Question
    fields = ["ordre", "cle", "type", "points", "bonnes"]
    readonly_fields = fields


@admin.register(Evaluation)
class EvaluationAdmin(LectureSeule, admin.ModelAdmin):
    list_display = ["cle", "titre", "role", "duree_min", "total", "seuil", "version"]
    list_filter = ["role", "version__parcours"]
    inlines = [QuestionEnLigne]


class ReponseEnLigne(LectureSeule, admin.TabularInline):
    model = Reponse
    fields = ["question", "choix", "juste", "points", "secondes", "modifications", "premiere_reponse_le",
              "derniere_reponse_le"]
    readonly_fields = fields

    @admin.display(description="temps (s)")
    def secondes(self, reponse):
        return f"{reponse.temps_ms / 1000:.1f}"


@admin.register(Tentative)
class TentativeAdmin(LectureSeule, admin.ModelAdmin):
    list_display = ["utilisateur", "cle_evaluation", "commencee_le", "terminee_le", "fin", "score", "total",
                    "reussie", "temps_total"]
    list_filter = ["parcours", "cle_evaluation", "fin", "groupe"]
    inlines = [ReponseEnLigne]

    @admin.display(description="temps total (s)")
    def temps_total(self, tentative):
        return f"{sum(r.temps_ms for r in tentative.reponses.all()) / 1000:.1f}"
