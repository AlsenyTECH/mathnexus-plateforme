import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from .telephone import normaliser_telephone


class UtilisateurManager(BaseUserManager):
    use_in_migrations = True

    def _creer(self, telephone, password, **champs):
        if not telephone:
            raise ValueError("Le numéro de téléphone est obligatoire.")
        telephone = normaliser_telephone(telephone)
        email = champs.pop("email", "") or ""
        utilisateur = self.model(telephone=telephone, email=self.normalize_email(email), **champs)
        utilisateur.set_password(password)
        utilisateur.save(using=self._db)
        return utilisateur

    def create_user(self, telephone, password=None, **champs):
        champs.setdefault("is_staff", False)
        champs.setdefault("is_superuser", False)
        return self._creer(telephone, password, **champs)

    def create_superuser(self, telephone, password=None, **champs):
        champs.update(is_staff=True, is_superuser=True, statut=Utilisateur.Statut.ACTIF)
        return self._creer(telephone, password, **champs)


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    """Un compte de la plateforme : élève, prof, parent ou admin.

    L'identifiant de connexion est le numéro de téléphone (beaucoup d'élèves n'ont pas
    d'e-mail qu'ils consultent). Le rôle dans une classe est porté par l'inscription,
    pas par le compte : un même compte peut être élève dans un groupe et prof dans un autre.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente de validation"
        ACTIF = "actif", "Actif"
        SUSPENDU = "suspendu", "Suspendu"
        ARCHIVE = "archive", "Archivé"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    telephone = models.CharField("téléphone", max_length=20, unique=True)
    email = models.EmailField("e-mail", blank=True)
    prenom = models.CharField("prénom", max_length=80)
    nom = models.CharField("nom", max_length=80)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)

    # Informations demandées à l'inscription
    etablissement_frequente = models.CharField("établissement fréquenté", max_length=150, blank=True)
    niveau_declare = models.CharField("niveau déclaré", max_length=80, blank=True)
    telephone_parent = models.CharField("téléphone d'un parent", max_length=20, blank=True)
    cgu_acceptees_le = models.DateTimeField("conditions acceptées le", null=True, blank=True)

    doit_changer_mot_de_passe = models.BooleanField(default=False)
    dernier_groupe = models.ForeignKey(
        "organisations.Groupe", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    is_staff = models.BooleanField("accès à l'administration", default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UtilisateurManager()

    USERNAME_FIELD = "telephone"
    REQUIRED_FIELDS = ["prenom", "nom"]

    class Meta:
        verbose_name = "utilisateur"
        ordering = ["nom", "prenom"]

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.telephone})"

    @property
    def est_admin(self):
        return self.is_superuser

    @property
    def peut_utiliser(self):
        """Un compte suspendu ou archivé ne peut plus rien faire."""
        return self.is_active and self.statut in {self.Statut.ACTIF, self.Statut.EN_ATTENTE}


class SessionAppareil(models.Model):
    """Les appareils connectés d'un compte, pour limiter le partage de comptes."""

    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name="appareils")
    cle_session = models.CharField(max_length=40, unique=True)
    navigateur = models.CharField(max_length=255, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["cree_le"]


class JournalAudit(models.Model):
    """Qui a fait quoi, quand, depuis où : seulement les actions sensibles."""

    acteur = models.ForeignKey(Utilisateur, null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=60)
    cible = models.CharField(max_length=120, blank=True)
    details = models.JSONField(default=dict, blank=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "entrée du journal d'audit"

    @classmethod
    def noter(cls, request, action, cible="", **details):
        acteur = request.user if request and request.user.is_authenticated else None
        ip = request.META.get("REMOTE_ADDR") if request else None
        return cls.objects.create(acteur=acteur, action=action, cible=str(cible), details=details, adresse_ip=ip)
