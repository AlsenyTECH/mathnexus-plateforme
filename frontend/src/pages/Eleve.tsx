import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ErreurApi } from '../api/client'
import type { EtapeLue, EtapeSommaire, Groupe, ResumeParcours, Sommaire } from '../api/types'
import { BarreAvancement, Cadre, Chargement, MessageErreur, useDonnees } from '../composants/communs'
import { Contenu } from '../lecteur/Contenu'
import { useSession } from '../session'
import { etapeAReprendre, numeroterEtapes } from '../utilitaires'
import { MesDevoirs } from './Devoirs'
import { SeanceDuJour } from './Suivi'

const RAISONS: Record<string, string> = {
  premium: 'Offre Premium',
  pas_encore_ouverte: 'Pas encore ouverte',
}

export function TableauDeBordClasse() {
  const { groupe = '' } = useParams()
  const g = useDonnees(() => api.get<Groupe>(`groupes/${groupe}/`), [groupe])
  const parcours = useDonnees(() => api.get<ResumeParcours[]>(`groupes/${groupe}/parcours/`), [groupe])
  return (
    <Cadre titre={g.donnees ? `${g.donnees.nom} · ${g.donnees.annee_libelle}` : undefined}>
      {(g.chargement || parcours.chargement) && <Chargement />}
      <MessageErreur erreur={g.erreur ?? parcours.erreur} />
      <SeanceDuJour groupe={groupe} />
      <MesDevoirs groupe={groupe} />
      <h2>Mes parcours</h2>
      {parcours.donnees?.length === 0 && <p className="encart">Aucun parcours n'est encore ouvert dans ta classe.</p>}
      <ul className="liste-cartes">
        {parcours.donnees?.map((p) => (
          <li key={p.slug}>
            <Link className="carte-parcours" to={`/classe/${groupe}/${p.slug}`}>
              <span className="carte-matiere">{p.matiere}</span>
              <strong>{p.titre}</strong>
              {p.description && <span className="carte-desc">{p.description}</span>}
              <BarreAvancement {...p.avancement} />
            </Link>
          </li>
        ))}
      </ul>
    </Cadre>
  )
}

function LigneEtape({ e, numero, href, actuelle }: { e: EtapeSommaire; numero: number; href: string; actuelle?: boolean }) {
  const classes = [e.validee ? 'done' : '', e.accessible ? '' : 'verrou'].join(' ')
  const contenu = (
    <>
      <span className="nav-n">{e.validee ? '✓' : e.accessible ? numero : '·'}</span>
      <span>
        {e.titre}
        {!e.accessible && e.raison && <em className="etape-raison"> · {RAISONS[e.raison]}</em>}
      </span>
    </>
  )
  return (
    <li>
      {e.accessible ? (
        <Link to={href} className={classes} aria-current={actuelle ? 'page' : undefined}>
          {contenu}
        </Link>
      ) : (
        <span className={`nav-verrou ${classes}`} aria-disabled="true">
          {contenu}
        </span>
      )}
    </li>
  )
}

function ListeEtapes({ s, groupe, actuelle }: { s: Sommaire; groupe: string; actuelle?: string }) {
  const numeros = numeroterEtapes(s)
  return (
    <>
      {s.parties.map((p) => (
        <div key={p.cle}>
          <p className="nav-part">{p.titre}</p>
          <ol className="nav-list">
            {p.etapes.map((e) => (
              <LigneEtape key={e.cle} e={e} numero={numeros[e.cle]} actuelle={e.cle === actuelle}
                href={`/classe/${groupe}/${s.slug}/${e.cle}`} />
            ))}
          </ol>
        </div>
      ))}
    </>
  )
}

export function SommaireParcours() {
  const { groupe = '', slug = '' } = useParams()
  const { donnees: s, erreur, chargement } = useDonnees(() => api.get<Sommaire>(`groupes/${groupe}/parcours/${slug}/`), [groupe, slug])
  const reprendre = s ? etapeAReprendre(s) : null
  return (
    <Cadre titre={s?.titre}>
      {chargement && <Chargement />}
      <MessageErreur erreur={erreur} />
      {s && (
        <div className="sommaire">
          <p className="fil">
            <Link to={`/classe/${groupe}`}>← Ma classe</Link>
          </p>
          <BarreAvancement {...s.avancement} />
          {reprendre && (
            <Link className="btn" to={`/classe/${groupe}/${slug}/${reprendre}`}>
              {s.avancement.validees ? 'Reprendre' : 'Commencer le parcours'} →
            </Link>
          )}
          <nav aria-label="Sommaire du parcours" className="sommaire-liste">
            <ListeEtapes s={s} groupe={groupe} />
          </nav>
        </div>
      )}
    </Cadre>
  )
}

export function LecteurEtape() {
  const { groupe = '', slug = '', cle = '' } = useParams()
  const { session } = useSession()
  const naviguer = useNavigate()
  // Le menu mobile se referme tout seul quand on change d'étape : il est « ouvert pour » une étape.
  const [menuPour, setMenuPour] = useState<string | null>(null)
  const menuOuvert = menuPour === cle
  const setMenuOuvert = (ouvert: boolean) => setMenuPour(ouvert ? cle : null)
  const sommaire = useDonnees(() => api.get<Sommaire>(`groupes/${groupe}/parcours/${slug}/`), [groupe, slug])
  const etape = useDonnees(() => api.get<EtapeLue>(`groupes/${groupe}/parcours/${slug}/etapes/${cle}/`), [groupe, slug, cle])
  const [validation, setValidation] = useState(false)

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [cle])

  const e = etape.donnees
  const s = sommaire.donnees
  const erreurEtape = etape.erreur instanceof ErreurApi ? etape.erreur : null

  async function compris() {
    if (!e) return
    setValidation(true)
    try {
      await api.post(`groupes/${groupe}/parcours/${slug}/etapes/${cle}/valider/`)
      sommaire.recharger()
      naviguer(e.suivante ? `/classe/${groupe}/${slug}/${e.suivante}` : `/classe/${groupe}/${slug}`)
    } finally {
      setValidation(false)
    }
  }

  return (
    <div className="app">
      <div className="topbar">
        <button type="button" className="btn ghost" aria-controls="side" aria-expanded={menuOuvert}
          onClick={() => setMenuOuvert(!menuOuvert)}>
          Sommaire
        </button>
        <div className="tb-mid">
          <img src="/logo.svg" alt="" />
          <p className="brand">{s?.titre}</p>
        </div>
        <p className="mini">{s ? `${s.avancement.validees} / ${s.avancement.total}` : ''}</p>
      </div>
      {menuOuvert && <div className="scrim" onClick={() => setMenuOuvert(false)} />}
      <nav className={`side${menuOuvert ? ' open' : ''}`} id="side" aria-label="Sommaire du parcours">
        <div className="brand-row">
          <img src="/logo.svg" alt="Logo Mathnexus" />
          <div>
            <p className="brand">{s?.titre ?? '…'}</p>
            <p className="brand-sub">
              <Link to={`/classe/${groupe}`}>← Ma classe</Link>
            </p>
          </div>
        </div>
        {s && <BarreAvancement {...s.avancement} />}
        {s && <ListeEtapes s={s} groupe={groupe} actuelle={cle} />}
      </nav>
      <main className="main">
        {etape.chargement && <Chargement />}
        {erreurEtape && (
          <section className="lesson">
            <div className="encart">
              <p>{erreurEtape.message}</p>
              <Link className="btn ghost" to={`/classe/${groupe}/${slug}`}>Retour au sommaire</Link>
            </div>
          </section>
        )}
        {e && !etape.chargement && (
          <section className="lesson">
            <header className="lhead">
              <p className="eyebrow">
                {e.partie}
                {e.duree_min && <span className="meta">{e.duree_min} min</span>}
              </p>
              <h2>{e.titre}</h2>
            </header>
            <Contenu html={e.html} prefixeNotes={`note:${session?.utilisateur.id}:${slug}`} contexte={{ groupe, slug }} />
          </section>
        )}
        {e && !etape.chargement && (
          <div className="pager">
            {e.precedente ? (
              <Link className="btn ghost" to={`/classe/${groupe}/${slug}/${e.precedente}`}>← Étape précédente</Link>
            ) : <span />}
            <div className="right">
              {e.validee && <p className="done-note">Étape validée</p>}
              <button type="button" className="btn" onClick={() => void compris()} disabled={validation}>
                {e.suivante ? "J'ai compris, étape suivante →" : "J'ai compris, fin du parcours"}
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
