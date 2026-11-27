"""Organisations, années scolaires, groupes et inscriptions.

Vocabulaire générique, pour servir Mathnexus aujourd'hui et SANGEL demain :
- une Organisation = Mathnexus Education, une école partenaire, plus tard la FST UCAD ;
- un Groupe = une classe (Terminale S2 2026-2027), plus tard une filière-niveau (L1 Maths FST) ;
- une Inscription = le lien entre un compte et un groupe, avec son rôle et son statut.
"""
import secrets
import unicodedata
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

# Alphabet sans caractères ambigus (pas de 0/O, 1/I/L) pour les codes dictés en classe.
_ALPHABET_CODE = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generer_suffixe(longueur=5):
    return "".join(secrets.choice(_ALPHABET_CODE) for _ in range(longueur))


class Organisation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    contact = models.CharField(max_length=150, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class AnneeScolaire(models.Model):
    libelle = models.CharField(max_length=20, unique=True, help_text="Par exemple 2026-2027")
    debut = models.DateField()
    fin = models.DateField()
    en_cours = models.BooleanField(default=False)

    class Meta:
        ordering = ["-debut"]
        verbose_name = "année scolaire"
        verbose_name_plural = "années scolaires"

    def __str__(self):
        return self.libelle


class Groupe(models.Model):
    class Cycle(models.TextChoices):
        LYCEE = "lycee", "Lycée"
        PREPA = "prepa", "Prépa"
        UNIVERSITE = "universite", "Université"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(Organisation, on_delete=models.PROTECT, related_name="groupes")
    annee = models.ForeignKey(AnneeScolaire, on_delete=models.PROTECT, related_name="groupes")
    nom = models.CharField(max_length=100, help_text="Par exemple Terminale S2")
    cycle = models.CharField(max_length=12, choices=Cycle.choices)
    code_inscription = models.CharField(max_length=24, unique=True, blank=True)
    inscriptions_ouvertes = models.BooleanField(
        default=True, help_text="Si non, le code d'inscription est refusé."
    )
    validation_automatique = models.BooleanField(
        default=False,
        help_text="Pour un établissement sous contrat : le code suffit, sans validation manuelle.",
    )
    archive = models.BooleanField(default=False)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["annee", "nom"]
        constraints = [
            models.UniqueConstraint(fields=["organisation", "annee", "nom"], name="groupe_unique_par_annee"),
        ]

    def __str__(self):
        return f"{self.nom} — {self.annee}"

    def save(self, *args, **kwargs):
        if not self.code_inscription:
            self.code_inscription = self.nouveau_code()
        super().save(*args, **kwargs)

    def nouveau_code(self):
        # Sans accent : un code se dicte en classe et se tape sur n'importe quel clavier.
        sans_accent = unicodedata.normalize("NFKD", self.nom).encode("ascii", "ignore").decode()
        prefixe = "".join(c for c in sans_accent.upper() if c.isalnum())[:4] or "GRP"
        while True:
            code = f"{prefixe}-{self.annee.libelle[:4]}-{generer_suffixe()}"
            if not Groupe.objects.filter(code_inscription=code).exists():
                return code

    def regenerer_code(self):
        self.code_inscription = self.nouveau_code()
        self.save(update_fields=["code_inscription"])


class Inscription(models.Model):
    class Role(models.TextChoices):
        ELEVE = "eleve", "Élève"
        PROF = "prof", "Prof"

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        VALIDEE = "validee", "Validée"
        REFUSEE = "refusee", "Refusée"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="inscriptions")
    groupe = models.ForeignKey(Groupe, on_delete=models.CASCADE, related_name="inscriptions")
    role = models.CharField(max_length=8, choices=Role.choices, default=Role.ELEVE)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    valide_le = models.DateTimeField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["groupe", "utilisateur"]
        constraints = [
            models.UniqueConstraint(fields=["utilisateur", "groupe"], name="une_inscription_par_groupe"),
        ]

    def __str__(self):
        return f"{self.utilisateur} → {self.groupe} ({self.get_role_display()}, {self.get_statut_display()})"

    def valider(self, par):
        self.statut = self.Statut.VALIDEE
        self.valide_par = par
        self.valide_le = timezone.now()
        self.save(update_fields=["statut", "valide_par", "valide_le"])
