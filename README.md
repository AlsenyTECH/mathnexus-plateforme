# Plateforme Mathnexus

Plateforme à comptes pour les classes de Mathnexus Education : chaque élève arrive directement
dans sa classe et n'y voit que ses ressources. Construite sur un **noyau commun** qui servira
ensuite SANGEL (organisations, groupes, rôles, offres, paiement, médias, progression, IA).

Plan complet : document « Plateforme Mathnexus — Plan complet ».

## État : phase 1, premier lot (noyau comptes et classes)

| Fait | Détail |
| --- | --- |
| Comptes | Connexion par téléphone (normalisé au format international), Argon2id, statuts en attente / actif / suspendu / archivé |
| Inscription | Formulaire public, code de classe, validation automatique pour un établissement sous contrat, téléphone parent obligatoire pour un mineur, acceptation des conditions datée |
| Validation | File des comptes en attente, validation avec choix de la classe, refus (suppression du compte), suspension et réactivation |
| Import | Liste de classe en une fois, mot de passe provisoire montré une seule fois, changement obligatoire à la première connexion, tout ou rien |
| Classes | Organisations, années scolaires, groupes avec code d'inscription lisible et régénérable, rôles élève / prof par groupe |
| Redirection | Admin, compte en attente, mot de passe à changer, prof, une classe, plusieurs classes (dernier choix retenu), aucune classe |
| Sécurité | Sessions par cookie HttpOnly + CSRF, limitation des tentatives (5 connexions par minute), deux appareils au plus par compte, périmètre vérifié côté serveur (404 hors périmètre), journal d'audit, réglages durcis hors DEBUG |
| Tests | 46 tests, passés sur SQLite et PostgreSQL 16 ; chaque règle d'accès cassée volontairement fait échouer au moins un test |

À venir dans la phase 1 : contenus (import des paquets du moteur, versions, rattachement aux classes),
lecteur d'étape, progression, tableau de bord prof, puis l'application React.

## Démarrer en local

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DJANGO_DEBUG=1
python manage.py migrate
python manage.py createsuperuser      # demande le téléphone, le prénom, le nom
python manage.py runserver
python -m pytest                      # les tests
```

Administration Django : http://localhost:8000/gestion/ (créer l'organisation, l'année et les classes).

Avec Docker (PostgreSQL + Redis + API) : `cp .env.example .env`, remplir les valeurs, puis `docker compose up --build`.

## API

Toutes les routes sont sous `/api/`. L'application appelle d'abord `GET auth/csrf/`, puis envoie
l'en-tête `X-CSRFToken` sur chaque requête qui modifie quelque chose.

| Route | Qui | Rôle |
| --- | --- | --- |
| `POST auth/inscription/` | public | Créer un compte (avec ou sans `code_classe`) |
| `POST auth/connexion/` | public | Ouvrir une session ; renvoie `destination` |
| `POST auth/deconnexion/` | connecté | Fermer la session |
| `GET moi/` | connecté | Profil et `destination` |
| `POST moi/mot-de-passe/` | connecté | Changer le mot de passe (déconnecte les autres appareils) |
| `POST moi/groupe-courant/` | élève | Choisir la classe de travail |
| `GET groupes/`, `GET groupes/<id>/` | connecté | Ses classes |
| `GET groupes/<id>/membres/` | prof du groupe, admin | Les élèves de la classe |
| `GET admin/comptes-en-attente/` | admin | File de validation |
| `POST admin/comptes/<id>/valider/` | admin | Valider (`groupe` si l'élève n'a pas donné de code) |
| `POST admin/comptes/<id>/refuser/` | admin | Refuser et supprimer |
| `POST admin/comptes/<id>/suspendre/`, `.../reactiver/` | admin | Suspendre, réactiver |
| `GET/POST admin/groupes/`, `GET/PATCH admin/groupes/<id>/` | admin | Gérer les classes |
| `POST admin/groupes/<id>/regenerer-code/` | admin | Nouveau code d'inscription |
| `POST admin/groupes/<id>/importer/` | admin | Importer une liste d'élèves |
| `POST admin/groupes/<id>/profs/` | admin | Ajouter un prof au groupe |

Valeurs de `destination` : `admin`, `attente`, `changer_mot_de_passe`, `prof`,
`groupe` (avec `groupe`), `choix_groupe` (avec `groupes`), `aucun_groupe`.

## Organisation du code

```
backend/
  config/          réglages (variables d'environnement), URL
  comptes/         Utilisateur, appareils, journal d'audit, inscription, connexion, validation
  organisations/   Organisation, AnneeScolaire, Groupe, Inscription ; acces.py = le périmètre de chaque compte
```

`organisations/acces.py` est le seul endroit qui décide de ce qu'un compte peut voir :
toute nouvelle vue doit partir de `groupes_visibles` ou `groupes_enseignes`.
