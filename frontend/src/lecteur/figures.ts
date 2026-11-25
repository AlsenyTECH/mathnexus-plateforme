import * as complexes from './figures-complexes'
import * as fonctions from './figures-fonctions'

interface Moteur {
  FIG: Record<string, unknown>
  Graph: new (el: HTMLElement) => { cfg?: unknown; render: () => void }
}

const MOTEURS: Moteur[] = [complexes as unknown as Moteur, fonctions as unknown as Moteur]

export function figuresConnues(): string[] {
  return MOTEURS.flatMap((m) => Object.keys(m.FIG))
}

/**
 * Monte les graphiques interactifs d'une étape : chaque <div class="graph" data-fig="…">
 * reçoit le moteur qui connaît cette figure. Renvoie la fonction de nettoyage.
 */
export function monterFigures(racine: HTMLElement): () => void {
  const graphes: { render: () => void }[] = []
  racine.querySelectorAll<HTMLElement>('.graph[data-fig]').forEach((el) => {
    const nom = el.dataset.fig ?? ''
    const moteur = MOTEURS.find((m) => Object.prototype.hasOwnProperty.call(m.FIG, nom))
    if (!moteur) {
      el.textContent = `Graphique « ${nom} » pas encore disponible dans l'application.`
      el.classList.add('graph-absent')
      return
    }
    const g = new moteur.Graph(el)
    if (g.cfg) graphes.push(g)
  })
  const redessiner = () => graphes.forEach((g) => g.render())
  // Le canevas mesure sa taille au rendu : on attend que l'étape soit affichée.
  const image = requestAnimationFrame(redessiner)
  // Absent des très vieux navigateurs : on redessine alors seulement au chargement et au thème.
  const observateur = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(redessiner)
  observateur?.observe(racine)
  const theme = window.matchMedia?.('(prefers-color-scheme: dark)')
  theme?.addEventListener?.('change', redessiner)
  return () => {
    cancelAnimationFrame(image)
    observateur?.disconnect()
    theme?.removeEventListener?.('change', redessiner)
  }
}
