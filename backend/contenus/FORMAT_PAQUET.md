# Format des paquets de parcours (format 1)

Le moteur de parcours produit, pour chaque parcours, une archive ZIP que la plateforme importe.

```
manifeste.json
etapes/carte.html
etapes/algebrique.html
…
```

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

## Import

- Par l'admin connecté : `POST /api/admin/contenus/import/` (champ `paquet`).
- Par le moteur (GitHub Actions) : même route, en-tête `Authorization: Cle-Deploiement <clé>`.
  La plateforme ne garde que l'empreinte SHA-256 de la clé (`CLE_DEPLOIEMENT_SHA256`).

Chaque import crée une nouvelle **version en brouillon**. L'admin la prévisualise, puis la publie :
la version publiée précédente est archivée. Un paquet identique au dernier importé est refusé.
