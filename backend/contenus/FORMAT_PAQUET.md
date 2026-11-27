# Format des paquets de parcours (format 2)

Le moteur de parcours produit, pour chaque parcours, une archive ZIP que la plateforme importe.

```
manifeste.json
etapes/carte.html
etapes/algebrique.html
evaluations/carte-sortie.json      (format 2)
…
```

| Format | Ce qu'il apporte | Accepté |
| --- | --- | --- |
| 1 | manifeste + fragments HTML | oui, sans limite de date |
| 2 | + évaluations en données ([plus bas](#format-2--les-évaluations-en-données)) | oui (`FORMAT_ACTUEL`) |

Un paquet au format 1 reste valable tel quel. Le champ `evaluations` n'existe qu'à partir du format 2.

## manifeste.json

```json
{
  "format": 1,
  "parcours": {
    "slug": "nombres-complexes",
    "titre": "Nombres complexes",
    "matiere": "Mathématiques",
    "cycle": "lycee",
    "description": "Tout le chapitre de Terminale S2, sauf les transformations du plan."
  },
  "parties": [
    {
      "cle": "forme-algebrique",
      "titre": "La forme algébrique",
      "etapes": [
        {"cle": "carte", "titre": "La carte d'un exercice de bac", "fichier": "etapes/carte.html",
         "acces": "public", "duree_min": 6}
      ]
    }
  ]
}
```

| Champ | Règle |
| --- | --- |
| `slug`, `cle` | minuscules, chiffres et tirets, 60 caractères au plus ; **stables d'une version à l'autre** : la progression des élèves y est accrochée |
| `cycle` | `lycee`, `prepa` ou `universite` |
| `acces` | `public` (vitrine, sans compte), `inscrit` (tout élève validé de la classe, par défaut), `premium` (offre payante) |
| `duree_min` | entier de 1 à 600, facultatif |
| `fichier` | `etapes/<nom>.html`, présent dans l'archive, UTF-8, 2 Mo au plus |

Limites de l'archive : 25 Mo, 40 Mo décompressée, 1 000 fichiers.

## Les fragments HTML

Un fragment contient le corps de l'étape, sans `<html>`, `<head>` ni `<body>`.
Les formules restent en TeX (`\( … \)`, `\[ … \]`) : l'application les rend.

**Interdits** (le paquet est refusé, avec la liste des lignes en cause) : `<script>`, `<style>`,
`<iframe>`, `<object>`, `<embed>`, `<form>` et les champs de saisie, `<base>`, `<meta>`, `<link>`,
tout attribut `on…` (`onclick`…), `srcdoc`, les URL `javascript:` et `data:` autres que des images.

Les composants interactifs se déclarent par des attributs, et c'est l'application qui les anime :

```html
<div class="graph" data-fig="second-degre"></div>
```

Ainsi, même un paquet modifié par un tiers ne peut pas exécuter de code chez les élèves.

## Format 2 : les évaluations en données

Une évaluation (QCM d'entrée ou de sortie, évaluation chronométrée) n'est plus écrite en HTML :
c'est un fichier JSON `evaluations/<nom>.json`, déclaré par l'étape qui la contient. La plateforme
range les bonnes réponses en base et **ne les envoie au navigateur qu'après la fin de la tentative**
de l'élève ; le score et l'échéance sont calculés par le serveur.

Dans le manifeste, une étape déclare ses évaluations :

```json
{"cle": "carte", "titre": "La carte d'un exercice de bac", "fichier": "etapes/carte.html",
 "evaluations": [{"cle": "carte-sortie", "fichier": "evaluations/carte-sortie.json"}]}
```

Dans le fragment de cette étape, un emplacement marque où l'évaluation s'affiche :

```html
<div data-composant="evaluation" data-cle="carte-sortie"></div>
```

Le fichier `evaluations/carte-sortie.json` :

```json
{
  "titre": "Test de sortie",
  "role": "sortie",
  "consigne": "<p>Réponds, puis termine pour voir la correction.</p>",
  "duree_min": 5,
  "seuil": 2,
  "questions": [
    {"cle": "module", "type": "choix_unique",
     "enonce": "<p>Le module de \\(z = 3 + 4i\\) vaut :</p>",
     "choix": ["\\(5\\)", "\\(7\\)", "\\(25\\)", "\\(\\sqrt{7}\\)"],
     "bonnes": [0], "points": 1,
     "explication": "<p>\\(|z| = \\sqrt{3^2 + 4^2} = 5\\).</p>"},
    {"cle": "reels", "type": "choix_multiple",
     "enonce": "<p>Lesquels sont réels ?</p>",
     "choix": ["\\(i^2\\)", "\\(i^3\\)", "\\((1+i)(1-i)\\)"],
     "bonnes": [0, 2], "points": 2}
  ]
}
```

| Champ | Règle |
| --- | --- |
| `cle` (évaluation, dans le manifeste) | comme une clé d'étape ; **unique dans tout le parcours** et **stable** : les tentatives des élèves y sont accrochées |
| `fichier` | `evaluations/<nom>.json`, présent dans l'archive, UTF-8, 512 Ko au plus |
| emplacement | le fragment de l'étape contient **exactement un** `data-composant="evaluation"` avec ce `data-cle` ; un emplacement sans évaluation déclarée par l'étape est refusé |
| `titre` | obligatoire, 200 caractères au plus |
| `role` | `entree` (test d'entrée), `sortie` (test de sortie), `evaluation` (par défaut) ; informatif pour l'instant |
| `consigne` | HTML facultatif |
| `duree_min` | entier de 1 à 600, facultatif ; présent : l'évaluation est chronométrée et le serveur refuse les réponses après l'échéance |
| `seuil` | points à atteindre pour réussir, facultatif, par quarts de point, au plus le total |
| `questions` | liste non vide, 200 au plus |
| `cle` (question) | comme une clé d'étape, unique dans l'évaluation, **stable** (le temps par question se compare d'une version à l'autre) |
| `type` | `choix_unique` (par défaut) ou `choix_multiple` |
| `enonce` | HTML obligatoire |
| `choix` | 2 à 12 textes HTML |
| `bonnes` | indices des bonnes réponses, **à partir de 0** ; exactement un pour `choix_unique` ; pour `choix_multiple`, au moins un et pas tous |
| `points` | de 0,25 à 100, par quarts de point, 1 par défaut ; une question à choix multiple est notée tout ou rien |
| `explication` | HTML facultatif, montré avec la correction |

Tout champ inconnu est refusé (une faute de frappe comme `bonne` au lieu de `bonnes` ne passe pas).
Les morceaux de HTML (`consigne`, `enonce`, `choix`, `explication`) suivent les mêmes règles que
les fragments ; les formules restent en TeX.

## Import

- Par l'admin connecté : `POST /api/admin/contenus/import/` (champ `paquet`).
- Par le moteur (GitHub Actions) : même route, en-tête `Authorization: Cle-Deploiement <clé>`.
  La plateforme ne garde que l'empreinte SHA-256 de la clé (`CLE_DEPLOIEMENT_SHA256`).

Chaque import crée une nouvelle **version en brouillon**. L'admin la prévisualise, puis la publie :
la version publiée précédente est archivée. Un paquet identique au dernier importé est refusé.
