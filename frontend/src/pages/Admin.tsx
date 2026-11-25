import { useState, type FormEvent } from 'react'
import { api, ErreurApi } from '../api/client'
import type { CompteEnAttente, GroupeAdmin, ParcoursCatalogue, ResumeVersion } from '../api/types'
import { Cadre, Chargement, MessageErreur, useDonnees } from '../composants/communs'
import { lireListe } from '../utilitaires'

interface Referentiel {
  organisations: { id: string; nom: string }[]
  annees: { id: number; libelle: string; en_cours: boolean }[]
}

const CYCLES = { lycee: 'Lycée', prepa: 'Prépa', universite: 'Université' } as const

// --- Comptes en attente --------------------------------------------------------------

export function ComptesEnAttente() {
  const comptes = useDonnees(() => api.get<CompteEnAttente[]>('admin/comptes-en-attente/'), [])
  const groupes = useDonnees(() => api.get<GroupeAdmin[]>('admin/groupes/'), [])
  const [choix, setChoix] = useState<Record<string, string>>({})
  const [erreur, setErreur] = useState<Error | null>(null)

  async function agir(id: string, action: 'valider' | 'refuser') {
    setErreur(null)
    try {
      await api.post(`admin/comptes/${id}/${action}/`, action === 'valider' && choix[id] ? { groupe: choix[id] } : undefined)
      comptes.recharger()
    } catch (e) {
      if (e instanceof ErreurApi && e.champs().groupe) setErreur(new Error(e.champs().groupe))
      else setErreur(e as Error)
    }
  }

  const actifs = groupes.donnees?.filter((g) => !g.archive) ?? []
  return (
    <Cadre titre="Comptes en attente">
      <MessageErreur erreur={comptes.erreur ?? erreur} />
      {comptes.chargement && <Chargement />}
      {comptes.donnees?.length === 0 && <p className="encart">Aucun compte en attente.</p>}
      <ul className="liste-cartes">
        {comptes.donnees?.map((c) => (
          <li key={c.id} className="carte-compte">
            <p><strong>{c.prenom} {c.nom}</strong> · {c.telephone}</p>
            <p className="discret">
              {[c.niveau_declare, c.etablissement_frequente, c.telephone_parent && `parent : ${c.telephone_parent}`]
                .filter(Boolean).join(' · ') || 'Aucune précision'}
            </p>
            {c.demandes.length > 0 ? (
              <p>Demande : {c.demandes.map((d) => d.groupe_nom).join(', ')}</p>
            ) : (
              <label className="champ">
                Classe à attribuer
                <select value={choix[c.id] ?? ''} onChange={(e) => setChoix({ ...choix, [c.id]: e.target.value })}>
                  <option value="">Choisir…</option>
                  {actifs.map((g) => <option key={g.id} value={g.id}>{g.nom}</option>)}
                </select>
              </label>
            )}
            <div className="actions">
              <button type="button" className="btn" onClick={() => void agir(c.id, 'valider')}>Valider</button>
              <button type="button" className="btn ghost" onClick={() => {
                if (window.confirm(`Refuser et supprimer le compte de ${c.prenom} ${c.nom} ?`)) void agir(c.id, 'refuser')
              }}>Refuser</button>
            </div>
          </li>
        ))}
      </ul>
    </Cadre>
  )
}

// --- Classes --------------------------------------------------------------------------

export function Classes() {
  const groupes = useDonnees(() => api.get<GroupeAdmin[]>('admin/groupes/'), [])
  const ref = useDonnees(() => api.get<Referentiel>('admin/referentiel/'), [])
  const catalogue = useDonnees(() => api.get<ParcoursCatalogue[]>('admin/contenus/parcours/'), [])
  const [f, setF] = useState({ nom: '', cycle: 'lycee', organisation: '', annee: '' })
  const [erreur, setErreur] = useState<Error | null>(null)
  const [ouverte, setOuverte] = useState<string | null>(null)

  async function creer(e: FormEvent) {
    e.preventDefault()
    setErreur(null)
    const r = ref.donnees
    try {
      await api.post('admin/groupes/', {
        ...f,
        organisation: f.organisation || r?.organisations[0]?.id,
        annee: Number(f.annee || r?.annees.find((a) => a.en_cours)?.id || r?.annees[0]?.id),
      })
      setF({ ...f, nom: '' })
      groupes.recharger()
    } catch (err) {
      setErreur(err as Error)
    }
  }

  return (
    <Cadre titre="Classes">
      <MessageErreur erreur={groupes.erreur ?? ref.erreur ?? erreur} />
      {ref.donnees && ref.donnees.organisations.length === 0 && (
        <p className="encart">Crée d'abord une organisation et une année scolaire dans l'administration Django (/gestion/).</p>
      )}
      <form className="ligne-formulaire" onSubmit={creer}>
        <input aria-label="Nom de la classe" placeholder="Terminale S2" value={f.nom} required
          onChange={(e) => setF({ ...f, nom: e.target.value })} />
        <select aria-label="Cycle" value={f.cycle} onChange={(e) => setF({ ...f, cycle: e.target.value })}>
          {Object.entries(CYCLES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <select aria-label="Organisation" value={f.organisation} onChange={(e) => setF({ ...f, organisation: e.target.value })}>
          {ref.donnees?.organisations.map((o) => <option key={o.id} value={o.id}>{o.nom}</option>)}
        </select>
        <select aria-label="Année scolaire" value={f.annee} onChange={(e) => setF({ ...f, annee: e.target.value })}>
          {ref.donnees?.annees.map((a) => <option key={a.id} value={a.id}>{a.libelle}</option>)}
        </select>
        <button className="btn" type="submit">Créer la classe</button>
      </form>
      {groupes.chargement && <Chargement />}
      <ul className="liste-cartes">
        {groupes.donnees?.map((g) => (
          <li key={g.id} className="carte-classe">
            <div className="carte-classe-tete">
              <p><strong>{g.nom}</strong> · {CYCLES[g.cycle]} · {g.effectif} élève{g.effectif > 1 ? 's' : ''}</p>
              <p>Code d'inscription : <code className="code-classe">{g.code_inscription}</code>{' '}
                <button type="button" className="btn ghost petit" onClick={async () => {
                  if (!window.confirm("L'ancien code ne marchera plus. Continuer ?")) return
                  await api.post(`admin/groupes/${g.id}/regenerer-code/`)
                  groupes.recharger()
                }}>Nouveau code</button>
              </p>
              <button type="button" className="btn ghost petit" aria-expanded={ouverte === g.id}
                onClick={() => setOuverte(ouverte === g.id ? null : g.id)}>
                {ouverte === g.id ? 'Fermer' : 'Gérer'}
              </button>
            </div>
            {ouverte === g.id && <GestionClasse groupe={g} catalogue={catalogue.donnees ?? []} />}
          </li>
        ))}
      </ul>
    </Cadre>
  )
}

function GestionClasse({ groupe, catalogue }: { groupe: GroupeAdmin; catalogue: ParcoursCatalogue[] }) {
  const [liste, setListe] = useState('')
  const [resultats, setResultats] = useState<{ telephone: string; etat: string; mot_de_passe_provisoire?: string }[] | null>(null)
  const [parcours, setParcours] = useState('')
  const [ouverture, setOuverture] = useState('tout')
  const [message, setMessage] = useState<string | null>(null)
  const [erreur, setErreur] = useState<Error | null>(null)
  const lignes = lireListe(liste)
  const publies = catalogue.filter((p) => p.versions.some((v) => v.statut === 'publiee'))

  return (
    <div className="gestion-classe">
      <section>
        <h3>Importer une liste d'élèves</h3>
        <p className="discret">Une ligne par élève : Prénom ; Nom ; Téléphone (copié depuis un tableur).</p>
        <textarea rows={5} value={liste} onChange={(e) => setListe(e.target.value)} aria-label="Liste des élèves"
          placeholder={'Fatou ; Ba ; 77 300 00 01\nIbou ; Fall ; 77 300 00 02'} />
        <button type="button" className="btn" disabled={!lignes.length} onClick={async () => {
          setErreur(null)
          try {
            const r = await api.post<{ resultats: typeof resultats }>(`admin/groupes/${groupe.id}/importer/`, { eleves: lignes })
            setResultats(r.resultats)
            setListe('')
          } catch (e) {
            setErreur(e as Error)
          }
        }}>Importer {lignes.length || ''} élève{lignes.length > 1 ? 's' : ''}</button>
        {resultats && (
          <div className="encart">
            <p><strong>Note ces mots de passe maintenant : ils ne seront plus affichés.</strong></p>
            <ul className="liste-simple">
              {resultats.map((r) => (
                <li key={r.telephone}>
                  {r.telephone} · {r.etat === 'cree' ? <>mot de passe provisoire : <code>{r.mot_de_passe_provisoire}</code></> : 'compte existant rattaché'}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
      <section>
        <h3>Rattacher un parcours</h3>
        <div className="ligne-formulaire">
          <select aria-label="Parcours" value={parcours} onChange={(e) => setParcours(e.target.value)}>
            <option value="">Choisir un parcours publié…</option>
            {publies.map((p) => <option key={p.slug} value={p.slug}>{p.titre}</option>)}
          </select>
          <select aria-label="Ouverture" value={ouverture} onChange={(e) => setOuverture(e.target.value)}>
            <option value="tout">Toutes les étapes ouvertes</option>
            <option value="progressive">Ouverture progressive par le prof</option>
          </select>
          <button type="button" className="btn" disabled={!parcours} onClick={async () => {
            setErreur(null)
            try {
              await api.post(`admin/groupes/${groupe.id}/parcours/`, { parcours, ouverture })
              setMessage('Parcours rattaché.')
            } catch (e) {
              setErreur(e as Error)
            }
          }}>Rattacher</button>
        </div>
        {message && <p className="done-note">{message}</p>}
      </section>
      <MessageErreur erreur={erreur} />
    </div>
  )
}

// --- Contenus --------------------------------------------------------------------------

export function Contenus() {
  const catalogue = useDonnees(() => api.get<ParcoursCatalogue[]>('admin/contenus/parcours/'), [])
  const [problemes, setProblemes] = useState<string[]>([])
  const [erreur, setErreur] = useState<Error | null>(null)
  const [envoi, setEnvoi] = useState(false)

  async function importer(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const champ = e.currentTarget.elements.namedItem('paquet') as HTMLInputElement
    const fichier = champ.files?.[0]
    if (!fichier) return
    setErreur(null)
    setProblemes([])
    setEnvoi(true)
    const donnees = new FormData()
    donnees.append('paquet', fichier)
    try {
      await api.post<ResumeVersion>('admin/contenus/import/', donnees)
      champ.value = ''
      catalogue.recharger()
    } catch (err) {
      if (err instanceof ErreurApi && Array.isArray(err.donnees.problemes)) setProblemes(err.donnees.problemes as string[])
      setErreur(err as Error)
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <Cadre titre="Contenus">
      <form className="ligne-formulaire" onSubmit={importer}>
        <input type="file" name="paquet" accept=".zip,application/zip" aria-label="Paquet de parcours (.zip)" required />
        <button className="btn" type="submit" disabled={envoi}>{envoi ? 'Import…' : 'Importer le paquet'}</button>
      </form>
      <MessageErreur erreur={catalogue.erreur ?? erreur} />
      {problemes.length > 0 && (
        <ul className="erreur liste-simple">{problemes.map((p) => <li key={p}>{p}</li>)}</ul>
      )}
      {catalogue.chargement && <Chargement />}
      <ul className="liste-cartes">
        {catalogue.donnees?.map((p) => (
          <li key={p.slug} className="carte-classe">
            <p><strong>{p.titre}</strong> · {p.matiere} · {p.groupes.length} classe{p.groupes.length > 1 ? 's' : ''}</p>
            <table>
              <thead><tr><th>Version</th><th>Statut</th><th>Étapes</th><th>Importée le</th><th /></tr></thead>
              <tbody>
                {p.versions.map((v) => (
                  <tr key={v.id}>
                    <td>v{v.numero}</td>
                    <td><span className={`badge ${v.statut === 'publiee' ? 'ok' : 'soon'}`}>{
                      { brouillon: 'Brouillon', publiee: 'Publiée', archivee: 'Archivée' }[v.statut]}</span></td>
                    <td>{v.nombre_etapes}</td>
                    <td>{new Date(v.importee_le).toLocaleString('fr-FR')}</td>
                    <td>
                      {v.statut !== 'publiee' && (
                        <button type="button" className="btn petit" onClick={async () => {
                          await api.post(`admin/contenus/versions/${v.id}/publier/`)
                          catalogue.recharger()
                        }}>Publier</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </li>
        ))}
      </ul>
    </Cadre>
  )
}
