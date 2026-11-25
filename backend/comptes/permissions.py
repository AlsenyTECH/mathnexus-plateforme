from rest_framework.permissions import BasePermission


class EstConnecteEtActif(BasePermission):
    """Par défaut : connecté, et compte ni suspendu ni archivé."""

    message = "Connexion requise."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.peut_utiliser)


class EstAdmin(BasePermission):
    message = "Réservé à l'administration."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.peut_utiliser and u.est_admin)
