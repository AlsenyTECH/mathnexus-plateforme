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
| Hébergement **cible** | Serveur unique ~4 Go : Docker Compose (API, worker Celery, Celery Beat, Redis, PostgreSQL, front statique), Caddy pour le HTTPS automatique, déploiement par GitHub Actions, sauvegarde quotidienne chiffrée de la base vers un stockage externe. `docker-compose.yml` et `frontend/Caddyfile` existent déjà |
| Hébergement **actuel** (à quitter) | Vercel : API `mathnexus-api.vercel.app` (`backend/vercel.json`, `vercel_build.py`) et front (`frontend/vercel.json`, qui relaie `/api`, `/gestion`, `/static` vers l'API) |

**Décision (26/11/2026)** : Vercel a été validé par erreur. La cible est le serveur Docker Compose du skill projet-dev.
Vercel ne peut pas faire tourner de worker Celery ni de tâches planifiées : la migration passe donc **avant** Celery
et Bunny Stream (voir « La suite »). En attendant, les réglages gèrent les deux cas : `SANS_SERVEUR` (activé par la
variable `VERCEL`) coupe les connexions persistantes et les curseurs côté serveur ; sans Redis, le cache de production
passe par une table de la base (`createcachetable`). Ce code propre à Vercel sera retiré après la bascule.

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

## Contrat avec le moteur de contenu

`backend/contenus/FORMAT_PAQUET.md` et `backend/contenus/paquet.py` (`lire_paquet`) **font autorité** sur le format
des paquets (format 1 aujourd'hui, `FORMAT_ACTUEL`). Le moteur de contenu (`mathnexus-moteur`, chantier 1) produit
exactement ce format et vérifie ses paquets avec la même fonction. Toute évolution du format (par exemple les
évaluations en données, pour la correction côté serveur) commence **ici** : on met à jour FORMAT_PAQUET.md et
`paquet.py`, avec leurs tests, on augmente `FORMAT_ACTUEL` en gardant l'ancien format accepté, et le moteur suit.

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

## La suite (Version 1)

Ordre des chantiers (skill projet-dev) : le **moteur de contenu** passe avant la suite de la plateforme
(plan : doc projet « Moteur de contenu — plan »). Ensuite, dans cet ordre proposé, qui suit les dépendances
(à valider au démarrage) :

1. [ ] **Migration de Vercel vers le serveur Docker Compose** :
   - comparer plusieurs fournisseurs de serveur (~4 Go) et montrer le total mensuel à Alseny avant de commander
     (budget de la V1 : environ 10 $ par mois, serveur, Bunny, domaine et sauvegardes compris) ;
   - `docker-compose.yml` a déjà `db` (PostgreSQL 16), `redis`, `api` (gunicorn) et `web` (Caddy, qui sert le front) ;
     y ajouter le worker et le beat Celery à l'étape 2, et rendre Redis persistant ; secrets dans `.env` sur le
     serveur, jamais dans le dépôt ;
   - déploiement par GitHub Actions après les tests ;
   - sauvegarde quotidienne chiffrée de la base vers un stockage externe, et **un essai de restauration** ;
   - bascule : copie de la base de production actuelle (`pg_dump` / `pg_restore`), vérification, changement de DNS,
     puis retrait de `vercel.json`, `vercel_build.py` et du mode `SANS_SERVEUR`.
2. [ ] **Celery + Redis + Celery Beat** : module `systeme` (tâches, notifications, journal). Premiers usages : import
   des paquets en tâche de fond, rappels. Redis remplace le cache en base (limitation des tentatives, cache).
3. [ ] **Évaluations enregistrées sur le serveur** (module `evaluations`) : tentatives, réponses, **temps par question**,
   note ; la correction se fait côté serveur et les réponses attendues ne partent jamais chez l'élève avant la remise.
   Demande que les évaluations arrivent du moteur sous forme de données : évolution du format de paquet (voir
   « Contrat avec le moteur »).
4. [ ] **Carnet d'erreurs** : chaque question ratée y entre, avec la correction et l'étape d'origine.
5. [ ] **Révision espacée** : planning de révision des questions du carnet, recalculé chaque nuit par Celery Beat.
6. [ ] **Séance du jour** : préparée chaque nuit pour chaque élève (étapes ouvertes à faire, évaluation quotidienne
   chronométrée, révisions dues).
7. [ ] **Vidéos Bunny Stream** : envoi et suivi de l'encodage par Celery ; lecture adaptative par **jeton signé à durée
   limitée**, délivré par l'API après vérification des droits, avec restriction de domaine ; les vidéos ne passent
   jamais par le serveur de la plateforme ; clés Bunny dans les secrets.

Aussi dans la Version 1, à placer dans cet ordre au moment voulu :
- [ ] double authentification **TOTP** obligatoire pour admin et prof ;
- [ ] fiche élève et **bilan parent** préparé automatiquement, envoyé par Alseny ;
- [ ] application installable (**PWA**) ;
- [ ] import depuis le **moteur de contenu**, puis retrait de `outils/convertir_parcours.py` ;
- [ ] migration de `prepa-cathy` (Supabase + Vercel) et de l'historique de Cathy avant d'arrêter l'ancienne application.

Pas en Version 1 : pgvector et IA, paiement, préproduction, supervision payante.

## Journal

- 26/11/2026 — Création de ce fichier ; état reconstitué depuis le README et le code ; tests relancés.
  Décision : Vercel provisoire jusqu'à la phase 2.
- 26/11/2026 — Correction : Vercel avait été validé par erreur ; la cible est le serveur Docker Compose, et la
  migration passe avant Celery et Bunny. Ajout de « La suite » et du contrat de format avec le moteur.
