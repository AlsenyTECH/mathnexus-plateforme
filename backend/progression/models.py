"""Ce que chaque élève a fait, étape par étape.

La progression est accrochée au parcours et à la clé stable de l'étape, pas à une version :
une nouvelle version publiée ne fait rien perdre aux élèves.
"""
from django.conf import settings
from django.db import models


class Progression(models.Model):
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="progressions")
    parcours = models.ForeignKey("contenus.Parcours", on_delete=models.CASCADE, related_name="progressions")
    cle_etape = models.CharField(max_length=60)
    premiere_ouverture_le = models.DateTimeField(auto_now_add=True)
    derniere_ouverture_le = models.DateTimeField(auto_now=True)
    validee_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["utilisateur", "parcours", "cle_etape"], name="progression_unique"),
        ]
        indexes = [models.Index(fields=["parcours", "cle_etape"])]

    def __str__(self):
        etat = "validée" if self.validee_le else "ouverte"
        return f"{self.utilisateur} · {self.parcours} · {self.cle_etape} ({etat})"
