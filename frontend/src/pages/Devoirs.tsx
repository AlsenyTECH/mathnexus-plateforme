/**
 * Les devoirs : le prof donne du travail et corrige, l'élève rend sa copie et lit sa correction.
 *
 * Côté élève : <MesDevoirs> (sur le tableau de bord de la classe) et <PageDevoirEleve>.
 * Côté prof : <DevoirsDeLaClasse> (dans la page de la classe), <SuiviDevoir>, <CorrigerCopie>
 * et <ACorriger> (en tête de « Mes classes »).
 *
 * Toutes les règles d'accès sont sur le serveur : ces pages n'affichent que ce qu'il renvoie.
 */
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ErreurApi } from '../api/client'
import type {
  CopieACorriger, CopieEleve, DevoirEleve, DevoirProf, EtatDevoir, EvaluationResume, Membre, PhotoCopie,
  PieceJointe, Rendu, ResumeParcours, Sommaire, StatutDevoir, SuiviDevoir, TypeDevoir,
} from '../api/types'
import { Cadre, Chargement, MessageErreur, useDonnees } from '../composants/communs'
import { rendreFormules } from '../lecteur/maths'
import { adresse, compresserImage, lienWhatsApp } from '../utilitaires'
import { AnnoterPhoto } from './Annotation'

// --- Petits morceaux communs ------------------------------------------------------------

const LIBELLES: Record<StatutDevoir, string> = {
  a_faire: 'À faire',
  en_retard: 'En retard',
  rendu: 'Rendu, en attente de correction',
  fait: 'Fait',
  corrige: 'Corrigé',
}

const CLASSES_BADGE: Record<StatutDevoir, string> = {
  a_faire: 'badge soon',
  en_retard: 'badge retard',
  rendu: 'badge attente',
  fait: 'badge ok',
  corrige: 'badge ok',
}

export function BadgeStatut({ statut }: { statut: StatutDevoir }) {
  return <span className={CLASSES_BADGE[statut]}>{LIBELLES[statut]}</span>
}

const TYPES: Record<TypeDevoir, string> = { etape: 'Étape', evaluation: 'Évaluation', libre: 'Travail' }

export function dateCourte(iso: string | null): string {
  if (!iso) return 'sans date limite'
  return new Date(iso).toLocaleString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

/** La note à afficher : celle du prof si elle existe, sinon le score de l'évaluation. */
function resultat(e: EtatDevoir, noteSur: number): string | null {
  if (e.note !== null) return `${e.note} / ${noteSur}`
  if (e.score !== null && e.total !== null) return `${e.score} / ${e.total}`
  return null
}

/**
 * Un texte écrit par le prof ou l'élève, affiché tel quel (retours à la ligne gardés, aucun HTML) ;
 * les formules entre \( … \) ou \[ … \] sont mises en forme par KaTeX. Le texte est inséré comme
 * texte (jamais comme HTML) : KaTeX ne fait que remplacer les formules qu'il reconnaît.
 */
export function TexteLibre({ texte }: { texte: string }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (ref.current) {
      ref.current.textContent = texte
      rendreFormules(ref.current)
    }
  }, [texte])
  return <div ref={ref} className="texte-libre" />
}

/** Le sujet joint : les photos s'affichent, les PDF s'ouvrent dans un nouvel onglet. */
function Pieces({ pieces, supprimer }: { pieces: PieceJointe[]; supprimer?: (p: PieceJointe) => void }) {
  if (!pieces.length) return null
  return (
    <ul className="pieces">
      {pieces.map((p) => (
        <li key={p.id}>
          {p.type_mime.startsWith('image/') ? (
            <a href={p.url} target="_blank" rel="noreferrer"><img src={p.url} alt={p.nom || 'Sujet'} loading="lazy" /></a>
          ) : (
            <a className="btn ghost" href={p.url} target="_blank" rel="noreferrer">📄 {p.nom || 'Sujet (PDF)'}</a>
          )}
          {supprimer && <button type="button" className="btn ghost petit" onClick={() => supprimer(p)}>Retirer</button>}
        </li>
      ))}
    </ul>
  )
}

/** Le temps qui reste avant `fin`, mis à jour chaque seconde. */
function Chronometre({ fin }: { fin: string }) {
  const [maintenant, setMaintenant] = useState(() => Date.now())
  useEffect(() => {
    const t = window.setInterval(() => setMaintenant(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [])
  const reste = Math.max(0, new Date(fin).getTime() - maintenant)
  const min = Math.floor(reste / 60_000)
  const sec = Math.floor((reste % 60_000) / 1000)
  return (
    <p className={`chronometre${reste < 120_000 ? ' presque' : ''}`} role="timer">
      {reste > 0 ? `Temps restant : ${min} min ${String(sec).padStart(2, '0')} s` : 'Temps écoulé : envoie ta copie maintenant.'}
    </p>
  )
}

/** Le message WhatsApp qui annonce un devoir à la classe. */
function messageDevoir(d: { titre: string; date_limite: string | null; groupe: string; id: string; duree_min: number | null }) {
  return `📚 Nouveau travail : ${d.titre}${d.duree_min ? ` (chronométré, ${d.duree_min} min)` : ''}\n` +
    `À rendre pour ${dateCourte(d.date_limite)}.\n${adresse(`/classe/${d.groupe}/devoirs/${d.id}`)}`
}

function Galerie({ photos, supprimer, annoter }: {
  photos: PhotoCopie[]; supprimer?: (p: PhotoCopie) => void; annoter?: (p: PhotoCopie) => void
}) {
  if (!photos.length) return null
  return (
    <ul className="galerie">
      {photos.map((p) => (
        <li key={p.id}>
          <a href={p.url} target="_blank" rel="noreferrer">
            <img src={p.url} alt="Photo de la copie" loading="lazy" />
          </a>
          {annoter && (
            <button type="button" className="btn petit" onClick={() => annoter(p)}>Annoter au stylo</button>
          )}
          {supprimer && (
            <button type="button" className="btn ghost petit" onClick={() => supprimer(p)}>Retirer</button>
          )}
        </li>
      ))}
    </ul>
  )
}

/** Envoie une ou plusieurs photos, une à une, après les avoir réduites (moins de données mobiles). */
function AjoutPhotos({ url, apres, libelle = 'Ajouter des photos de ta copie' }: {
  url: string; apres: (r: { rendu: Rendu }) => void; libelle?: string
}) {
  const [envoi, setEnvoi] = useState('')
  const [erreur, setErreur] = useState<Error | null>(null)

  async function choisir(fichiers: FileList | null) {
    if (!fichiers?.length) return
    setErreur(null)
    try {
      const liste = Array.from(fichiers)
      for (const [i, fichier] of liste.entries()) {
        setEnvoi(`Envoi de la photo ${i + 1} sur ${liste.length}…`)
        const donnees = new FormData()
        donnees.append('photo', await compresserImage(fichier), 'copie.jpg')
        apres(await api.post<{ rendu: Rendu }>(url, donnees))
      }
    } catch (e) {
      setErreur(e as Error)
    } finally {
      setEnvoi('')
    }
  }

  return (
    <div className="ajout-photos">
      <label className="btn ghost">
        {libelle}
        <input type="file" accept="image/*" multiple hidden onChange={(e) => {
          void choisir(e.target.files)
          e.target.value = ''
        }} />
      </label>
      {envoi && <span className="discret"> {envoi}</span>}
      <MessageErreur erreur={erreur} />
    </div>
  )
}

/** Le lien vers ce qu'il faut faire dans un parcours (étape ou évaluation). */
function LienTravail({ d }: { d: { groupe: string; parcours: string | null; cle_etape: string | null; type: TypeDevoir; parcours_titre: string | null } }) {
  if (!d.parcours || !d.cle_etape) return null
  return (
    <p>
      <Link className="btn" to={`/classe/${d.groupe}/${d.parcours}/${d.cle_etape}`}>
        {d.type === 'evaluation' ? "Passer l'évaluation" : "Ouvrir l'étape"}
      </Link>
      <span className="discret"> · {d.parcours_titre}</span>
    </p>
  )
}

// --- L'élève ----------------------------------------------------------------------------

/** La liste des devoirs d'une classe, sur le tableau de bord de l'élève. */
export function MesDevoirs({ groupe }: { groupe: string }) {
  const { donnees, erreur, chargement } = useDonnees(
    () => api.get<(DevoirEleve)[]>(`mes-devoirs/?groupe=${groupe}`), [groupe],
  )
  if (chargement) return <Chargement texte="Chargement de tes devoirs…" />
  if (erreur) return <MessageErreur erreur={erreur} />
  const enCours = donnees?.filter((d) => d.statut === 'a_faire' || d.statut === 'en_retard') ?? []
  const autres = donnees?.filter((d) => !enCours.includes(d)) ?? []
  return (
    <section className="bloc-devoirs">
      <h2>Mes devoirs</h2>
      {!donnees?.length && <p className="discret">Aucun devoir pour l'instant.</p>}
      <ul className="liste-devoirs">
        {[...enCours, ...autres.slice(0, 8)].map((d) => (
          <li key={d.id}>
            <Link to={`/classe/${groupe}/devoirs/${d.id}`} className="ligne-devoir">
              <span className="ligne-devoir-titre">
                <span className="discret">{TYPES[d.type]} · </span>{d.titre}
              </span>
              <span className="ligne-devoir-infos">
                <BadgeStatut statut={d.statut} />
                {resultat(d, d.note_sur) && <strong> {resultat(d, d.note_sur)}</strong>}
                <span className="discret"> · pour {dateCourte(d.date_limite)}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** Un devoir vu par l'élève : la consigne, sa copie (texte + photos), puis sa correction. */
export function PageDevoirEleve() {
  const { groupe = '', devoir = '' } = useParams()
  const charge = useDonnees(() => api.get<DevoirEleve>(`devoirs/${devoir}/`), [devoir])
  const [d, setD] = useState<DevoirEleve | null>(null)
  const actuel = d ?? charge.donnees ?? null
  const [texte, setTexte] = useState<string | null>(null)
  const [erreur, setErreur] = useState<Error | null>(null)
  const [message, setMessage] = useState('')

  function mettreAJour(r: { rendu: Rendu | null } & Partial<EtatDevoir>) {
    if (actuel) setD({ ...actuel, ...r })
  }

  async function enregistrer(envoyer: boolean) {
    setErreur(null)
    setMessage('')
    try {
      const r = await api.post<EtatDevoir & { rendu: Rendu }>(`devoirs/${devoir}/rendu/`, {
        texte: texte ?? actuel?.rendu?.texte ?? '', envoyer,
      })
      mettreAJour(r)
      setMessage(envoyer ? 'Ta copie est envoyée à ton prof.' : 'Brouillon enregistré.')
    } catch (e) {
      setErreur(e as Error)
    }
  }

  async function commencer() {
    setErreur(null)
    try {
      setD(await api.post<DevoirEleve>(`devoirs/${devoir}/commencer/`))
    } catch (e) {
      setErreur(e as Error)
    }
  }

  async function retirer(p: PhotoCopie) {
    await api.delete(`photos/${p.id}/`)
    if (actuel?.rendu) mettreAJour({ rendu: { ...actuel.rendu, photos: actuel.rendu.photos.filter((x) => x.id !== p.id) } })
  }

  if (!actuel) return <Cadre><Chargement /><MessageErreur erreur={charge.erreur} /></Cadre>
  const corrige = actuel.statut === 'corrige'
  const r = actuel.rendu
  return (
    <Cadre titre={actuel.titre}>
      <p className="fil"><Link to={`/classe/${groupe}`}>← Ma classe</Link></p>
      <p>
        <BadgeStatut statut={actuel.statut} /> <span className="discret">À rendre pour {dateCourte(actuel.date_limite)}</span>
      </p>
      {actuel.sujet_masque ? (
        <section className="encart commencer">
          <h2>Évaluation chronométrée : {actuel.duree_min} min</h2>
          <p>Le sujet apparaît quand tu cliques sur « Commencer », et le chronomètre démarre. Installe-toi au calme, avec ta copie et ton stylo.</p>
          <button type="button" className="btn" onClick={() => void commencer()}>Commencer</button>
          <MessageErreur erreur={erreur} />
        </section>
      ) : (
        <>
          {actuel.fin_prevue && actuel.statut !== 'corrige' && !actuel.rendu_le && <Chronometre fin={actuel.fin_prevue} />}
          {(actuel.consigne || actuel.pieces.length > 0) && (
            <section className="encart">
              <h2>Sujet</h2>
              {actuel.consigne && <TexteLibre texte={actuel.consigne} />}
              <Pieces pieces={actuel.pieces} />
            </section>
          )}
        </>
      )}
      <LienTravail d={actuel} />
      {actuel.type === 'evaluation' && actuel.score !== null && (
        <p className="encart">Évaluation terminée : <strong>{actuel.score} / {actuel.total}</strong>. La correction détaillée est dans l'étape.</p>
      )}

      {corrige && r && (
        <section className="encart correction">
          <h2>Ta correction</h2>
          {r.note !== null && <p className="note-grande">{r.note} / {actuel.note_sur}</p>}
          {r.commentaire && <><h3>Le mot du prof</h3><TexteLibre texte={r.commentaire} /></>}
          {r.correction && <><h3>Correction</h3><TexteLibre texte={r.correction} /></>}
          <Galerie photos={r.photos_correction} />
        </section>
      )}

      {!actuel.sujet_masque && <section>
        <h2>Ma copie</h2>
        {corrige ? (
          <>
            {r?.texte && <TexteLibre texte={r.texte} />}
            <Galerie photos={r?.photos ?? []} />
          </>
        ) : (
          <>
            <textarea
              className="zone-copie" rows={8} placeholder="Écris ta réponse ici, ou ajoute des photos de ta copie."
              value={texte ?? r?.texte ?? ''} onChange={(e) => setTexte(e.target.value)}
            />
            <Galerie photos={r?.photos ?? []} supprimer={retirer} />
            <AjoutPhotos url={`devoirs/${devoir}/rendu/photos/`} apres={(x) => mettreAJour(x)} />
            <div className="actions">
              <button type="button" className="btn ghost" onClick={() => void enregistrer(false)}>Enregistrer le brouillon</button>
              <button type="button" className="btn" onClick={() => void enregistrer(true)}>
                {r?.rendu_le ? 'Renvoyer ma copie' : 'Envoyer à mon prof'}
              </button>
            </div>
            {r?.rendu_le && <p className="discret">Envoyée le {dateCourte(r.rendu_le)}. Tu peux encore la modifier tant qu'elle n'est pas corrigée.</p>}
          </>
        )}
        {message && <p className="succes" role="status">{message}</p>}
        {actuel.hors_temps && <p className="discret">Copie envoyée après la fin du temps.</p>}
        <MessageErreur erreur={erreur} />
      </section>}
    </Cadre>
  )
}

// --- Le prof ------------------------------------------------------------------------------

/** Ce soir 23 h 59, au format attendu par <input type="datetime-local">. */
function ceSoir(): string {
  const d = new Date()
  const deux = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${deux(d.getMonth() + 1)}-${deux(d.getDate())}T23:59`
}

/** Le formulaire « Donner du travail » : à toute la classe ou à un élève. */
function DonnerDuTravail({ groupe, eleves, parcours, apres }: {
  groupe: string; eleves: Membre[]; parcours: ResumeParcours[]; apres: () => void
}) {
  const [type, setType] = useState<TypeDevoir>('libre')
  const [slug, setSlug] = useState('')
  const sommaire = useDonnees(
    () => (slug && type === 'etape' ? api.get<Sommaire>(`groupes/${groupe}/parcours/${slug}/`) : Promise.resolve(null)),
    [groupe, slug, type],
  )
  const evaluations = useDonnees(
    () => (slug && type === 'evaluation' ? api.get<EvaluationResume[]>(`groupes/${groupe}/parcours/${slug}/evaluations/`) : Promise.resolve([])),
    [groupe, slug, type],
  )
  const [erreur, setErreur] = useState<Error | null>(null)
  const [envoi, setEnvoi] = useState(false)
  const [fichiers, setFichiers] = useState<File[]>([])

  async function donner(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const formulaire = e.currentTarget
    const f = new FormData(formulaire)
    const limite = String(f.get('date_limite') || '')
    setErreur(null)
    setEnvoi(true)
    try {
      const cree = await api.post<{ id: string }>(`groupes/${groupe}/devoirs/`, {
        type,
        titre: f.get('titre') || '',
        consigne: f.get('consigne') || '',
        eleve: f.get('eleve') || null,
        parcours: slug || null,
        cle_etape: f.get('cle_etape') || '',
        cle_evaluation: f.get('cle_evaluation') || '',
        // La date saisie est en heure locale : on l'envoie avec son fuseau.
        date_limite: limite ? new Date(limite).toISOString() : null,
        note_sur: f.get('note_sur') || undefined,
        duree_min: f.get('duree_min') ? Number(f.get('duree_min')) : null,
      })
      for (const fichier of fichiers) {
        const donnees = new FormData()
        if (fichier.type.startsWith('image/')) donnees.append('fichier', await compresserImage(fichier), fichier.name.replace(/\.\w+$/, '.jpg'))
        else donnees.append('fichier', fichier, fichier.name)
        await api.post(`devoirs/${cree.id}/sujet/`, donnees)
      }
      setFichiers([])
      formulaire.reset()
      setSlug('')
      apres()
    } catch (err) {
      setErreur(err instanceof ErreurApi ? new Error(Object.values(err.champs()).join(' ') || err.message) : (err as Error))
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <form className="encart formulaire-devoir" onSubmit={donner}>
      <h3>Donner du travail</h3>
      <div className="grille-2">
        <label className="champ">Pour
          <select name="eleve" defaultValue="">
            <option value="">Toute la classe</option>
            {eleves.map((m) => <option key={m.utilisateur} value={m.utilisateur}>{m.prenom} {m.nom}</option>)}
          </select>
        </label>
        <label className="champ">Type
          <select name="type" value={type} onChange={(e) => setType(e.target.value as TypeDevoir)}>
            <option value="libre">Travail libre (exercices, copie)</option>
            <option value="etape">Une étape d'un parcours</option>
            <option value="evaluation">Une évaluation (corrigée automatiquement)</option>
          </select>
        </label>
      </div>
      {type !== 'libre' && (
        <div className="grille-2">
          <label className="champ">Parcours
            <select name="parcours" value={slug} onChange={(e) => setSlug(e.target.value)} required>
              <option value="">Choisir…</option>
              {parcours.map((p) => <option key={p.slug} value={p.slug}>{p.titre}</option>)}
            </select>
          </label>
          {type === 'etape' && (
            <label className="champ">Étape
              <select name="cle_etape" required disabled={!sommaire.donnees}>
                {sommaire.donnees?.parties.map((p) => (
                  <optgroup key={p.cle} label={p.titre}>
                    {p.etapes.map((e) => <option key={e.cle} value={e.cle}>{e.titre}</option>)}
                  </optgroup>
                ))}
              </select>
            </label>
          )}
          {type === 'evaluation' && (
            <label className="champ">Évaluation
              <select name="cle_evaluation" required disabled={!evaluations.donnees?.length}>
                {evaluations.donnees?.map((e) => (
                  <option key={e.cle} value={e.cle}>{e.titre}{e.duree_min ? ` (${e.duree_min} min)` : ''}</option>
                ))}
              </select>
              {slug && evaluations.donnees?.length === 0 && (
                <span className="champ-aide">Ce parcours n'a pas encore d'évaluation enregistrée : donne plutôt l'étape, ou un travail libre.</span>
              )}
            </label>
          )}
        </div>
      )}
      <label className="champ">Titre{type !== 'libre' && <span className="champ-aide"> (facultatif : celui de l'étape par défaut)</span>}
        <input name="titre" required={type === 'libre'} placeholder="Ex. : Évaluation du jour — produit de matrices" />
      </label>
      <label className="champ">Consigne ou énoncé
        <textarea name="consigne" rows={4} placeholder="Les exercices à faire. Formules : \\( x^2 \\) dans la ligne, \\[ \\int_0^1 f \\] à part." />
      </label>
      <label className="champ">Sujet en photo ou en PDF <span className="champ-aide">(facultatif : exercices photographiés, fiche de TD)</span>
        <input type="file" accept="image/*,application/pdf" multiple onChange={(e) => setFichiers(Array.from(e.target.files ?? []))} />
      </label>
      <div className="grille-2">
        <label className="champ">À rendre pour
          <input type="datetime-local" name="date_limite" defaultValue={ceSoir()} />
        </label>
        <label className="champ">Noté sur
          <input type="number" name="note_sur" min={1} max={1000} step="0.5" placeholder="20" />
        </label>
      </div>
      {type !== 'evaluation' && (
        <label className="champ">Chronométré <span className="champ-aide">(minutes ; vide : pas de chronomètre. Le sujet reste caché jusqu'au clic sur « Commencer »)</span>
          <input type="number" name="duree_min" min={1} max={600} placeholder="Ex. : 15 pour l'évaluation du jour" />
        </label>
      )}
      <MessageErreur erreur={erreur} />
      <button className="btn" type="submit" disabled={envoi}>{envoi ? 'Envoi…' : 'Donner ce travail'}</button>
    </form>
  )
}

/** Dans la page d'une classe : les devoirs donnés et le formulaire pour en donner un. */
export function DevoirsDeLaClasse({ groupe, eleves, parcours }: { groupe: string; eleves: Membre[]; parcours: ResumeParcours[] }) {
  const devoirs = useDonnees(() => api.get<DevoirProf[]>(`groupes/${groupe}/devoirs/`), [groupe])
  const [ouvert, setOuvert] = useState(false)
  return (
    <section>
      <div className="titre-avec-action">
        <h2>Devoirs</h2>
        <button type="button" className="btn" onClick={() => setOuvert(!ouvert)}>{ouvert ? 'Fermer' : '+ Donner du travail'}</button>
      </div>
      {ouvert && (
        <DonnerDuTravail groupe={groupe} eleves={eleves} parcours={parcours} apres={() => {
          setOuvert(false)
          devoirs.recharger()
        }} />
      )}
      {devoirs.chargement && <Chargement />}
      <MessageErreur erreur={devoirs.erreur} />
      {devoirs.donnees?.length === 0 && <p className="discret">Aucun devoir donné pour l'instant.</p>}
      <ul className="liste-devoirs">
        {devoirs.donnees?.map((d) => (
          <li key={d.id}>
            <div className="ligne-avec-action">
              <Link to={`/prof/${groupe}/devoirs/${d.id}`} className="ligne-devoir">
                <span className="ligne-devoir-titre">
                  <span className="discret">{TYPES[d.type]}{d.duree_min ? ` ${d.duree_min} min` : ''} · </span>{d.titre}
                  {d.eleve_nom && <span className="discret"> · pour {d.eleve_nom}</span>}
                </span>
                <span className="ligne-devoir-infos">
                  {d.a_corriger > 0 && <span className="badge attente">{d.a_corriger} à corriger</span>}
                  <span className="discret"> {d.termines}/{d.effectif} faits · pour {dateCourte(d.date_limite)}</span>
                </span>
              </Link>
              <a className="btn ghost petit whatsapp" href={lienWhatsApp(messageDevoir(d))} target="_blank" rel="noreferrer"
                title="Annoncer ce travail sur WhatsApp">WhatsApp</a>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** Un devoir vu par le prof : où en est chaque élève, et l'accès à chaque copie. */
export function SuiviDevoir() {
  const { groupe = '', devoir = '' } = useParams()
  const navigate = useNavigate()
  const { donnees: d, erreur, chargement } = useDonnees(() => api.get<SuiviDevoir>(`devoirs/${devoir}/`), [devoir])

  async function supprimer() {
    if (!window.confirm('Supprimer ce devoir et toutes les copies rendues ?')) return
    await api.delete(`devoirs/${devoir}/`)
    navigate(`/prof/${groupe}`)
  }

  return (
    <Cadre titre={d?.titre}>
      <p className="fil"><Link to={`/prof/${groupe}`}>← La classe</Link></p>
      {chargement && <Chargement />}
      <MessageErreur erreur={erreur} />
      {d && (
        <>
          <p className="discret">
            {TYPES[d.type]}{d.duree_min ? `, chronométré ${d.duree_min} min` : ''} · à rendre pour {dateCourte(d.date_limite)} · noté sur {d.note_sur}
          </p>
          <p>
            <a className="btn ghost whatsapp" href={lienWhatsApp(messageDevoir(d))} target="_blank" rel="noreferrer">Annoncer sur WhatsApp</a>
          </p>
          {(d.consigne || d.pieces.length > 0) && (
            <div className="encart">
              {d.consigne && <TexteLibre texte={d.consigne} />}
              <Pieces pieces={d.pieces} />
            </div>
          )}
          <div className="table-wrap">
            <table className="tableau-progression">
              <thead><tr><th>Élève</th><th>Statut</th><th>Résultat</th><th>Rendu le</th><th /></tr></thead>
              <tbody>
                {d.eleves.map((e) => (
                  <tr key={e.eleve}>
                    <td>{e.prenom} {e.nom}</td>
                    <td><BadgeStatut statut={e.statut} />{e.hors_temps && <span className="discret"> hors temps</span>}</td>
                    <td>{resultat(e, d.note_sur) ?? '—'}</td>
                    <td>{e.rendu_le ? dateCourte(e.rendu_le) : e.tentative_terminee_le ? dateCourte(e.tentative_terminee_le) : '—'}</td>
                    <td><Link className="btn petit" to={`/prof/${groupe}/devoirs/${devoir}/${e.eleve}`}>
                      {e.statut === 'rendu' ? 'Corriger' : 'Voir'}
                    </Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p><button type="button" className="btn ghost petit" onClick={() => void supprimer()}>Supprimer ce devoir</button></p>
        </>
      )}
    </Cadre>
  )
}

/** Corriger la copie d'un élève : sa réponse à gauche, la correction à droite. */
export function CorrigerCopie() {
  const { groupe = '', devoir = '', eleve = '' } = useParams()
  const url = `devoirs/${devoir}/eleves/${eleve}/`
  const charge = useDonnees(() => api.get<CopieEleve>(url), [url])
  const [copie, setCopie] = useState<CopieEleve | null>(null)
  const c = copie ?? charge.donnees ?? null
  const [erreur, setErreur] = useState<Error | null>(null)
  const [message, setMessage] = useState('')
  // Quel bouton a envoyé le formulaire : « Enregistrer » ou « Rendre la copie ».
  const rendreDemande = useRef(false)
  const commentaire = useRef<HTMLTextAreaElement>(null)
  const banque = useDonnees(() => api.get<string[]>('mes-commentaires/'), [url])
  // Passer à la copie suivante garde la même page : on oublie la copie précédente.
  useEffect(() => {
    setCopie(null)
    setMessage('')
    setErreur(null)
  }, [url])
  const suivi = useDonnees(() => api.get<SuiviDevoir>(`devoirs/${devoir}/`), [devoir, copie?.corrige_le])
  const [aAnnoter, setAAnnoter] = useState<PhotoCopie | null>(null)
  // La copie suivante à corriger dans ce devoir (dans l'ordre de la liste).
  const suivante = suivi.donnees?.eleves.find((e) => e.statut === 'rendu' && e.eleve !== eleve)

  function ajouterCommentaire(texte: string) {
    const zone = commentaire.current
    if (!zone) return
    zone.value = zone.value.trim() ? `${zone.value.trim()}\n${texte}` : texte
    zone.focus()
  }

  async function enregistrerAnnotation(image: Blob) {
    const donnees = new FormData()
    donnees.append('photo', image, 'copie-annotee.jpg')
    const r = await api.post<{ rendu: Rendu }>(`${url}photos/`, donnees)
    if (c) setCopie({ ...c, rendu: r.rendu })
    setAAnnoter(null)
  }

  async function enregistrer(e: FormEvent<HTMLFormElement>, rendre: boolean) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setErreur(null)
    setMessage('')
    try {
      const r = await api.post<EtatDevoir & { rendu: Rendu }>(url, {
        note: f.get('note') === '' ? null : f.get('note'),
        commentaire: f.get('commentaire') ?? '',
        correction: f.get('correction') ?? '',
        rendre,
      })
      if (c) setCopie({ ...c, ...r })
      setMessage(rendre ? "Copie rendue : l'élève voit sa correction." : 'Correction enregistrée (pas encore rendue).')
    } catch (err) {
      setErreur(err instanceof ErreurApi ? new Error(Object.values(err.champs()).join(' ') || err.message) : (err as Error))
    }
  }

  if (!c) return <Cadre><Chargement /><MessageErreur erreur={charge.erreur} /></Cadre>
  const r = c.rendu
  return (
    <Cadre titre={`${c.eleve.prenom} ${c.eleve.nom}`}>
      <p className="fil"><Link to={`/prof/${groupe}/devoirs/${devoir}`}>← {c.devoir.titre}</Link></p>
      <p>
        <BadgeStatut statut={c.statut} />{c.score !== null && <> · évaluation : <strong>{c.score} / {c.total}</strong></>}
        {c.hors_temps && <span className="discret"> · envoyée après la fin du temps</span>}
        {suivante && (
          <Link className="btn ghost petit copie-suivante" to={`/prof/${groupe}/devoirs/${devoir}/${suivante.eleve}`}>
            Copie suivante : {suivante.prenom} →
          </Link>
        )}
      </p>
      {aAnnoter && <AnnoterPhoto url={aAnnoter.url} fermer={() => setAAnnoter(null)} enregistrer={enregistrerAnnotation} />}
      <div className="grille-2 haut">
        <section>
          <h2>La copie</h2>
          {!r?.texte && !r?.photos.length && <p className="discret">Rien n'a encore été rendu.</p>}
          {r?.texte && <TexteLibre texte={r.texte} />}
          <Galerie photos={r?.photos ?? []} annoter={setAAnnoter} />
          {(r?.photos.length ?? 0) > 0 && <p className="discret">« Annoter au stylo » : tu écris en rouge sur la photo, elle est ajoutée à la correction.</p>}
        </section>
        <section>
          <h2>La correction</h2>
          <form key={c.corrige_le ?? 'brouillon'} onSubmit={(e) => void enregistrer(e, rendreDemande.current)} className="formulaire-correction">
            <label className="champ">Note sur {c.devoir.note_sur}
              <input type="number" name="note" min={0} max={c.devoir.note_sur} step="0.25" defaultValue={r?.note ?? ''} />
            </label>
            <label className="champ">Mot pour l'élève
              <textarea ref={commentaire} name="commentaire" rows={3} defaultValue={r?.commentaire ?? ''} placeholder="Ce qui est bien, ce qu'il faut retravailler." />
            </label>
            {(banque.donnees?.length ?? 0) > 0 && (
              <div className="banque-commentaires" aria-label="Tes commentaires fréquents">
                {banque.donnees?.map((t) => (
                  <button key={t} type="button" className="puce" onClick={() => ajouterCommentaire(t)} title="Ajouter ce commentaire">{t}</button>
                ))}
              </div>
            )}
            <label className="champ">Correction rédigée
              <textarea name="correction" rows={8} defaultValue={r?.correction ?? ''} />
            </label>
            <Galerie photos={r?.photos_correction ?? []} supprimer={async (p) => {
              await api.delete(`photos/${p.id}/`)
              if (r) setCopie({ ...c, rendu: { ...r, photos_correction: r.photos_correction.filter((x) => x.id !== p.id) } })
            }} />
            <AjoutPhotos url={`${url}photos/`} libelle="Ajouter une photo (copie annotée, corrigé)"
              apres={(x) => setCopie({ ...c, rendu: x.rendu })} />
            <MessageErreur erreur={erreur} />
            {message && (
              <p className="succes" role="status">
                {message}
                {message.startsWith('Copie rendue') && suivante && (
                  <> <Link to={`/prof/${groupe}/devoirs/${devoir}/${suivante.eleve}`}>Copie suivante : {suivante.prenom} {suivante.nom} →</Link></>
                )}
              </p>
            )}
            <div className="actions">
              <button type="submit" className="btn ghost" onClick={() => { rendreDemande.current = false }}>Enregistrer</button>
              <button type="submit" className="btn" onClick={() => { rendreDemande.current = true }}>
                {c.statut === 'corrige' ? 'Mettre à jour la correction rendue' : "Rendre la copie à l'élève"}
              </button>
            </div>
          </form>
        </section>
      </div>
    </Cadre>
  )
}

/** En tête de « Mes classes » : toutes les copies qui attendent une correction. */
export function ACorriger() {
  const { donnees, erreur } = useDonnees(() => api.get<CopieACorriger[]>('a-corriger/'), [])
  if (erreur) return <MessageErreur erreur={erreur} />
  if (!donnees?.length) return null
  return (
    <section className="encart a-corriger">
      <h2>À corriger ({donnees.length})</h2>
      <ul className="liste-simple">
        {donnees.map((c) => (
          <li key={`${c.devoir}-${c.eleve}`}>
            <Link to={`/prof/${c.groupe}/devoirs/${c.devoir}/${c.eleve}`}>{c.prenom} {c.nom} — {c.titre}</Link>
            <span className="discret"> · {c.groupe_nom} · rendu {dateCourte(c.rendu_le)}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
