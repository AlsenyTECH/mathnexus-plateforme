# CLAUDE.md — mathnexus-plateforme

À lire au début de chaque conversation. À mettre à jour à la fin de chaque session (« État », « La suite » et « Journal »).

## But

La plateforme à comptes de Mathnexus Education (chantier 1 du skill projet-dev) : chaque élève arrive dans sa
classe et n'y voit que ses ressources (parcours, séance du jour, évaluations, progression) ; les parcours arrivent
en **paquets** construits par le moteur de contenu (`AlsenyTECH/mathnexus-moteur`). Noyau commun réutilisé plus
tard par SANGEL.

- Ce que la plateforme doit être pour élèves, parents et prof : doc « Plateforme Mathnexus — ma proposition » (validé) ;
  pilote : skill `cours-classe`.
- Cible technique : doc « Plateforme Mathnexus — Plan complet ».
- Moteur et format des paquets : doc projet « Moteur de contenu — plan » (projet Claude *Dev · Moteur et plateforme*).
- **Version 1 = pilote** : une classe (Terminale S2, maths) et Cathy (prépa ECG1), tout gratuit.

Alseny construit pour apprendre : il lance lui-même le code et les tests. Expliquer chaque choix, surtout en React,
en JavaScript et pour Celery.

## Stack

| Partie | Choix |
| --- | --- |
| Backend | Django 5.1 + Django REST Framework, Python 3.13, pytest ; sessions par cookie + CSRF, Argon2id |
| Base | PostgreSQL 16 en production (`DATABASE_URL`), SQLite par défaut en local |
| Front | React 19 + TypeScript + Vite ; React Router, `fetch`, KaTeX, DOMPurify. Volontairement simple : pas de gestionnaire d'état ni de bibliothèque de composants |
| Composants partagés avec le moteur | `frontend/src/partages/` : JavaScript **sans dépendance**, typé par JSDoc (`// @ts-check`, `allowJs` + `checkJs`) |
| Tests front | Vitest + Testing Library ; bout en bout (Chrome) : `frontend/e2e/scenario.mjs` (parcours complet), `frontend/e2e/evaluation.mjs` (évaluations) |
| CI | GitHub Actions (`.github/workflows/tests.yml`) : pytest sur SQLite **et** PostgreSQL 16, tests de l'outil de conversion, `manage.py check --deploy`, `tsc -b`, Vitest, build |
| Hébergement **cible** | Serveur unique ~4 Go : Docker Compose (API, worker Celery, Celery Beat, Redis, PostgreSQL, front statique), Caddy pour le HTTPS automatique, déploiement par GitHub Actions, sauvegarde quotidienne chiffrée de la base vers un stockage externe. `docker-compose.yml` et `frontend/Caddyfile` existent déjà |
| Hébergement **actuel** (à quitter) | Vercel : API `mathnexus-api.vercel.app` (`backend/vercel.json`, `vercel_build.py`) et front (`frontend/vercel.json`, qui relaie `/api`, `/gestion`, `/static` vers l'API) |

**Décision (26/11/2026)** : Vercel a été validé par erreur. La cible est le serveur Docker Compose du skill projet-dev.
Vercel ne peut pas faire tourner de worker Celery ni de tâches planifiées : la migration passe donc **avant** Celery
et Bunny Stream. **Ne rien ajouter qui dépende de Vercel.** En attendant, les réglages gèrent les deux cas :
`SANS_SERVEUR` (activé par la variable `VERCEL`) coupe les connexions persistantes et les curseurs côté serveur ;
sans Redis, le cache de production passe par une table de la base (`createcachetable`). Ce code propre à Vercel
sera retiré après la bascule. Ne jamais supprimer un projet Vercel sans l'accord explicite d'Alseny.

## Commandes

Alseny travaille sous **Windows** (invite de commandes), un `.venv` par dépôt, plateforme locale **sans Docker**, SQLite.

```bat
cd backend
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
set DJANGO_DEBUG=1
python manage.py migrate
python manage.py createsuperuser          :: téléphone (775148833 ou +221775148833), prénom, nom
python -m pytest                          :: tests (SQLite)
python -m pytest ..\outils\tests          :: test de l'outil de conversion
python manage.py runserver                :: http://localhost:8000 ; admin Django : /gestion/
python manage.py importer_paquet chemin\paquet.zip [--publier]
python manage.py preparer_demo            :: classe « Démo évaluations » + parcours d'essai + un élève
python manage.py paquet_exemple %TEMP%\exemple-format2.zip

cd frontend
npm install
npm run dev        :: http://localhost:5173, relaie /api vers Django
npm test           :: Vitest
npx tsc -b         :: typage (y compris src/partages/*.js)
npm run build      :: construction
npm run e2e        :: scénario de bout en bout
```

Linux : `python3 -m venv .venv && source .venv/bin/activate`, `export DJANGO_DEBUG=1` ; mêmes tests sur PostgreSQL
avec `TEST_DATABASE_URL=postgres://… python -m pytest`.
Bout en bout des évaluations : `frontend/e2e/evaluation.mjs` avec `GROUPE=<id affiché par preparer_demo>`.

Docker (cible) : `cp .env.example .env`, remplir, puis `docker compose up --build` → http://localhost:8080.

Convertir un parcours « cahier » actuel en paquet, puis l'importer (pont provisoire en attendant le moteur) :

```bash
python3 outils/convertir_parcours.py chemin/nombres-complexes.html --slug nombres-complexes \
    --titre "Nombres complexes" --matiere Mathématiques --cycle lycee --public carte -o nc.zip
cd backend && python manage.py importer_paquet ../nc.zip --publier
```

Commandes de gestion : `initialiser_plateforme` (lancée au déploiement Vercel de production), `importer_paquet`,
`preparer_demo`, `paquet_exemple`.

## Organisation

```
backend/
  config/          réglages (tout par variables d'environnement, voir .env.example), URL (toutes sous /api/,
                   admin Django sous /gestion/)
  comptes/         Utilisateur (téléphone normalisé +221…), appareils, journal d'audit, inscription, connexion, validation
  organisations/   Organisation, AnneeScolaire, Groupe, Inscription ; acces.py = le périmètre de chaque compte
  contenus/        Parcours, versions, parties, étapes, rattachements ; acces.py = ouverture et niveau d'accès
                   paquet.py + FORMAT_PAQUET.md = LE CONTRAT avec le moteur ; exemple.py = parcours d'essai (format 2)
  progression/     étapes ouvertes et validées par élève (clés stables)
  evaluations/     Evaluation, Question (importées), Tentative, Reponse (temps par question) ;
                   tentatives.py = les règles (échéance, temps plafonné, correction) ; vues.py = l'API
frontend/src/
  api/             client (cookie + CSRF ; GET, POST, PUT, PATCH, DELETE) et types
  pages/           Entree (connexion, inscription…), Eleve (lecteur), Prof, Admin
  lecteur/         Contenu.tsx (HTML nettoyé + composants), composants.ts (registre data-composant),
                   evaluation.ts (évaluations à barème des pages cahier, format 1), figures, KaTeX
  partages/        evaluation.js + evaluation.css : COPIÉS PAR LE MOTEUR (voir Conventions)
  style/           cahier.css (application), blocs.css (blocs des fragments du moteur, limités à .lbody)
outils/            convertir_parcours.py (pages cahier → paquet ; à retirer après la migration de Terminale et de la prépa)
```

Le découpage cible du Plan complet (`comptes`, `scolarite`, `contenus`, `progression`, `evaluations`, `systeme`,
puis `ia` et `offres`) n'est pas appliqué tel quel : `organisations` joue le rôle de `scolarite` ; `systeme` reste
à créer (avec Celery).

## Contrat avec le moteur de contenu

`backend/contenus/FORMAT_PAQUET.md` et `backend/contenus/paquet.py` (`lire_paquet`) **font autorité** sur le format
des paquets (format 2 aujourd'hui, `FORMAT_ACTUEL` ; le format 1 reste accepté). Le moteur produit exactement ce
format et vérifie ses paquets avec une copie exacte de `paquet.py` (son `controle.py`, surveillé par empreinte et
par sa tâche CI `contrat`). Toute évolution du format commence **ici** : spécification, validation, tests,
`FORMAT_ACTUEL` augmenté, anciens formats toujours acceptés ; puis le moteur recopie `paquet.py`.

## Conventions

- Code, noms, messages et tests en **français**.
- **Accès** : `organisations/acces.py` est le seul endroit qui décide de ce qu'un compte voit ; `contenus/acces.py`
  ajoute l'ouverture et le niveau d'accès. Toute nouvelle vue part de `groupes_visibles` / `groupes_enseignes`
  (ou de `contenus.vues._contexte`) ; hors périmètre → **404** (on ne révèle pas l'existence). Chaque règle d'accès
  a un test qui échoue si on la casse.
- Un module ne touche pas directement aux tables d'un autre ; clés publiques en UUID.
- Paquets : `slug` et `cle` d'étape **stables** d'une version à l'autre (la progression y est accrochée). Aucun
  script, `on…`, `javascript:` dans les fragments : contrôle serveur à l'import **et** DOMPurify côté front.
- `construire_paquet` est reproductible (ZIP stocké, dates 1980-01-01, `manifeste.json` d'abord, puis trié).
- **Composants partagés** (`frontend/src/partages/`) : interface `monter(element, donnees, services) → demonter`.
  Aucun import, aucune dépendance ; tout ce qui dépend de l'hôte passe par `services` (API ici, correction locale
  sur le site public). La plateforme est la référence ; le moteur en garde une copie exacte surveillée par empreinte.
  Changer un de ces fichiers = prévenir le moteur.
- Évaluations : **jamais** `bonnes`, `explication`, `juste` ni score dans une réponse avant la fin de la tentative
  (`test_rien_de_la_correction_avant_la_fin`). Échéance et score calculés par le serveur.
- Secrets jamais dans le dépôt : `.env` (ignoré), variables d'environnement du serveur (aujourd'hui : variables
  Vercel). La clé de déploiement du moteur n'est stockée que par son empreinte (`CLE_DEPLOIEMENT_SHA256`).
- Toute modification de l'API : mettre à jour le tableau des routes du `README.md`.
- Pas de dépendance ajoutée sans en parler.
- **Checklist sécurité à chaque fonctionnalité** (skill projet-dev) : droits vérifiés côté serveur avec un test qui
  les casse ; entrées validées ; CSRF ; XSS ; secrets hors dépôt ; journal d'audit des actions sensibles ; données
  de mineurs minimales (téléphone parent obligatoire, consentement). Référence : OWASP ASVS niveau 2.

## État (au 27/11/2026)

- **Phase 1 faite** (comptes et classes, contenus et progression, application React) :
  - comptes par téléphone (format international), Argon2id, statuts en attente / actif / suspendu / archivé ;
  - inscription avec code de classe, validation par l'admin, import de listes (mot de passe provisoire, changement obligatoire) ;
  - sessions par cookie HttpOnly + CSRF, 5 connexions/min, 2 appareils max, journal d'audit ;
  - import de paquets (admin ou clé de déploiement), versions brouillon → aperçu → publication ;
  - parcours partagés entre classes, ouverture progressive par le prof, accès public / inscrit / premium, vitrine publique ;
  - progression par étape, tableau du prof ; front élève, prof, admin, pages chargées à la demande.
- **M4-a faite** (PR #1, fusionnée le 27/11/2026) : correctifs M3 (numéro sans `+221` dans l'admin et
  `createsuperuser`, `construire_paquet` reproductible) ; **format 2** (évaluations en données) ; module
  `evaluations` (import, API des tentatives, admin) ; composant évaluation partagé dans le lecteur ; style des blocs
  des fragments ; `preparer_demo`, `paquet_exemple`, `e2e/evaluation.mjs`. 173 tests serveur, 29 tests Vitest.
  Preuves faites dans la session (Linux) : scénario e2e (réponses, reprise, correction 2/3, chronomètre) ; temps par
  question en base ; paquet de Complexité v0.3.0 importé ; paquet d'essai : 4 725 octets, empreinte `389c1f16…7f253f`.
- Conséquence voulue de la fusion : la tâche CI `contrat` du moteur échoue (copie de `paquet.py` dépassée) jusqu'à
  **M4-b** côté moteur (recopier `paquet.py`, mettre à jour le contrat, sortir les QCM au format 2, copier `src/partages/`).

## La suite (Version 1)

1. [ ] **Migration de Vercel vers le serveur Docker Compose** :
   - comparer plusieurs fournisseurs de serveur (~4 Go) et montrer le total mensuel à Alseny avant de commander
     (budget de la V1 : environ 10 $ par mois, serveur, Bunny, domaine et sauvegardes compris) ;
   - `docker-compose.yml` a déjà `db` (PostgreSQL 16), `redis`, `api` (gunicorn) et `web` (Caddy, qui sert le front) ;
     y ajouter le worker et le beat Celery, et rendre Redis persistant ; secrets dans `.env` sur le serveur ;
   - déploiement par GitHub Actions après les tests ;
   - sauvegarde quotidienne chiffrée de la base vers un stockage externe, et **un essai de restauration** ;
   - bascule : copie de la base de production actuelle (`pg_dump` / `pg_restore`), vérification, changement de DNS,
     puis retrait de `vercel.json`, `vercel_build.py` et du mode `SANS_SERVEUR`, et désactivation des projets Vercel
     (avec l'accord d'Alseny).
2. [ ] **Celery + Redis + Celery Beat** : module `systeme` (tâches, notifications, journal). Premiers usages : import
   des paquets en tâche de fond, rappels. Redis remplace le cache en base (limitation des tentatives, cache).
3. [~] **Évaluations enregistrées sur le serveur** : fait en M4-a (tentatives, réponses, temps par question, score,
   correction côté serveur). Reste : tableau des résultats pour le prof (avec la fiche élève), questions à barème.
4. [ ] **Carnet d'erreurs** : chaque question ratée y entre, avec la correction et l'étape d'origine.
5. [ ] **Révision espacée** : planning de révision des questions du carnet, recalculé chaque nuit par Celery Beat.
6. [ ] **Séance du jour** : préparée chaque nuit pour chaque élève (étapes ouvertes à faire, évaluation quotidienne
   chronométrée, révisions dues).
7. [ ] **Vidéos Bunny Stream** : envoi et suivi de l'encodage par Celery ; lecture adaptative par **jeton signé à durée
   limitée**, délivré par l'API après vérification des droits, avec restriction de domaine ; les vidéos ne passent
   jamais par le serveur de la plateforme ; clés Bunny dans les secrets.

Aussi dans la Version 1, à placer au moment voulu :
- [ ] double authentification **TOTP** obligatoire pour admin et prof ;
- [ ] fiche élève et **bilan parent** préparé automatiquement, envoyé par Alseny ;
- [ ] application installable (**PWA**) ;
- [ ] import depuis le **moteur de contenu**, puis retrait de `outils/convertir_parcours.py` ;
- [ ] migration de `prepa-cathy` (Supabase + Vercel) et de l'historique de Cathy avant d'arrêter l'ancienne application.

Pas en Version 1 : pgvector et IA, paiement, préproduction, supervision payante.

## À reprendre plus tard

- Tableau des résultats d'évaluation pour le prof (aujourd'hui dans l'admin Django seulement), avec la fiche élève.
- Atelier Pyodide interactif : étape à part, dans une iframe isolée (sans les cookies de session), CSP adaptée.
  Animateur et mesure : quand leur code aura quitté Complexité pour le moteur.
- Liens d'un fragment vers une autre étape : mènent encore au site public (résoudre la clé d'étape).
- L'aperçu admin d'une version n'affiche pas les évaluations (message « elle se passe depuis la classe »).
- `role` d'une évaluation (entrée, sortie) : informatif ; le test d'entrée pourrait un jour permettre de sauter l'étape.
- Questions à barème (exercices rédigés, auto-correction) : format suivant, avec la migration de Terminale.

## Journal

- 26/11/2026 — Création de ce fichier (branche `claude-md`) ; état reconstitué depuis le README et le code ; tests
  relancés. Correction le même jour : Vercel avait été validé par erreur ; la cible est le serveur Docker Compose, et
  la migration passe avant Celery et Bunny. Ajout de « La suite » et du contrat de format avec le moteur.
- 27/11/2026 — M4-a : plan en QCM (toutes options recommandées : un fichier JSON par évaluation ; choix unique et
  multiple ; correction à la fin ; temps mesuré par le navigateur et plafonné par le serveur ; évaluation seule
  interactive ; composants JS de référence ici, copiés par le moteur ; tentatives illimitées sans validation
  automatique). A1 correctifs M3 → A2 format 2 → A3 modèles et import → A4 API → A5 lecteur → A6 style des blocs →
  A7 README, CLAUDE.md, PR.
- 27/11/2026 — `claude-md` fusionnée dans `main` ; `main` fusionnée dans `m4a-evaluations` en combinant les deux
  CLAUDE.md (base M4-a, plus la stack détaillée, l'hébergement actuel, les conventions et « La suite » de
  `claude-md`) ; PR #1 fusionnée.
