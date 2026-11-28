/**
 * Annoter une copie au stylo : la photo de l'élève s'ouvre sur une toile, le prof écrit en rouge
 * (au doigt sur téléphone, à la souris sur ordinateur), puis l'image annotée est ajoutée à la correction.
 *
 * Les traits sont gardés dans une liste : « Annuler » retire le dernier, et la toile est redessinée
 * à partir de la photo à chaque changement.
 */
import { useEffect, useRef, useState, type PointerEvent } from 'react'

type Point = [number, number]
const COULEURS = { rouge: '#d11a2a', vert: '#0a7441', bleu: '#1c3bb0' }

export function AnnoterPhoto({ url, fermer, enregistrer }: {
  url: string; fermer: () => void; enregistrer: (image: Blob) => Promise<void>
}) {
  const toile = useRef<HTMLCanvasElement>(null)
  const image = useRef<HTMLImageElement | null>(null)
  const [traits, setTraits] = useState<{ couleur: string; points: Point[] }[]>([])
  const enCours = useRef<{ couleur: string; points: Point[] } | null>(null)
  const [couleur, setCouleur] = useState(COULEURS.rouge)
  const [etat, setEtat] = useState<'chargement' | 'pret' | 'envoi' | 'erreur'>('chargement')

  // Charger la photo (même origine : la toile reste exportable).
  useEffect(() => {
    const img = new Image()
    img.onload = () => {
      image.current = img
      const c = toile.current
      if (!c) return
      const echelle = Math.min(1, 1600 / Math.max(img.naturalWidth, img.naturalHeight))
      c.width = Math.round(img.naturalWidth * echelle)
      c.height = Math.round(img.naturalHeight * echelle)
      setEtat('pret')
    }
    img.onerror = () => setEtat('erreur')
    img.src = url
  }, [url])

  // Redessiner la photo et tous les traits.
  useEffect(() => {
    const c = toile.current
    const ctx = c?.getContext('2d')
    if (!c || !ctx || !image.current) return
    ctx.drawImage(image.current, 0, 0, c.width, c.height)
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.lineWidth = Math.max(3, c.width / 300)
    for (const t of traits) {
      ctx.strokeStyle = t.couleur
      ctx.beginPath()
      t.points.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)))
      ctx.stroke()
    }
  }, [traits, etat])

  function position(e: PointerEvent<HTMLCanvasElement>): Point {
    const c = e.currentTarget
    const r = c.getBoundingClientRect()
    return [((e.clientX - r.left) * c.width) / r.width, ((e.clientY - r.top) * c.height) / r.height]
  }

  function debut(e: PointerEvent<HTMLCanvasElement>) {
    e.currentTarget.setPointerCapture(e.pointerId)
    enCours.current = { couleur, points: [position(e)] }
  }

  function bouger(e: PointerEvent<HTMLCanvasElement>) {
    const t = enCours.current
    const ctx = e.currentTarget.getContext('2d')
    if (!t || !ctx) return
    const [x0, y0] = t.points[t.points.length - 1]
    const [x, y] = position(e)
    t.points.push([x, y])
    ctx.strokeStyle = t.couleur
    ctx.beginPath()
    ctx.moveTo(x0, y0)
    ctx.lineTo(x, y)
    ctx.stroke()
  }

  function fin() {
    const t = enCours.current
    enCours.current = null
    if (t && t.points.length > 1) setTraits((ts) => [...ts, t])
  }

  async function valider() {
    const c = toile.current
    if (!c) return
    setEtat('envoi')
    const blob = await new Promise<Blob | null>((ok) => c.toBlob(ok, 'image/jpeg', 0.85))
    if (!blob) return setEtat('erreur')
    try {
      await enregistrer(blob)
    } catch {
      setEtat('erreur')
    }
  }

  return (
    <div className="annotation" role="dialog" aria-modal="true" aria-label="Annoter la copie">
      <div className="annotation-barre">
        {Object.entries(COULEURS).map(([nom, valeur]) => (
          <button key={nom} type="button" className={`pastille${couleur === valeur ? ' active' : ''}`}
            style={{ background: valeur }} aria-label={`Stylo ${nom}`} onClick={() => setCouleur(valeur)} />
        ))}
        <button type="button" className="btn ghost petit" disabled={!traits.length} onClick={() => setTraits((t) => t.slice(0, -1))}>Annuler le trait</button>
        <button type="button" className="btn ghost petit" disabled={!traits.length} onClick={() => setTraits([])}>Tout effacer</button>
        <span className="espace" />
        <button type="button" className="btn ghost petit" onClick={fermer}>Fermer</button>
        <button type="button" className="btn petit" disabled={etat !== 'pret' || !traits.length} onClick={() => void valider()}>
          {etat === 'envoi' ? 'Envoi…' : 'Ajouter à la correction'}
        </button>
      </div>
      {etat === 'chargement' && <p className="discret">Chargement de la photo…</p>}
      {etat === 'erreur' && <p className="erreur">La photo n'a pas pu être chargée ou envoyée.</p>}
      <canvas ref={toile} className="annotation-toile" onPointerDown={debut} onPointerMove={bouger} onPointerUp={fin} onPointerCancel={fin} />
    </div>
  )
}
