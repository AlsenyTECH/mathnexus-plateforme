import { useEffect, useMemo, useRef } from 'react'
import { monterEvaluations } from './evaluation'
import { monterFigures } from './figures'
import { rendreFormules } from './maths'
import { nettoyer } from './nettoyage'

/** Affiche le HTML d'une étape et y monte les composants (formules, graphiques, évaluations). */
export function Contenu({ html, prefixeNotes }: { html: string; prefixeNotes: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const propre = useMemo(() => nettoyer(html), [html])

  useEffect(() => {
    const racine = ref.current
    if (!racine) return
    rendreFormules(racine)
    const demonterFigures = monterFigures(racine)
    const demonterEvaluations = monterEvaluations(racine, prefixeNotes, rendreFormules)
    return () => {
      demonterFigures()
      demonterEvaluations()
    }
  }, [propre, prefixeNotes])

  return <div ref={ref} className="lbody" dangerouslySetInnerHTML={{ __html: propre }} />
}
