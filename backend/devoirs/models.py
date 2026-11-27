"""Donner du travail et corriger.

- Un Devoir est donné par le prof à toute une classe ou à un seul élève : une étape à faire,
  une évaluation à passer, ou un travail libre (exercices sur papier, rédaction…), avec une
  date limite. Plusieurs devoirs par jour sont possibles (évaluations quotidiennes).
- Un Rendu est la réponse d'un élève : un texte et des photos de sa copie. Le prof le corrige
  (note, commentaire, correction rédigée, photos annotées) ; l'élève voit alors sa correction.
- Une évaluation donnée en devoir se corrige toute seule (score de la tentative) ; le prof peut
  quand même ajouter un commentaire.

Les photos sont gardées dans la base (petites images compressées par le navigateur) : c'est le
plus simple tant que la plateforme n'a pas de stockage de fichiers. Elles passeront dans un
stockage d'objets avec le serveur.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Devoir(models.Model):
    class Type(models.TextChoices):
        ETAPE = "etape", "Étape d'un parcours"
        EVALUATION = "evaluation", "Évaluation"
        LIBRE = "libre", "Travail libre"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    groupe = models.ForeignKey("organisations.Groupe", on_delete=models.CASCADE, related_name="devoirs")
    eleve = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="devoirs_personnels",
        help_text="Vide : toute la classe.",
    )
    type = models.CharField(max_length=12, choices=Type.choices, default=Type.LIBRE)
    titre = models.CharField(max_length=200)
    consigne = models.TextField(blank=True)
    parcours = models.ForeignKey("contenus.Parcours", null=True, blank=True, on_delete=models.CASCADE, related_name="devoirs")
    cle_etape = models.CharField(max_length=60, blank=True)
    cle_evaluation = models.CharField(max_length=60, blank=True)
    date_limite = models.DateTimeField(null=True, blank=True)
    note_sur = models.DecimalField(max_digits=6, decimal_places=2, default=20)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    cree_le = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-cree_le"]

    def __str__(self):
        return f"{self.titre} ({self.groupe})"

    def en_retard(self, maintenant=None):
        return bool(self.date_limite and (maintenant or timezone.now()) > self.date_limite)


class Rendu(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    devoir = models.ForeignKey(Devoir, on_delete=models.CASCADE, related_name="rendus")
    eleve = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rendus")
    texte = models.TextField(blank=True)
    rendu_le = models.DateTimeField(null=True, blank=True, help_text="Vide : brouillon pas encore envoyé")
    note = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    commentaire = models.TextField(blank=True)
    correction = models.TextField(blank=True)
    corrige_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    corrige_le = models.DateTimeField(null=True, blank=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["devoir", "eleve"]
        constraints = [models.UniqueConstraint(fields=["devoir", "eleve"], name="un_rendu_par_eleve")]

    def __str__(self):
        return f"{self.eleve} · {self.devoir}"


class Photo(models.Model):
    class Cote(models.TextChoices):
        ELEVE = "eleve", "Copie de l'élève"
        CORRECTION = "correction", "Correction du prof"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rendu = models.ForeignKey(Rendu, on_delete=models.CASCADE, related_name="photos")
    cote = models.CharField(max_length=12, choices=Cote.choices, default=Cote.ELEVE)
    type_mime = models.CharField(max_length=20)
    taille = models.PositiveIntegerField()
    donnees = models.BinaryField()
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["cree_le"]
