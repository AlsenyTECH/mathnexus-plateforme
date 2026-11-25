import { useEffect, useState, type DependencyList, type ReactNode } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { ErreurApi } from '../api/client'
import { routePour, useSession } from '../session'

/** Charge une donnée de l'API et suit son état. */
export function useDonnees<T>(charger: () => Promise<T>, deps: DependencyList) {
  const [etat, setEtat] = useState<{ donnees?: T; erreur?: ErreurApi | Error; chargement: boolean }>({ chargement: true })
  const [version, setVersion] = useState(0)
  useEffect(() => {
    let actif = true
    setEtat((e) => ({ ...e, chargement: true }))
    charger()
      .then((donnees) => actif && setEtat({ donnees, chargement: false }))
      .catch((erreur) => actif && setEtat({ erreur, chargement: false }))
    return () => {
      actif = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version])
  return { ...etat, recharger: () => setVersion((v) => v + 1) }
}

export function Chargement({ texte = 'Chargement…' }: { texte?: string }) {
  return (
    <p className="chargement" role="status">
      {texte}
    </p>
  )
}

export function MessageErreur({ erreur }: { erreur?: Error | null }) {
  if (!erreur) return null
  return (
    <p className="erreur" role="alert">
      {erreur.message}
    </p>
  )
}

/** Protège une page : il faut une session, et le cas échéant le bon rôle. */
export function Protege({ children, role }: { children: ReactNode; role?: 'admin' }) {
  const { chargement, session } = useSession()
  const lieu = useLocation()
  if (chargement) return <Chargement />
  if (!session) return <Navigate to="/connexion" replace state={{ depuis: lieu.pathname }} />
  if (role === 'admin' && !session.utilisateur.est_admin) return <Navigate to={routePour(session.destination)} replace />
  return <>{children}</>
}

/** La barre du haut des pages hors lecteur. */
export function Cadre({ children, titre }: { children: ReactNode; titre?: string }) {
  const { session, deconnecter } = useSession()
  const u = session?.utilisateur
  const estProf = session?.destination.type === 'prof'
  return (
    <div className="cadre">
      <header className="cadre-haut">
        <Link to="/" className="cadre-marque">
          <img src="/logo.svg" alt="" width={32} height={32} />
          <span>Mathnexus</span>
        </Link>
        {u && (
          <nav className="cadre-nav" aria-label="Navigation principale">
            {u.est_admin && <Link to="/admin">Comptes</Link>}
            {u.est_admin && <Link to="/admin/classes">Classes</Link>}
            {u.est_admin && <Link to="/admin/contenus">Contenus</Link>}
            {(estProf || u.est_admin) && <Link to="/prof">Mes classes</Link>}
            <span className="cadre-nom">{u.prenom}</span>
            <button type="button" className="btn ghost" onClick={() => void deconnecter()}>
              Se déconnecter
            </button>
          </nav>
        )}
      </header>
      <main className="cadre-contenu">
        {titre && <h1 className="cadre-titre">{titre}</h1>}
        {children}
      </main>
    </div>
  )
}

export function BarreAvancement({ validees, total }: { validees: number; total: number }) {
  const pourcent = total ? Math.round((100 * validees) / total) : 0
  return (
    <div className="prog" aria-label={`${validees} étapes validées sur ${total}`}>
      <div className="prog-bar">
        <div className="prog-fill" style={{ width: `${pourcent}%` }} />
      </div>
      <p className="prog-txt">
        {validees} étape{validees > 1 ? 's' : ''} validée{validees > 1 ? 's' : ''} sur {total}
      </p>
    </div>
  )
}
