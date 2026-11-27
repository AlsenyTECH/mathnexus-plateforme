import { useEffect, useMemo, useRef } from 'react'
import { type ContexteParcours, monterComposants } from './composants'
import { monterEvaluations } from './evaluation'
import { monterFigures } from './figures'
import { rendreFormules } from './maths'
import { nettoyer } from './nettoyage'

/**
 * Affiche le HTML d'une étape et y monte les composants (formules, graphiques, évaluations).
 *
 * React ne gère que le HTML de l'étape (dangerouslySetInnerHTML, après DOMPurify) ; les
 * composants s'y greffent dans useEffect, qui s'exécute une fois le HTML dans la page. La
 * fonction renvoyée par useEffect les démonte quand on change d'étape (minuteurs arrêtés,
 * dernier temps de réponse envoyé).
 */
export function Contenu({ html, prefixeNotes, contexte = null }: {
  html: string
  prefixeNotes: string
  contexte?: ContexteParcours | null
}) {
  const ref = useRef<HTMLDivElement>(null)
  const propre = useMemo(() => nettoyer(html), [html])
  // Deux chaînes plutôt que l'objet : un objet { groupe, slug } est recréé à chaque rendu, et
  // l'effet remonterait alors les composants (chronomètre compris) à chaque rendu.
  const groupe = contexte?.groupe
  const slug = contexte?.slug

  useEffect(() => {
    const racine = ref.current
    if (!racine) return
    rendreFormules(racine)
    const demonterFigures = monterFigures(racine)
    const demonterEvaluations = monterEvaluations(racine, prefixeNotes, rendreFormules)
    const ctx = groupe && slug ? { groupe, slug } : null
    const demonterComposants = monterComposants(racine, ctx, rendreFormules)
    return () => {
      demonterFigures()
      demonterEvaluations()
      demonterComposants()
    }
  }, [propre, prefixeNotes, groupe, slug])

  return <div ref={ref} className="lbody" dangerouslySetInnerHTML={{ __html: propre }} />
}
