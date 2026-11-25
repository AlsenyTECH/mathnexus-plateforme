import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { Groupe, Membre, ResumeParcours, Sommaire, TableauProgression } from '../api/types'
import { BarreAvancement, Cadre, Chargement, MessageErreur, useDonnees } from '../composants/communs'

export function MesClasses() {
  const { donnees, erreur, chargement } = useDonnees(() => api.get<Groupe[]>('groupes/'), [])
  const classes = donnees?.filter((g) => g.mon_role === 'prof' || g.mon_role === 'admin')
  return (
    <Cadre titre="Mes classes">
      {chargement && <Chargement />}
      <MessageErreur erreur={erreur} />
      <ul className="liste-cartes">
        {classes?.map((g) => (
          <li key={g.id}>
            <Link className="carte-choix" to={`/prof/${g.id}`}>
              <strong>{g.nom}</strong>
              <span>{g.organisation_nom} · {g.annee_libelle}</span>
            </Link>
          </li>
        ))}
      </ul>
    </Cadre>
  )
}

export function ClasseProf() {
  const { groupe = '' } = useParams()
  const g = useDonnees(() => api.get<Groupe>(`groupes/${groupe}/`), [groupe])
  const membres = useDonnees(() => api.get<Membre[]>(`groupes/${groupe}/membres/`), [groupe])
  const parcours = useDonnees(() => api.get<ResumeParcours[]>(`groupes/${groupe}/parcours/`), [groupe])
  const eleves = membres.donnees?.filter((m) => m.role === 'eleve') ?? []
  return (
    <Cadre titre={g.donnees ? `${g.donnees.nom} · ${g.donnees.annee_libelle}` : undefined}>
      <p className="fil"><Link to="/prof">← Mes classes</Link></p>
      <MessageErreur erreur={g.erreur ?? membres.erreur ?? parcours.erreur} />
      <div className="grille-2 haut">
        <section>
          <h2>Parcours</h2>
          {parcours.chargement && <Chargement />}
          {parcours.donnees?.length === 0 && <p className="encart">Aucun parcours rattaché à cette classe.</p>}
          <ul className="liste-simple">
            {parcours.donnees?.map((p) => (
              <li key={p.slug}>
                <Link to={`/prof/${groupe}/${p.slug}`}>{p.titre}</Link>
                <span className="discret"> · {p.ouverture === 'progressive' ? 'ouverture progressive' : 'tout ouvert'}</span>
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h2>Élèves ({eleves.length})</h2>
          {membres.chargement && <Chargement />}
          <ul className="liste-simple">
            {eleves.map((m) => <li key={m.utilisateur}>{m.prenom} {m.nom}</li>)}
          </ul>
        </section>
      </div>
    </Cadre>
  )
}

export function ProgressionProf() {
  const { groupe = '', slug = '' } = useParams()
  const tableau = useDonnees(() => api.get<TableauProgression>(`groupes/${groupe}/parcours/${slug}/progression/`), [groupe, slug])
  const sommaire = useDonnees(() => api.get<Sommaire>(`groupes/${groupe}/parcours/${slug}/`), [groupe, slug])
  const [ouvertes, setOuvertes] = useState<string[] | null>(null)
  const [erreur, setErreur] = useState<Error | null>(null)
  const t = tableau.donnees
  const s = sommaire.donnees

  async function basculer(cle: string, ouvrir: boolean) {
    setErreur(null)
    try {
      const r = await api.post<{ ouvertes: string[] }>(`groupes/${groupe}/parcours/${slug}/ouverture/`, { etapes: [cle], ouvrir })
      setOuvertes(r.ouvertes)
    } catch (e) {
      setErreur(e as Error)
    }
  }

  return (
    <Cadre titre={s?.titre}>
      <p className="fil"><Link to={`/prof/${groupe}`}>← La classe</Link></p>
      <MessageErreur erreur={tableau.erreur ?? sommaire.erreur ?? erreur} />
      {(tableau.chargement || sommaire.chargement) && <Chargement />}
      {s?.ouverture === 'progressive' && (
        <section className="encart">
          <h2>Ouvrir les étapes au fil du cours</h2>
          <OuvertureEtapes sommaire={s} ouvertes={ouvertes} basculer={basculer} />
        </section>
      )}
      {t && (
        <section>
          <h2>Progression des élèves</h2>
          <div className="table-wrap">
            <table className="tableau-progression">
              <thead>
                <tr>
                  <th>Élève</th>
                  <th>Avancement</th>
                  {t.etapes.map((e, i) => <th key={e.cle} className="c" title={e.titre}>{i + 1}</th>)}
                  <th>Dernière activité</th>
                </tr>
              </thead>
              <tbody>
                {t.eleves.map((el) => (
                  <tr key={el.utilisateur}>
                    <td>{el.prenom} {el.nom}</td>
                    <td><BarreAvancement validees={el.validees.length} total={t.etapes.length} /></td>
                    {t.etapes.map((e) => (
                      <td key={e.cle} className="c" aria-label={`${e.titre} : ${el.validees.includes(e.cle) ? 'validée' : 'non validée'}`}>
                        {el.validees.includes(e.cle) ? '✓' : ''}
                      </td>
                    ))}
                    <td>{el.derniere_activite ? new Date(el.derniere_activite).toLocaleDateString('fr-FR') : 'jamais'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </Cadre>
  )
}

function OuvertureEtapes({ sommaire, ouvertes, basculer }: {
  sommaire: Sommaire; ouvertes: string[] | null; basculer: (cle: string, ouvrir: boolean) => void
}) {
  return (
    <ul className="liste-simple">
      {sommaire.parties.flatMap((p) => p.etapes).map((e) => {
        const ouverte = ouvertes ? ouvertes.includes(e.cle) : e.ouverte_eleves
        return (
          <li key={e.cle} className="ligne-ouverture">
            <span>
              {e.titre} <span className={ouverte ? 'badge ok' : 'badge soon'}>{ouverte ? 'Ouverte' : 'Fermée'}</span>
            </span>
            <button type="button" className="btn ghost petit" onClick={() => basculer(e.cle, !ouverte)}>
              {ouverte ? 'Fermer' : 'Ouvrir'}
            </button>
          </li>
        )
      })}
    </ul>
  )
}
