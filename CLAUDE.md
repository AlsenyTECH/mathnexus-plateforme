# CLAUDE.md — Plateforme Mathnexus

À lire au début de chaque conversation. À mettre à jour à la fin de chaque session (section « État » et « Journal »).

## But

Plateforme à comptes de Mathnexus Education : chaque élève arrive dans sa classe et n'y voit que ses
ressources (parcours, séance du jour, évaluations, progression). Construite sur un **noyau commun**
réutilisable plus tard par SANGEL.

- Ce que la plateforme doit être pour élèves, parents et prof : doc « Plateforme Mathnexus — ma proposition » (validé).
- Cible technique : doc « Plateforme Mathnexus — Plan complet ».
- **Version 1 = pilote** : une classe (Terminale S2, maths) et Cathy (prépa ECG1), tout gratuit.

Alseny construit pour apprendre : il lance lui-même le code et les tests. Expliquer chaque choix,
surtout en React, TypeScript et (plus tard) Celery.

## Stack

| Partie | Choix |
| --- | --- |
| Backend | Django 5 + Django REST Framework, Python 3.13, pytest |
| Base | PostgreSQL 16 en production (`DATABASE_URL`), SQLite par défaut en local |
| Front | React 19 + TypeScript + Vite ; React Router, `fetch`, KaTeX, DOMPurify ; pas de gestionnaire d'état ni de bibliothèque de composants |
| Tests front | Vitest + Testing Library ; scénario de bout en bout `frontend/e2e/scenario.mjs` (Playwright, Chrome) |
| CI | GitHub Actions (`.github/workflows/tests.yml`) : pytest sur SQLite **et** PostgreSQL 16, tests de l'outil de conversion, `manage.py check --deploy`, `tsc -b`, Vitest, build |
| Hébergement actuel | **Vercel (provisoire)** : API `mathnexus-api.vercel.app` (`backend/vercel.json`, `vercel_build.py`) et front (`frontend/vercel.json`, qui relaie `/api`, `/gestion`, `/static` vers l'API) |
| Hébergement cible | Serveur unique ~4 Go : Docker Compose (API, worker Celery, Redis, PostgreSQL, front statique), Caddy pour le HTTPS. `docker-compose.yml` et `frontend/Caddyfile` existent déjà |

**Décision (26/11/2026)** : Vercel sert au pilote ; on passe au serveur Docker quand Celery et Bunny Stream arrivent
(phase 2). Les réglages gèrent les deux cas : `SANS_SERVEUR` (activé par la variable `VERCEL`) coupe les connexions
persistantes et les curseurs côté serveur ; sans Redis, le cache de production passe par une table de la base
(`createcachetable`), pour que la limitation des tentatives tienne entre instances.

## Commandes

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DJANGO_DEBUG=1
python manage.py migrate
python manage.py createsuperuser          # téléphone, prénom, nom
python manage.py runserver                # http://localhost:8000 ; admin Django : /gestion/
python -m pytest                          # tests (SQLite)
TEST_DATABASE_URL=postgres://… python -m pytest   # mêmes tests sur PostgreSQL
python -m pytest ../outils/tests          # test de l'outil de conversion

# Front (second terminal)
cd frontend
npm install
npm run dev                               # http://localhost:5173, relaie /api vers :8000
npm test                                  # Vitest
npx tsc -b && npm run build               # typage + construction
npm run e2e                               # scénario de bout en bout

# Docker (cible) : cp .env.example .env, remplir, puis
docker compose up --build                 # http://localhost:8080

# Convertir un parcours « cahier » actuel en paquet, puis l'importer
python3 outils/convertir_parcours.py chemin/nombres-complexes.html --slug nombres-complexes \
    --titre "Nombres complexes" --matiere Mathématiques --cycle lycee --public carte -o nc.zip
cd backend && python manage.py importer_paquet ../nc.zip --publier
```

Commandes de gestion : `initialiser_plateforme` (lancée au déploiement Vercel de production), `importer_paquet`.

## Organisation du code

```
backend/
  config/          réglages (tout par variables d'environnement, voir .env.example), URL
  comptes/         Utilisateur, appareils, journal d'audit, inscription, connexion, validation
  organisations/   Organisation, AnneeScolaire, Groupe, Inscription ; acces.py = périmètre de chaque compte
  contenus/        Parcours, versions, parties, étapes, rattachements ; paquet.py = validation ; FORMAT_PAQUET.md
  progression/     progression par élève et par étape
frontend/src/
  api/             client (cookie de session + jeton CSRF), types des réponses
  pages/           Entree (connexion, inscription…), Eleve, Prof, Admin
  lecteur/         rendu d'une étape : KaTeX, figures, évaluations chronométrées, nettoyage DOMPurify
  style/cahier.css style « cahier » repris des parcours
outils/convertir_parcours.py   parcours « cahier » HTML → paquet (pont provisoire en attendant le moteur)
```

Le découpage cible du Plan complet (`comptes`, `scolarite`, `contenus`, `progression`, `evaluations`, `systeme`,
puis `ia` et `offres`) n'est pas encore appliqué tel quel : `organisations` joue le rôle de `scolarite` ;
`evaluations` et `systeme` restent à créer.

## Conventions

- Code, noms et messages en **français** (modèles, vues, routes, tests).
- **Accès** : `organisations/acces.py` est le seul endroit qui décide de ce qu'un compte voit. Toute nouvelle vue part
  de `groupes_visibles` ou `groupes_enseignes` ; `contenus/acces.py` ajoute ouverture et niveau d'accès.
  Hors périmètre → **404** (on ne révèle pas l'existence). Chaque règle d'accès a un test qui échoue si on la casse.
- Un module ne touche pas directement aux tables d'un autre ; clés publiques en UUID.
- Paquets : `slug` et `cle` d'étape **stables** d'une version à l'autre (la progression y est accrochée).
  Aucun script, `on…`, `javascript:` dans les fragments : contrôle serveur à l'import + DOMPurify côté front.
- Secrets jamais dans le dépôt : `.env` (ignoré), variables Vercel. La clé de déploiement du moteur n'est stockée
  que par son empreinte (`CLE_DEPLOIEMENT_SHA256`).
- Toute modification de l'API : mettre à jour le tableau des routes du `README.md`.
- **Checklist sécurité à chaque fonctionnalité** : droits vérifiés côté serveur avec tests, entrées validées,
  CSRF/XSS, secrets hors dépôt, journal d'audit des actions sensibles, données de mineurs minimales
  (téléphone parent obligatoire, consentement). Référence : OWASP ASVS niveau 2.

## État (au 26/11/2026)

**Phase 1 faite** (comptes et classes, contenus et progression, application React) :
- comptes par téléphone (format international), Argon2id, statuts en attente / actif / suspendu / archivé ;
- inscription avec code de classe, validation par l'admin, import de listes (mot de passe provisoire, changement obligatoire) ;
- sessions par cookie HttpOnly + CSRF, 5 connexions/min, 2 appareils max, journal d'audit ;
- import de paquets (admin ou clé de déploiement), versions brouillon → aperçu → publication ;
- parcours partagés entre classes, ouverture progressive par le prof, accès public / inscrit / premium, vitrine publique ;
- progression par étape, tableau du prof ;
- front : élève (tableau de bord, sommaire, lecteur), prof, admin ; pages chargées à la demande.

Vérifié le 26/11/2026 : **88 tests backend** et 1 test de l'outil passent sur SQLite (le README annonce encore 83).

**Manque par rapport à la Version 1 du skill** :
- [ ] double authentification **TOTP** obligatoire pour admin et prof ;
- [ ] **évaluations enregistrées sur le serveur** (temps par question), révision espacée, carnet d'erreurs (module `evaluations`) ;
- [ ] **séance du jour** ;
- [ ] **vidéos Bunny Stream** (jeton signé délivré par l'API après vérification des droits) ;
- [ ] **Celery + Redis + Celery Beat** (import, encodage vidéo, calculs nocturnes, bilans parents, rappels) ;
- [ ] fiche élève et **bilan parent** préparé automatiquement ;
- [ ] application installable (**PWA**) ;
- [ ] passage au **serveur Docker** + sauvegarde quotidienne chiffrée ;
- [ ] import depuis le **moteur de contenu** (aujourd'hui : `convertir_parcours.py` sur les pages HTML) ;
- [ ] migration de `prepa-cathy` (Supabase + Vercel) et de l'historique de Cathy.

Ordre des chantiers (skill projet-dev) : le **moteur de contenu** (dépôt `parcours-complexite` comme modèle) passe
avant la suite de la plateforme.

## Journal

- 26/11/2026 — Création de ce fichier ; état reconstitué depuis le README et le code ; tests relancés.
  Décision : Vercel provisoire jusqu'à la phase 2.
