"""Le catalogue des contenus : parcours, versions, parties, étapes, et leur rattachement aux groupes.

Un parcours existe une seule fois ; on le partage en le rattachant à des groupes.
Chaque import du moteur crée une version ; une seule version est publiée à la fois.
Les étapes sont repérées par une clé stable d'une version à l'autre : la progression des
élèves s'y accroche, elle survit donc aux nouvelles versions.
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Matiere(models.Model):
    nom = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "matière"

    def __str__(self):
        return self.nom


class Parcours(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=60, unique=True)
    titre = models.CharField(max_length=200)
    matiere = models.ForeignKey(Matiere, on_delete=models.PROTECT, related_name="parcours")
    cycle = models.CharField(max_length=12)
    description = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["titre"]
        verbose_name_plural = "parcours"

    def __str__(self):
        return self.titre

    def version_publiee(self):
        return self.versions.filter(statut=VersionParcours.Statut.PUBLIEE).first()


class VersionParcours(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = "brouillon", "Brouillon"
        PUBLIEE = "publiee", "Publiée"
        ARCHIVEE = "archivee", "Archivée"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parcours = models.ForeignKey(Parcours, on_delete=models.CASCADE, related_name="versions")
    numero = models.PositiveIntegerField()
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.BROUILLON)
    empreinte = models.CharField(max_length=64, help_text="SHA-256 du paquet importé")
    manifeste = models.JSONField()
    importee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    importee_le = models.DateTimeField(auto_now_add=True)
    publiee_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["parcours", "-numero"]
        verbose_name = "version de parcours"
        constraints = [
            models.UniqueConstraint(fields=["parcours", "numero"], name="numero_unique_par_parcours"),
            models.UniqueConstraint(
                fields=["parcours"], condition=Q(statut="publiee"), name="une_seule_version_publiee"
            ),
        ]

    def __str__(self):
        return f"{self.parcours} v{self.numero} ({self.get_statut_display()})"

    def publier(self):
        maintenant = timezone.now()
        self.parcours.versions.filter(statut=self.Statut.PUBLIEE).exclude(pk=self.pk).update(statut=self.Statut.ARCHIVEE)
        self.statut = self.Statut.PUBLIEE
        self.publiee_le = maintenant
        self.save(update_fields=["statut", "publiee_le"])


class Partie(models.Model):
    version = models.ForeignKey(VersionParcours, on_delete=models.CASCADE, related_name="parties")
    cle = models.CharField(max_length=60)
    titre = models.CharField(max_length=200)
    ordre = models.PositiveIntegerField()

    class Meta:
        ordering = ["version", "ordre"]
        constraints = [models.UniqueConstraint(fields=["version", "cle"], name="partie_unique_par_version")]

    def __str__(self):
        return self.titre


class Etape(models.Model):
    class Acces(models.TextChoices):
        PUBLIC = "public", "Public"
        INSCRIT = "inscrit", "Inscrit"
        PREMIUM = "premium", "Premium"

    version = models.ForeignKey(VersionParcours, on_delete=models.CASCADE, related_name="etapes")
    partie = models.ForeignKey(Partie, on_delete=models.CASCADE, related_name="etapes")
    cle = models.CharField(max_length=60)
    titre = models.CharField(max_length=200)
    ordre = models.PositiveIntegerField(help_text="Position dans tout le parcours")
    duree_min = models.PositiveIntegerField(null=True, blank=True)
    acces = models.CharField(max_length=8, choices=Acces.choices, default=Acces.INSCRIT)
    html = models.TextField()

    class Meta:
        ordering = ["version", "ordre"]
        verbose_name = "étape"
        constraints = [models.UniqueConstraint(fields=["version", "cle"], name="etape_unique_par_version")]

    def __str__(self):
        return self.titre


class Rattachement(models.Model):
    """Un parcours rendu disponible dans un groupe."""

    class Ouverture(models.TextChoices):
        TOUT = "tout", "Toutes les étapes ouvertes"
        PROGRESSIVE = "progressive", "Le prof ouvre les étapes au fil du cours"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    groupe = models.ForeignKey("organisations.Groupe", on_delete=models.CASCADE, related_name="rattachements")
    parcours = models.ForeignKey(Parcours, on_delete=models.CASCADE, related_name="rattachements")
    ordre = models.PositiveIntegerField(default=0)
    ouverture = models.CharField(max_length=12, choices=Ouverture.choices, default=Ouverture.TOUT)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["groupe", "ordre"]
        constraints = [models.UniqueConstraint(fields=["groupe", "parcours"], name="rattachement_unique")]

    def __str__(self):
        return f"{self.parcours} → {self.groupe}"

    def cles_ouvertes(self):
        return set(self.ouvertures.values_list("cle_etape", flat=True))


class EtapeOuverte(models.Model):
    """En ouverture progressive : une étape que le prof a ouverte pour son groupe."""

    rattachement = models.ForeignKey(Rattachement, on_delete=models.CASCADE, related_name="ouvertures")
    cle_etape = models.CharField(max_length=60)
    ouverte_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    ouverte_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["rattachement", "cle_etape"], name="ouverture_unique")]
