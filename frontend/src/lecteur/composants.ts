import { api, ErreurApi } from '../api/client'
import { monter as monterEvaluation, type Services } from '../partages/evaluation.js'
import '../partages/evaluation.css'
import { nettoyer } from './nettoyage'

/**
 * Le registre des composants : chaque <… data-composant="nom"> d'une étape reçoit le module
 * qui le fait vivre, avec l'interface commune monter(element, donnees, services) → demonter.
 *
 * Les composants partagés (src/partages/) ne savent rien de la plateforme : c'est ici qu'on leur
 * branche l'API. Les autres valeurs de data-composant (qcm, atelier, animateur, mesure, sage,
 * venus des paquets au format 1) restent sous leur forme statique ; « bouton » et « case »
 * relèvent des évaluations à barème (evaluation.ts).
 */

/** Où se trouve l'étape affichée : nécessaire pour retrouver ses évaluations sur le serveur. */
export interface ContexteParcours {
  groupe: string
  slug: string
}

/** Les services de l'évaluation, branchés sur l'API Django (réponses gardées sur le serveur). */
export function servicesEvaluation(contexte: ContexteParcours, rendre: (el: HTMLElement) => void): Services {
  const base = `groupes/${contexte.groupe}/parcours/${contexte.slug}/evaluations`
  return {
    charger: (cle) => api.get(`${base}/${cle}/`),
    commencer: (cle) => api.post(`${base}/${cle}/tentatives/`),
    reprendre: (id) => api.get(`tentatives/${id}/`),
    repondre: (id, question, choix, temps_ms) => api.put(`tentatives/${id}/reponses/${question}/`, { choix, temps_ms }),
    terminer: (id, temps) => api.post(`tentatives/${id}/terminer/`, { temps }),
    nettoyer,
    rendre,
    // 409 : la tentative est déjà terminée (échéance passée, ou terminée dans un autre onglet)
    estClose: (erreur) => erreur instanceof ErreurApi && erreur.statut === 409,
  }
}

/** Monte les composants d'une étape. Sans contexte (aperçu, vitrine), l'évaluation est seulement annoncée. */
export function monterComposants(
  racine: HTMLElement,
  contexte: ContexteParcours | null,
  rendre: (el: HTMLElement) => void,
): () => void {
  const demontages: (() => void)[] = []
  racine.querySelectorAll<HTMLElement>('[data-composant="evaluation"]').forEach((element) => {
    const cle = element.dataset.cle ?? ''
    if (!contexte) {
      element.className = 'evd'
      element.textContent = 'Évaluation : elle se passe depuis la classe, une fois connecté.'
      return
    }
    demontages.push(monterEvaluation(element, { cle }, servicesEvaluation(contexte, rendre)))
  })
  return () => demontages.forEach((demonter) => demonter())
}
