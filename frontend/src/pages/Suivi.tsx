/**
 * Le suivi au quotidien.
 *
 * Élève : <SeanceDuJour> (en tête de sa classe) et <PageCarnet> (son carnet d'erreurs à retravailler).
 * Prof : <TableauDeClasse> (dans la page de la classe) et <PageFicheEleve> (tout sur un élève,
 * le bilan à envoyer au parent, le mot de passe à réinitialiser).
 */
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { Bilan, Carnet, EntreeCarnet, FicheEleve, LigneSuivi, ReponseCarnet, SeanceDuJour as Seance } from '../api/types'
import { Cadre, Chargement, MessageErreur, useDonnees } from '../composants/communs'
import { useSession } from '../session'
import { rendreFormules } from '../lecteur/maths'
import { nettoyer } from '../lecteur/nettoyage'
import { depuis, lienWhatsApp } from '../utilitaires'
import { BadgeStatut, dateCourte } from './Devoirs'

// --- L'élève : la séance du jour --------------------------------------------------------------

export function SeanceDuJour({ groupe }: { groupe: string }) {
  const { donnees: s, erreur } = useDonnees(() => api.get<Seance>(`groupes/${groupe}/seance/`), [groupe])
  if (erreur) return <MessageErreur erreur={erreur} />
  if (!s) return <Chargement texte="Préparation de ta séance…" />
  const rien = !s.devoirs.length && !s.etapes.length && !s.revisions
  const date = new Date(s.date).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })
  return (
    <section className="seance">
      <h2>Ma séance du {date}</h2>
      {rien && <p>Rien d'urgent aujourd'hui. Avance dans un parcours ci-dessous, ou relis tes cours.</p>}
      <ol className="seance-liste">
        {s.devoirs.map((d) => (
          <li key={d.id} className={d.statut === 'en_retard' ? 'retard' : ''}>
            <Link to={`/classe/${groupe}/devoirs/${d.id}`}>
              <span className="seance-type">{d.duree_min ? `Évaluation ${d.duree_min} min` : 'Devoir'}</span>
              <strong>{d.titre}</strong>
              <span className="discret">
                {d.statut === 'en_retard' ? 'En retard · ' : ''}pour {dateCourte(d.date_limite)}
                {d.duree_min && !d.commence_le ? ' · le chronomètre démarre quand tu commences' : ''}
              </span>
            </Link>
          </li>
        ))}
        {s.revisions > 0 && (
          <li>
            <Link to={`/classe/${groupe}/carnet`}>
              <span className="seance-type">Révision</span>
              <strong>{s.revisions} question{s.revisions > 1 ? 's' : ''} de ton carnet d'erreurs</strong>
              <span className="discret">Quelques minutes : refais les questions que tu avais ratées.</span>
            </Link>
          </li>
        )}
        {s.etapes.map((e) => (
          <li key={`${e.parcours}-${e.cle}`}>
            <Link to={`/classe/${groupe}/${e.parcours}/${e.cle}`}>
              <span className="seance-type">{e.commencee ? 'Reprendre' : 'Étape suivante'}</span>
              <strong>{e.titre}</strong>
              <span className="discret">{e.parcours_titre}{e.duree_min ? ` · ${e.duree_min} min` : ''}</span>
            </Link>
          </li>
        ))}
      </ol>
      <p className="discret">
        {s.autres_parcours > 0 && <>Et {s.autres_parcours} autre{s.autres_parcours > 1 ? 's' : ''} parcours plus bas. · </>}
        <Link to={`/classe/${groupe}/carnet`}>Mon carnet d'erreurs</Link>
      </p>
    </section>
  )
}

// --- L'élève : le carnet d'erreurs -------------------------------------------------------------

/** Un morceau de HTML venu d'un paquet (énoncé, choix) : nettoyé, puis formules rendues. */
function Html({ html, className }: { html: string; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const propre = nettoyer(html)
  useEffect(() => {
    if (ref.current) rendreFormules(ref.current)
  }, [propre])
  return <div ref={ref} className={className} dangerouslySetInnerHTML={{ __html: propre }} />
}

function QuestionCarnet({ entree, apres }: { entree: EntreeCarnet; apres: (r: ReponseCarnet) => void }) {
  const [choix, setChoix] = useState<number[]>([])
  const [reponse, setReponse] = useState<ReponseCarnet | null>(null)
  const [erreur, setErreur] = useState<Error | null>(null)
  const q = entree.question

  async function verifier() {
    setErreur(null)
    try {
      const r = await api.post<ReponseCarnet>(`carnet/${entree.id}/repondre/`, { choix })
      setReponse(r)
      apres(r)
    } catch (e) {
      setErreur(e as Error)
    }
  }

  function cocher(i: number) {
    if (reponse) return
    setChoix((c) => (q.multiple ? (c.includes(i) ? c.filter((x) => x !== i) : [...c, i]) : [i]))
  }

  return (
    <article className="carnet-question">
      <p className="discret">{entree.evaluation} · {entree.parcours_titre}</p>
      <Html className="lbody enonce" html={q.enonce} />
      {q.multiple && <p className="discret">Plusieurs réponses possibles.</p>}
      <ul className="choix-carnet">
        {q.choix.map((c, i) => {
          const classe = reponse ? (reponse.bonnes.includes(i) ? 'juste' : choix.includes(i) ? 'faux' : '') : choix.includes(i) ? 'choisi' : ''
          return (
            <li key={i}>
              <button type="button" className={`choix ${classe}`} aria-pressed={choix.includes(i)} onClick={() => cocher(i)}>
                <Html html={c} />
              </button>
            </li>
          )
        })}
      </ul>
      {!reponse && <button type="button" className="btn" disabled={!choix.length} onClick={() => void verifier()}>Vérifier</button>}
      {reponse && (
        <div className={`verdict ${reponse.juste ? 'ok' : 'ko'}`}>
          <strong>{reponse.juste ? 'Juste !' : 'Pas encore.'}</strong>{' '}
          {reponse.entree.maitrisee_le
            ? 'Question maîtrisée : elle sort du carnet.'
            : reponse.juste
              ? `Elle reviendra dans quelques jours pour vérifier que c'est bien acquis.`
              : 'Elle reviendra demain.'}
          {reponse.explication && <Html className="lbody" html={reponse.explication} />}
          <p><Link to={`/classe/${entree.groupe}/${entree.parcours}/${entree.cle_etape}`}>Revoir l'étape : {entree.etape_titre}</Link></p>
        </div>
      )}
      <MessageErreur erreur={erreur} />
    </article>
  )
}

export function PageCarnet() {
  const { groupe = '' } = useParams()
  const { donnees, erreur, chargement, recharger } = useDonnees(() => api.get<Carnet>(`carnet/?groupe=${groupe}`), [groupe])
  const [index, setIndex] = useState(0)
  const [repondue, setRepondue] = useState(false)
  // La liste des questions dues est figée à l'ouverture : on les fait une par une.
  const [dues, setDues] = useState<EntreeCarnet[] | null>(null)
  useEffect(() => {
    if (donnees && dues === null) setDues(donnees.entrees.filter((e) => e.due))
  }, [donnees, dues])
  const actuelle = dues?.[index]

  return (
    <Cadre titre="Mon carnet d'erreurs">
      <p className="fil"><Link to={`/classe/${groupe}`}>← Ma classe</Link></p>
      {chargement && <Chargement />}
      <MessageErreur erreur={erreur} />
      {donnees && (
        <p className="discret">
          Les questions ratées de tes évaluations arrivent ici. Une bonne réponse les fait revenir dans 1, puis 3, puis 7 jours ;
          trois bonnes réponses de suite et la question est maîtrisée. · {donnees.en_cours} en cours, {donnees.maitrisees} maîtrisée{donnees.maitrisees > 1 ? 's' : ''}.
        </p>
      )}
      {dues && dues.length === 0 && <p className="encart">Rien à revoir aujourd'hui. Bravo !</p>}
      {actuelle && (
        <>
          <p><strong>Question {index + 1} sur {dues.length}</strong></p>
          <QuestionCarnet key={actuelle.id} entree={actuelle} apres={() => setRepondue(true)} />
          {repondue && (
            index + 1 < dues.length ? (
              <button type="button" className="btn" onClick={() => { setIndex(index + 1); setRepondue(false) }}>Question suivante →</button>
            ) : (
              <p className="succes">Séance de révision terminée. <Link to={`/classe/${groupe}`}>Retour à ma classe</Link></p>
            )
          )}
        </>
      )}
      {dues && index >= dues.length && dues.length > 0 && (
        <button type="button" className="btn ghost" onClick={() => { setDues(null); setIndex(0); recharger() }}>Recharger</button>
      )}
    </Cadre>
  )
}

// --- Le prof : tableau de classe ----------------------------------------------------------------

function moyenne(n: number | null) {
  return n === null ? '—' : `${n.toFixed(1).replace('.', ',')}/20`
}

export function TableauDeClasse({ groupe }: { groupe: string }) {
  const { donnees, erreur, chargement } = useDonnees(() => api.get<LigneSuivi[]>(`groupes/${groupe}/suivi/`), [groupe])
  return (
    <section>
      <h2>Suivi des élèves</h2>
      {chargement && <Chargement />}
      <MessageErreur erreur={erreur} />
      {donnees?.length === 0 && <p className="discret">Aucun élève pour l'instant : donne-leur le code d'inscription de la classe (menu « Classes »).</p>}
      {!!donnees?.length && (
        <div className="table-wrap">
          <table className="tableau-progression tableau-suivi">
            <thead>
              <tr><th>Élève</th><th>Travaux faits</th><th>En retard</th><th>Moyenne</th><th>Étapes</th><th>À revoir</th><th>Dernière activité</th></tr>
            </thead>
            <tbody>
              {donnees.map((l) => {
                const inactif = !l.derniere_activite || Date.now() - new Date(l.derniere_activite).getTime() > 3 * 86_400_000
                return (
                  <tr key={l.eleve}>
                    <td><Link to={`/prof/${groupe}/eleves/${l.eleve}`}>{l.prenom} {l.nom}</Link></td>
                    <td>{l.termines}/{l.devoirs}{l.a_corriger > 0 && <span className="badge attente"> {l.a_corriger} à corriger</span>}</td>
                    <td className={l.en_retard ? 'alerte' : ''}>{l.en_retard || '—'}</td>
                    <td>{moyenne(l.moyenne)}</td>
                    <td>{l.etapes_validees}/{l.etapes_total}</td>
                    <td>{l.carnet_a_revoir || '—'}</td>
                    <td className={inactif ? 'alerte' : ''}>{depuis(l.derniere_activite)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

// --- Le prof : fiche élève, bilan parent, mot de passe ------------------------------------------

function BilanParent({ groupe, eleve, prenom }: { groupe: string; eleve: string; prenom: string }) {
  const [jours, setJours] = useState(7)
  const { donnees: b, erreur } = useDonnees(() => api.get<Bilan>(`groupes/${groupe}/eleves/${eleve}/bilan/?jours=${jours}`), [groupe, eleve, jours])
  const [texte, setTexte] = useState('')
  const [copie, setCopie] = useState(false)
  useEffect(() => {
    if (b) setTexte(b.texte)
  }, [b])

  async function copier() {
    await navigator.clipboard.writeText(texte)
    setCopie(true)
    window.setTimeout(() => setCopie(false), 2000)
  }

  return (
    <section className="encart bilan">
      <div className="titre-avec-action">
        <h2>Bilan pour le parent</h2>
        <select value={jours} onChange={(e) => setJours(Number(e.target.value))} aria-label="Période">
          <option value={7}>7 derniers jours</option>
          <option value={14}>14 derniers jours</option>
          <option value={30}>30 derniers jours</option>
        </select>
      </div>
      <MessageErreur erreur={erreur} />
      <p className="discret">Relis et complète le message (ton avis, un conseil), puis envoie-le.</p>
      <textarea className="zone-copie" rows={9} value={texte} onChange={(e) => setTexte(e.target.value)} />
      <div className="actions">
        {b?.telephone_parent ? (
          <a className="btn whatsapp" href={lienWhatsApp(texte, b.telephone_parent)} target="_blank" rel="noreferrer">Envoyer au parent sur WhatsApp</a>
        ) : (
          <span className="discret">Pas de téléphone de parent enregistré pour {prenom}.</span>
        )}
        <a className="btn ghost" href={lienWhatsApp(texte)} target="_blank" rel="noreferrer">Choisir le destinataire sur WhatsApp</a>
        <button type="button" className="btn ghost" onClick={() => void copier()}>{copie ? 'Copié ✓' : 'Copier le texte'}</button>
      </div>
    </section>
  )
}

function NouveauMotDePasse({ eleve, prenom, telephone }: { eleve: string; prenom: string; telephone: string }) {
  const [mdp, setMdp] = useState<string | null>(null)
  const [erreur, setErreur] = useState<Error | null>(null)

  async function reinitialiser() {
    if (!window.confirm(`Donner un nouveau mot de passe provisoire à ${prenom} ? Son ancien mot de passe ne marchera plus.`)) return
    setErreur(null)
    try {
      setMdp((await api.post<{ mot_de_passe_provisoire: string }>(`admin/comptes/${eleve}/reinitialiser-mot-de-passe/`)).mot_de_passe_provisoire)
    } catch (e) {
      setErreur(e as Error)
    }
  }

  const message = mdp
    ? `Bonjour ${prenom}, voici ton mot de passe provisoire pour Mathnexus : ${mdp}\nConnecte-toi sur ${window.location.origin}/connexion avec ton numéro ; on te demandera d'en choisir un nouveau.`
    : ''
  return (
    <section>
      <h3>Mot de passe oublié</h3>
      {!mdp && <button type="button" className="btn ghost petit" onClick={() => void reinitialiser()}>Donner un nouveau mot de passe provisoire</button>}
      {mdp && (
        <p className="encart">
          Mot de passe provisoire : <strong className="mdp">{mdp}</strong> (affiché une seule fois).{' '}
          <a className="btn petit whatsapp" href={lienWhatsApp(message, telephone)} target="_blank" rel="noreferrer">Le lui envoyer sur WhatsApp</a>
        </p>
      )}
      <MessageErreur erreur={erreur} />
    </section>
  )
}

export function PageFicheEleve() {
  const { groupe = '', eleve = '' } = useParams()
  const utilisateur = useSession().session?.utilisateur
  const { donnees: f, erreur, chargement } = useDonnees(() => api.get<FicheEleve>(`groupes/${groupe}/eleves/${eleve}/`), [groupe, eleve])
  return (
    <Cadre titre={f ? `${f.prenom} ${f.nom}` : undefined}>
      <p className="fil"><Link to={`/prof/${groupe}`}>← La classe</Link></p>
      {chargement && <Chargement />}
      <MessageErreur erreur={erreur} />
      {f && (
        <>
          <div className="chiffres">
            <div><strong>{f.termines}/{f.devoirs}</strong><span>travaux faits</span></div>
            <div className={f.en_retard ? 'alerte' : ''}><strong>{f.en_retard}</strong><span>en retard</span></div>
            <div><strong>{moyenne(f.moyenne)}</strong><span>moyenne</span></div>
            <div><strong>{f.etapes_validees}/{f.etapes_total}</strong><span>étapes</span></div>
            <div><strong>{f.carnet_a_revoir}</strong><span>erreurs à revoir</span></div>
            <div><strong>{depuis(f.derniere_activite)}</strong><span>dernière activité</span></div>
          </div>
          <p className="contacts">
            <a className="btn ghost petit whatsapp" href={lienWhatsApp(`Bonjour ${f.prenom}, `, f.telephone)} target="_blank" rel="noreferrer">
              WhatsApp {f.prenom} ({f.telephone})
            </a>
            {f.telephone_parent && (
              <a className="btn ghost petit whatsapp" href={lienWhatsApp('Bonjour, ', f.telephone_parent)} target="_blank" rel="noreferrer">
                WhatsApp parent ({f.telephone_parent})
              </a>
            )}
          </p>

          <BilanParent groupe={groupe} eleve={eleve} prenom={f.prenom} />

          <h2>Travaux</h2>
          {f.liste_devoirs.length === 0 && <p className="discret">Aucun travail donné pour l'instant.</p>}
          <div className="table-wrap">
            <table className="tableau-progression">
              <tbody>
                {f.liste_devoirs.map((d) => (
                  <tr key={d.id}>
                    <td><Link to={`/prof/${groupe}/devoirs/${d.id}/${eleve}`}>{d.titre}</Link></td>
                    <td><BadgeStatut statut={d.statut} /></td>
                    <td>{d.sur_20 !== null ? moyenne(d.sur_20) : '—'}</td>
                    <td className="discret">{dateCourte(d.date_limite)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {f.evaluations.length > 0 && (
            <>
              <h2>Évaluations des parcours</h2>
              <ul className="liste-simple">
                {f.evaluations.map((e, i) => (
                  <li key={i}>
                    {e.titre} <span className="discret">· {e.parcours_titre}</span> : <strong>{e.score} / {e.total}</strong>
                    <span className="discret"> · {dateCourte(e.terminee_le)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          <h2>Parcours</h2>
          <ul className="liste-simple">
            {f.progression.map((p) => (
              <li key={p.slug}>
                <Link to={`/prof/${groupe}/${p.slug}`}>{p.titre}</Link> : {p.validees}/{p.total} étapes
                <span className="discret"> · {p.derniere_ouverture ? `ouvert ${depuis(p.derniere_ouverture)}` : 'pas encore ouvert'}</span>
              </li>
            ))}
          </ul>

          {utilisateur?.est_admin && <NouveauMotDePasse eleve={eleve} prenom={f.prenom} telephone={f.telephone} />}
        </>
      )}
    </Cadre>
  )
}
