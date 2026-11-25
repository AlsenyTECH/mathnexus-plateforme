import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { api, ErreurApi } from '../api/client'
import type { Groupe, Session } from '../api/types'
import { Cadre, Chargement, MessageErreur, useDonnees } from '../composants/communs'
import { routePour, useSession } from '../session'

function Champ({
  id, label, erreur, aide, children,
}: { id: string; label: string; erreur?: string; aide?: string; children: ReactNode }) {
  return (
    <div className="champ">
      <label htmlFor={id}>{label}</label>
      {children}
      {aide && !erreur && <p className="champ-aide">{aide}</p>}
      {erreur && (
        <p className="champ-erreur" id={`${id}-erreur`} role="alert">
          {erreur}
        </p>
      )}
    </div>
  )
}

function useEnvoi() {
  const [envoi, setEnvoi] = useState(false)
  const [erreur, setErreur] = useState<ErreurApi | Error | null>(null)
  const [champs, setChamps] = useState<Record<string, string>>({})
  async function lancer(action: () => Promise<void>) {
    setEnvoi(true)
    setErreur(null)
    setChamps({})
    try {
      await action()
    } catch (e) {
      if (e instanceof ErreurApi) {
        setChamps(e.champs())
        if (!Object.keys(e.champs()).length || e.donnees.detail) setErreur(e)
      } else setErreur(e as Error)
    } finally {
      setEnvoi(false)
    }
  }
  return { envoi, erreur, champs, lancer }
}

export function Connexion() {
  const { session, definir } = useSession()
  const naviguer = useNavigate()
  const [telephone, setTelephone] = useState('')
  const [motDePasse, setMotDePasse] = useState('')
  const { envoi, erreur, lancer } = useEnvoi()

  if (session) return <Navigate to={routePour(session.destination)} replace />

  function soumettre(e: FormEvent) {
    e.preventDefault()
    void lancer(async () => {
      const s = await api.post<Session>('auth/connexion/', { telephone, mot_de_passe: motDePasse })
      definir(s)
      naviguer(routePour(s.destination), { replace: true })
    })
  }

  return (
    <Cadre>
      <form className="carte-formulaire" onSubmit={soumettre} noValidate>
        <h1>Se connecter</h1>
        <Champ id="telephone" label="Numéro de téléphone">
          <input id="telephone" type="tel" autoComplete="tel" inputMode="tel" required
            value={telephone} onChange={(e) => setTelephone(e.target.value)} placeholder="77 123 45 67" />
        </Champ>
        <Champ id="mdp" label="Mot de passe">
          <input id="mdp" type="password" autoComplete="current-password" required
            value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)} />
        </Champ>
        <MessageErreur erreur={erreur} />
        <button className="btn" type="submit" disabled={envoi}>
          {envoi ? 'Connexion…' : 'Se connecter'}
        </button>
        <p className="formulaire-pied">
          Pas encore de compte ? <Link to="/inscription">Inscris-toi</Link>
        </p>
      </form>
    </Cadre>
  )
}

export function Inscription() {
  const { session, definir } = useSession()
  const naviguer = useNavigate()
  const [params] = useSearchParams()
  const [f, setF] = useState({
    prenom: '', nom: '', telephone: '', email: '', mot_de_passe: '', niveau_declare: '',
    etablissement_frequente: '', est_mineur: true, telephone_parent: '', code_classe: params.get('code') ?? '',
    accepte_conditions: false,
  })
  const { envoi, erreur, champs, lancer } = useEnvoi()
  if (session) return <Navigate to={routePour(session.destination)} replace />

  const maj = (cle: keyof typeof f) => (e: { target: HTMLInputElement }) =>
    setF({ ...f, [cle]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  function soumettre(e: FormEvent) {
    e.preventDefault()
    void lancer(async () => {
      const s = await api.post<Session>('auth/inscription/', f)
      definir(s)
      naviguer(routePour(s.destination), { replace: true })
    })
  }

  return (
    <Cadre>
      <form className="carte-formulaire large" onSubmit={soumettre} noValidate>
        <h1>Créer mon compte</h1>
        <p className="lead">Ton prof valide ton compte, puis tu arrives directement dans ta classe.</p>
        <div className="grille-2">
          <Champ id="prenom" label="Prénom" erreur={champs.prenom}>
            <input id="prenom" autoComplete="given-name" value={f.prenom} onChange={maj('prenom')} required />
          </Champ>
          <Champ id="nom" label="Nom" erreur={champs.nom}>
            <input id="nom" autoComplete="family-name" value={f.nom} onChange={maj('nom')} required />
          </Champ>
        </div>
        <Champ id="telephone" label="Numéro de téléphone" erreur={champs.telephone} aide="Il te servira d'identifiant.">
          <input id="telephone" type="tel" autoComplete="tel" inputMode="tel" value={f.telephone} onChange={maj('telephone')} required />
        </Champ>
        <Champ id="email" label="E-mail (facultatif)" erreur={champs.email}>
          <input id="email" type="email" autoComplete="email" value={f.email} onChange={maj('email')} />
        </Champ>
        <Champ id="mdp" label="Mot de passe" erreur={champs.mot_de_passe} aide="8 caractères au moins, pas uniquement des chiffres.">
          <input id="mdp" type="password" autoComplete="new-password" value={f.mot_de_passe} onChange={maj('mot_de_passe')} required />
        </Champ>
        <Champ id="code" label="Code de classe (si ton prof t'en a donné un)" erreur={champs.code_classe}>
          <input id="code" value={f.code_classe} onChange={maj('code_classe')} placeholder="TERM-2026-K7Q4P" autoCapitalize="characters" />
        </Champ>
        <div className="grille-2">
          <Champ id="niveau" label="Classe ou niveau" erreur={champs.niveau_declare}>
            <input id="niveau" value={f.niveau_declare} onChange={maj('niveau_declare')} placeholder="Terminale S2" />
          </Champ>
          <Champ id="etab" label="Établissement fréquenté" erreur={champs.etablissement_frequente}>
            <input id="etab" value={f.etablissement_frequente} onChange={maj('etablissement_frequente')} />
          </Champ>
        </div>
        <label className="case-ligne">
          <input type="checkbox" checked={f.est_mineur} onChange={maj('est_mineur')} /> J'ai moins de 18 ans
        </label>
        {f.est_mineur && (
          <Champ id="parent" label="Téléphone d'un parent" erreur={champs.telephone_parent}>
            <input id="parent" type="tel" inputMode="tel" value={f.telephone_parent} onChange={maj('telephone_parent')} />
          </Champ>
        )}
        <label className="case-ligne">
          <input type="checkbox" checked={f.accepte_conditions} onChange={maj('accepte_conditions')} />
          J'accepte les conditions d'utilisation et la politique de confidentialité
        </label>
        {champs.accepte_conditions && <p className="champ-erreur" role="alert">{champs.accepte_conditions}</p>}
        <MessageErreur erreur={erreur} />
        <button className="btn" type="submit" disabled={envoi}>
          {envoi ? 'Création…' : 'Créer mon compte'}
        </button>
        <p className="formulaire-pied">
          Déjà inscrit ? <Link to="/connexion">Connecte-toi</Link>
        </p>
      </form>
    </Cadre>
  )
}

export function Attente() {
  const { session, rafraichir } = useSession()
  const naviguer = useNavigate()
  const [verif, setVerif] = useState(false)
  if (session && session.destination.type !== 'attente') return <Navigate to={routePour(session.destination)} replace />
  return (
    <Cadre titre="Ton compte est en attente">
      <div className="encart">
        <p>
          Merci {session?.utilisateur.prenom} ! Ton prof doit valider ton compte. Dès que c'est fait, tu arriveras
          directement dans ta classe.
        </p>
        <button className="btn" type="button" disabled={verif}
          onClick={async () => {
            setVerif(true)
            const s = await rafraichir().finally(() => setVerif(false))
            if (s && s.destination.type !== 'attente') naviguer(routePour(s.destination), { replace: true })
          }}>
          {verif ? 'Vérification…' : 'Vérifier maintenant'}
        </button>
      </div>
    </Cadre>
  )
}

export function MotDePasse() {
  const { definir } = useSession()
  const naviguer = useNavigate()
  const [actuel, setActuel] = useState('')
  const [nouveau, setNouveau] = useState('')
  const { envoi, erreur, champs, lancer } = useEnvoi()
  return (
    <Cadre>
      <form className="carte-formulaire" noValidate onSubmit={(e) => {
        e.preventDefault()
        void lancer(async () => {
          const s = await api.post<Session>('moi/mot-de-passe/', { actuel, nouveau })
          definir(s)
          naviguer(routePour(s.destination), { replace: true })
        })
      }}>
        <h1>Choisis ton mot de passe</h1>
        <p className="lead">Remplace le mot de passe provisoire par un mot de passe que toi seul connais.</p>
        <Champ id="actuel" label="Mot de passe actuel" erreur={champs.actuel}>
          <input id="actuel" type="password" autoComplete="current-password" value={actuel} onChange={(e) => setActuel(e.target.value)} />
        </Champ>
        <Champ id="nouveau" label="Nouveau mot de passe" erreur={champs.nouveau}>
          <input id="nouveau" type="password" autoComplete="new-password" value={nouveau} onChange={(e) => setNouveau(e.target.value)} />
        </Champ>
        <MessageErreur erreur={erreur} />
        <button className="btn" type="submit" disabled={envoi}>Enregistrer</button>
      </form>
    </Cadre>
  )
}

export function ChoisirClasse() {
  const { definir } = useSession()
  const naviguer = useNavigate()
  const { donnees, erreur, chargement } = useDonnees(() => api.get<Groupe[]>('groupes/'), [])
  return (
    <Cadre titre="Dans quelle classe veux-tu travailler ?">
      {chargement && <Chargement />}
      <MessageErreur erreur={erreur} />
      <ul className="liste-cartes">
        {donnees?.map((g) => (
          <li key={g.id}>
            <button type="button" className="carte-choix" onClick={async () => {
              const s = await api.post<Session>('moi/groupe-courant/', { groupe: g.id })
              definir(s)
              naviguer(`/classe/${g.id}`)
            }}>
              <strong>{g.nom}</strong>
              <span>{g.organisation_nom} · {g.annee_libelle}</span>
            </button>
          </li>
        ))}
      </ul>
    </Cadre>
  )
}

export function AucuneClasse() {
  return (
    <Cadre titre="Aucune classe pour l'instant">
      <p className="encart">Ton compte est actif mais n'est rattaché à aucune classe. Demande à ton prof de t'y ajouter.</p>
    </Cadre>
  )
}
