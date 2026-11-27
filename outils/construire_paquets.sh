#!/usr/bin/env bash
# Reconstruit les paquets préchargés (backend/contenus_initiaux/) depuis les dépôts des parcours « cahier ».
# Usage : outils/construire_paquets.sh ~/alsenytech   (dossier qui contient parcours-algebre-lineaire, mathnexus-terminale…)
set -e
cd "$(dirname "$0")/.."
A="${1:?Usage : outils/construire_paquets.sh <dossier contenant les dépôts de parcours>}"; D=backend/contenus_initiaux; C="python3 outils/convertir_parcours.py --premium-prefixe="
$C $A/parcours-algebre-lineaire/algebre-lineaire.html --slug prepa-algebre-lineaire --titre "Algèbre linéaire (ECG1)" --matiere Mathématiques --cycle prepa --description "Matrices, systèmes et espaces vectoriels, avec vidéos, exercices et évaluations." --base-url https://alsenytech.github.io/parcours-algebre-lineaire -o $D/prepa-algebre-lineaire.zip
$C $A/parcours-algebre-lineaire/suites-fonctions.html --slug prepa-suites-fonctions --titre "Suites et fonctions (ECG1)" --matiere Mathématiques --cycle prepa --description "Suites, monotonie, récurrence et fonctions usuelles." --base-url https://alsenytech.github.io/parcours-algebre-lineaire -o $D/prepa-suites-fonctions.zip
$C $A/parcours-algebre-lineaire/limites.html --slug prepa-limites-suites --titre "Limites de suites (ECG1)" --matiere Mathématiques --cycle prepa --description "Convergence, théorèmes de comparaison et suites de référence." --base-url https://alsenytech.github.io/parcours-algebre-lineaire -o $D/prepa-limites-suites.zip
$C $A/mathnexus-terminale/nombres-complexes.html --slug nombres-complexes --titre "Nombres complexes" --matiere Mathématiques --cycle lycee --base-url https://alsenytech.github.io/mathnexus-terminale -o $D/nombres-complexes.zip
$C $A/mathnexus-terminale/etude-de-fonction.html --slug etude-de-fonction --titre "Étude de fonction" --matiere Mathématiques --cycle lycee --base-url https://alsenytech.github.io/mathnexus-terminale -o $D/etude-de-fonction.zip
$C $A/mathnexus-terminale/physique/p1.html --slug physique-p1-cinematique --titre "Physique P1 — Cinématique" --matiere "Sciences physiques" --cycle lycee --base-url https://alsenytech.github.io/mathnexus-terminale/physique -o $D/physique-p1-cinematique.zip
$C $A/mathnexus-terminale/physique/p2.html --slug physique-p2-dynamique --titre "Physique P2 — Dynamique" --matiere "Sciences physiques" --cycle lycee --base-url https://alsenytech.github.io/mathnexus-terminale/physique -o $D/physique-p2-dynamique.zip
$C $A/reseaux-securite/index.html --slug reseaux-securite-s2 --titre "Réseau & Sécurité — semestre 2" --matiere "Réseaux et sécurité" --cycle universite --description "Les sujets d'exposé du semestre 2, avec vidéos et exercices." --base-url https://alsenytech.github.io/reseaux-securite -o $D/reseaux-securite-s2.zip
for n in 0 1 2 3 4; do
  case $n in 0) t="Langage et outils";; 1) t="Arithmétique, groupes, algèbre linéaire";; 2) t="Anneaux, polynômes, modules";; 3) t="Corps et corps finis";; 4) t="Les branches spécialisées";; esac
  $C $A/fondements-maths-mcs/docs/niveau-$n.html --slug mcs-fondements-niveau-$n --titre "Fondements MCS — Niveau $n : $t" --matiere Mathématiques --cycle universite --base-url https://alsenytech.github.io/fondements-maths-mcs -o $D/mcs-fondements-niveau-$n.zip
done
