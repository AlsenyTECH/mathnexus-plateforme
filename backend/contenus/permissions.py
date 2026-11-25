import hashlib
import hmac

from django.conf import settings
from rest_framework.permissions import BasePermission

from comptes.permissions import EstAdmin

PREFIXE = "Cle-Deploiement "


def cle_de_deploiement_valide(request):
    """Le moteur de parcours (GitHub Actions) s'authentifie par une clé dont seule l'empreinte est stockée."""
    attendu = getattr(settings, "CLE_DEPLOIEMENT_SHA256", "")
    entete = request.META.get("HTTP_AUTHORIZATION", "")
    if not attendu or not entete.startswith(PREFIXE):
        return False
    recu = hashlib.sha256(entete[len(PREFIXE):].strip().encode()).hexdigest()
    return hmac.compare_digest(recu, attendu.lower())


class EstAdminOuCleDeploiement(BasePermission):
    message = "Réservé à l'administration ou au moteur de parcours."

    def has_permission(self, request, view):
        return cle_de_deploiement_valide(request) or EstAdmin().has_permission(request, view)
