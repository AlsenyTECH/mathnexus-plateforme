"""Les évaluations (format 2 des paquets) et les tentatives des élèves.

Deux familles de tables :

- Evaluation et Question : le contenu, importé avec une version de parcours. Les bonnes
  réponses (`Question.bonnes`) ne quittent le serveur qu'avec la correction d'une tentative
  terminée.
- Tentative et Reponse : ce que fait l'élève. Une tentative est accrochée à la clé stable de
  l'évaluation (pour suivre un élève d'une version à l'autre) et à l'évaluation de la version
  qu'il a passée (pour corriger avec les bonnes questions). Chaque réponse garde le temps passé
  sur la question.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Evaluation(models.Model):
    class Role(models.TextChoices):
        ENTREE = "entree", "Test d'entrée"
        SORTIE = "sortie", "Test de sortie"
        EVALUATION = "evaluation", "Évaluation"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey("contenus.VersionParcours", on_delete=models.CASCADE, related_name="evaluations")
    etape = models.ForeignKey("contenus.Etape", on_delete=models.CASCADE, related_name="evaluations")
    cle = models.CharField(max_length=60, help_text="Stable d'une version à l'autre")
    titre = models.CharField(max_length=200)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.EVALUATION)
    consigne = models.TextField(blank=True)
    duree_min = models.PositiveIntegerField("durée (min)", null=True, blank=True, help_text="Vide : pas de chronomètre")
    seuil = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=7, decimal_places=2)

    class Meta:
        ordering = ["version", "etape__ordre", "cle"]
        verbose_name = "évaluation"
        constraints = [models.UniqueConstraint(fields=["version", "cle"], name="evaluation_unique_par_version")]

    def __str__(self):
        return f"{self.titre} ({self.cle})"


class Question(models.Model):
    class Type(models.TextChoices):
        CHOIX_UNIQUE = "choix_unique", "Choix unique"
        CHOIX_MULTIPLE = "choix_multiple", "Choix multiple"

    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name="questions")
    cle = models.CharField(max_length=60)
    ordre = models.PositiveIntegerField()
    type = models.CharField(max_length=14, choices=Type.choices, default=Type.CHOIX_UNIQUE)
    enonce = models.TextField("énoncé")
    choix = models.JSONField(help_text="Liste de morceaux de HTML")
    bonnes = models.JSONField(help_text="Indices des bonnes réponses (à partir de 0) : jamais envoyés avant la fin")
    points = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    explication = models.TextField(blank=True)

    class Meta:
        ordering = ["evaluation", "ordre"]
        constraints = [models.UniqueConstraint(fields=["evaluation", "cle"], name="question_unique_par_evaluation")]

    def __str__(self):
        return f"{self.evaluation.cle} · {self.cle}"

    def est_juste(self, choix):
        """Tout ou rien : la réponse doit désigner exactement les bonnes réponses."""
        return choix is not None and sorted(set(choix)) == sorted(self.bonnes)


class Tentative(models.Model):
    class Fin(models.TextChoices):
        TERMINEE = "terminee", "Terminée par l'élève"
        TEMPS_ECOULE = "temps_ecoule", "Temps écoulé"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tentatives")
    groupe = models.ForeignKey("organisations.Groupe", on_delete=models.CASCADE, related_name="tentatives")
    parcours = models.ForeignKey("contenus.Parcours", on_delete=models.CASCADE, related_name="tentatives")
    cle_evaluation = models.CharField("clé de l'évaluation", max_length=60)
    # PROTECT : on ne peut pas supprimer une version dont des élèves ont passé les évaluations.
    evaluation = models.ForeignKey(Evaluation, on_delete=models.PROTECT, related_name="tentatives")
    commencee_le = models.DateTimeField("commencée le", default=timezone.now)
    echeance = models.DateTimeField("échéance", null=True, blank=True, help_text="Vide : pas de chronomètre")
    terminee_le = models.DateTimeField("terminée le", null=True, blank=True)
    fin = models.CharField(max_length=12, choices=Fin.choices, blank=True)
    score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=7, decimal_places=2)
    reussie = models.BooleanField("réussie", null=True, blank=True, help_text="Vide : pas de seuil, ou pas terminée")

    class Meta:
        ordering = ["-commencee_le"]
        indexes = [models.Index(fields=["utilisateur", "parcours", "cle_evaluation"])]

    def __str__(self):
        return f"{self.utilisateur} · {self.cle_evaluation} · {self.commencee_le:%d/%m/%Y %H:%M}"

    @property
    def terminee(self):
        return self.terminee_le is not None


class Reponse(models.Model):
    """La réponse à une question dans une tentative, et le temps passé dessus.

    `temps_ms` est le temps actif mesuré par le navigateur (question affichée, onglet visible),
    plafonné par le serveur : la somme sur une tentative ne dépasse jamais le temps réellement
    écoulé depuis le début. Les deux dates sont celles du serveur.
    """

    tentative = models.ForeignKey(Tentative, on_delete=models.CASCADE, related_name="reponses")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="reponses")
    choix = models.JSONField(null=True, blank=True, help_text="Indices choisis ; vide : question vue sans réponse")
    temps_ms = models.PositiveIntegerField("temps (ms)", default=0)
    modifications = models.PositiveIntegerField(default=0, help_text="Nombre de fois où la réponse a changé")
    premiere_reponse_le = models.DateTimeField("première réponse le", null=True, blank=True)
    derniere_reponse_le = models.DateTimeField("dernière réponse le", null=True, blank=True)
    juste = models.BooleanField(null=True, blank=True, help_text="Rempli à la fin de la tentative")
    points = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["tentative", "question__ordre"]
        verbose_name = "réponse"
        constraints = [models.UniqueConstraint(fields=["tentative", "question"], name="reponse_unique_par_question")]

    def __str__(self):
        return f"{self.tentative_id} · {self.question.cle}"
