# CLAUDE.md — mathnexus-plateforme

À lire au début de chaque conversation. À mettre à jour à la fin de chaque session (« État » et « Journal »).

## But

La plateforme à comptes de Mathnexus Education (chantier 1 du skill projet-dev) : chaque élève arrive dans sa
classe et n'y voit que ses ressources ; les parcours arrivent en **paquets** construits par le moteur de contenu
(`AlsenyTECH/mathnexus-moteur`). Noyau commun réutilisé plus tard par SANGEL.

- Plan complet : doc « Plateforme Mathnexus — Plan complet » ; pilote : skill `cours-classe`.
- Moteur et format des paquets : doc projet « Moteur de contenu — plan » (projet Claude *Dev · Moteur et plateforme*).

Alseny construit pour apprendre : il lance lui-même le code et les tests. Expliquer chaque choix, surtout en React,
en JavaScript et pour Celery.

## Stack

- Backend : Django 5.1 + DRF, PostgreSQL (SQLite en développement), pytest. Sessions par cookie + CSRF, Argon2id.
- Front : React 19 + TypeScript (Vite), React Router, `fetch` ; KaTeX, DOMPurify ; Vitest. Volontairement simple :
  pas de gestionnaire d'état, pas de bibliothèque de composants.
- Composants partagés avec le moteur (`frontend/src/partages/`) : JavaScript **sans dépendance**, typé par JSDoc
  (`// @ts-check`, `allowJs` + `checkJs`).
- Hébergement visé : **un serveur avec Docker Compose** (API, Celery, Redis, PostgreSQL, Caddy). La configuration
  Vercel encore dans le dépôt a été validée par erreur : ne rien ajouter qui en dépende ; elle sera retirée après
  la migration (voir le skill projet-dev).

## Commandes

Alseny travaille sous **Windows** (invite de commandes), un `.venv` par dépôt, plateforme locale **sans Docker**, SQLite.

```bat
cd backend
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
set DJANGO_DEBUG=1
python manage.py migrate
python -m pytest
python manage.py runserver
python manage.py importer_paquet chemin\paquet.zip [--publier]
python manage.py preparer_demo            :: classe « Démo évaluations » + parcours d'essai + un élève
python manage.py paquet_exemple %TEMP%\exemple-format2.zip

cd frontend
npm install
npm run dev        :: http://localhost:5173, relaie /api vers Django
npm test           :: Vitest
npx tsc -b         :: typage (y compris src/partages/*.js)
```

Linux : `python3 -m venv .venv && source .venv/bin/activate`, `export DJANGO_DEBUG=1`.
Bout en bout (Chrome) : `frontend/e2e/scenario.mjs` (parcours complet), `frontend/e2e/evaluation.mjs` (évaluations ;
`GROUPE=<id affiché par preparer_demo>`).

## Organisation

```
backend/
  config/          réglages (variables d'environnement), URL (toutes sous /api/, admin Django sous /gestion/)
  comptes/         Utilisateur (téléphone normalisé +221…), appareils, journal d'audit, inscription, connexion
  organisations/   Organisation, AnneeScolaire, Groupe, Inscription ; acces.py = le périmètre de chaque compte
  contenus/        Parcours, versions, parties, étapes, rattachements ; acces.py = ouverture et niveau d'accès
                   paquet.py + FORMAT_PAQUET.md = LE CONTRAT avec le moteur ; exemple.py = parcours d'essai (format 2)
  progression/     étapes ouvertes et validées par élève (clés stables)
  evaluations/     Evaluation, Question (importées), Tentative, Reponse (temps par question) ;
                   tentatives.py = les règles (échéance, temps plafonné, correction) ; vues.py = l'API
frontend/src/
  api/             client (cookie + CSRF ; GET, POST, PUT, PATCH, DELETE) et types
  pages/           Entree, Eleve (lecteur), Prof, Admin
  lecteur/         Contenu.tsx (HTML nettoyé + composants), composants.ts (registre data-composant),
                   evaluation.ts (évaluations à barème des pages cahier, format 1), figures, KaTeX
  partages/        evaluation.js + evaluation.css : COPIÉS PAR LE MOTEUR (voir Conventions)
  style/           cahier.css (application), blocs.css (blocs des fragments du moteur, limités à .lbody)
outils/            convertir_parcours.py (pages cahier → paquet ; à retirer après la migration de Terminale et de la prépa)
```

## Conventions

- Code, noms, messages et tests en **français**.
- `organisations/acces.py` est le seul endroit qui décide de ce qu'un compte voit ; `contenus/acces.py` ajoute
  l'ouverture et le niveau d'accès. Toute nouvelle vue part de `groupes_visibles` / `groupes_enseignes`
  (ou de `contenus.vues._contexte`) ; hors périmètre → 404.
- **Format des paquets** : `FORMAT_PAQUET.md` et `paquet.py` font autorité. Toute évolution commence ici
  (spécification, validation, tests, `FORMAT_ACTUEL` augmenté, anciens formats toujours acceptés), puis le moteur
  recopie `paquet.py` dans son `controle.py` (sa tâche CI `contrat` échoue tant qu'il ne l'a pas fait).
- **Composants partagés** (`frontend/src/partages/`) : interface `monter(element, donnees, services) → demonter`.
  Aucun import, aucune dépendance ; tout ce qui dépend de l'hôte passe par `services` (API ici, correction locale
  sur le site public). La plateforme est la référence ; le moteur en garde une copie exacte surveillée par empreinte.
  Changer un de ces fichiers = prévenir le moteur (M4-b et suivantes).
- `construire_paquet` est reproductible (ZIP stocké, dates 1980-01-01, `manifeste.json` d'abord, puis trié).
- **Checklist sécurité** à chaque fonctionnalité (skill projet-dev) : droits côté serveur avec un test qui les casse ;
  entrées validées ; CSRF ; XSS (HTML de paquet contrôlé à l'import **et** passé par DOMPurify à l'affichage) ;
  secrets hors du dépôt ; journal des actions sensibles ; données de mineurs au minimum.
- Évaluations : **jamais** `bonnes`, `explication`, `juste` ni score dans une réponse avant la fin de la tentative
  (`test_rien_de_la_correction_avant_la_fin`). Échéance et score calculés par le serveur.
- Pas de dépendance ajoutée sans en parler.

## État (au 27/11/2026, M4-a)

- Phase 1 faite : comptes, classes, contenus, progression, application React, e2e (voir README).
- **M4-a** (branche `m4a-evaluations`, PR à fusionner par Alseny) : correctifs M3 (numéro sans `+221` dans l'admin et
  `createsuperuser`, `construire_paquet` reproductible) ; **format 2** (évaluations en données) ; module
  `evaluations` (import, API des tentatives, admin) ; composant évaluation partagé dans le lecteur ; style des blocs
  des fragments ; `preparer_demo`, `paquet_exemple`, `e2e/evaluation.mjs`. 173 tests serveur, 29 tests Vitest.
  Preuves faites dans la session (Linux) : scénario e2e (réponses, reprise, correction 2/3, chronomètre) ; temps par
  question en base ; paquet de Complexité v0.3.0 importé ; paquet d'essai : 4 725 octets, empreinte `389c1f16…7f253f`.
- Prochaine étape côté moteur : **M4-b** (recopier `paquet.py`, mettre à jour le contrat, sortir les QCM au format 2,
  copier `src/partages/`).

## À reprendre plus tard

- Tableau des résultats d'évaluation pour le prof (aujourd'hui dans l'admin Django seulement), avec la fiche élève.
- Atelier Pyodide interactif : étape à part, dans une iframe isolée (sans les cookies de session), CSP adaptée.
  Animateur et mesure : quand leur code aura quitté Complexité pour le moteur.
- Liens d'un fragment vers une autre étape : mènent encore au site public (résoudre la clé d'étape).
- L'aperçu admin d'une version n'affiche pas les évaluations (message « elle se passe depuis la classe »).
- `role` d'une évaluation (entrée, sortie) : informatif ; le test d'entrée pourrait un jour permettre de sauter l'étape.
- Questions à barème (exercices rédigés, auto-correction) : format suivant, avec la migration de Terminale.

## Journal

- 27/11/2026 — M4-a : plan en QCM (toutes options recommandées : un fichier JSON par évaluation ; choix unique et
  multiple ; correction à la fin ; temps mesuré par le navigateur et plafonné par le serveur ; évaluation seule
  interactive ; composants JS de référence ici, copiés par le moteur ; tentatives illimitées sans validation
  automatique). A1 correctifs M3 → A2 format 2 → A3 modèles et import → A4 API → A5 lecteur → A6 style des blocs →
  A7 README, ce fichier, PR. Création de ce CLAUDE.md.
