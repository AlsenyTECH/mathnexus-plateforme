from django.contrib import admin
from django.urls import include, path

from comptes import vues as c
from organisations import vues as o

api = [
    # Session
    path("auth/csrf/", c.JetonCsrf.as_view()),
    path("auth/inscription/", c.Inscription_.as_view()),
    path("auth/connexion/", c.Connexion.as_view()),
    path("auth/deconnexion/", c.Deconnexion.as_view()),
    # Mon compte
    path("moi/", c.Moi.as_view()),
    path("moi/mot-de-passe/", c.ChangerMotDePasse.as_view()),
    path("moi/groupe-courant/", c.GroupeCourant.as_view()),
    # Groupes, vus par l'élève ou le prof
    path("groupes/", o.MesGroupes.as_view()),
    path("groupes/<uuid:pk>/", o.DetailGroupe.as_view()),
    path("groupes/<uuid:pk>/membres/", o.MembresGroupe.as_view()),
    # Administration
    path("admin/comptes-en-attente/", c.ComptesEnAttente.as_view()),
    path("admin/comptes/<uuid:pk>/valider/", c.ValiderCompte.as_view()),
    path("admin/comptes/<uuid:pk>/refuser/", c.RefuserCompte.as_view()),
    path("admin/comptes/<uuid:pk>/suspendre/", c.SuspendreCompte.as_view()),
    path("admin/comptes/<uuid:pk>/reactiver/", c.ReactiverCompte.as_view()),
    path("admin/groupes/", o.GroupesAdmin.as_view()),
    path("admin/groupes/<uuid:pk>/", o.GroupeAdmin.as_view()),
    path("admin/groupes/<uuid:pk>/regenerer-code/", o.RegenererCode.as_view()),
    path("admin/groupes/<uuid:pk>/importer/", o.ImporterEleves.as_view()),
    path("admin/groupes/<uuid:pk>/profs/", o.AjouterProf.as_view()),
]

urlpatterns = [
    path("gestion/", admin.site.urls),  # l'admin Django, hors du chemin /admin trop connu
    path("api/", include(api)),
]
