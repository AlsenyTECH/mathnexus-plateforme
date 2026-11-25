import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api } from './api/client'
import type { Destination, Session } from './api/types'

interface ContexteSession {
  chargement: boolean
  session: Session | null
  rafraichir: () => Promise<Session | null>
  definir: (s: Session) => void
  deconnecter: () => Promise<void>
}

const Contexte = createContext<ContexteSession | null>(null)

export function FournisseurSession({ children }: { children: ReactNode }) {
  const [chargement, setChargement] = useState(true)
  const [session, setSession] = useState<Session | null>(null)

  const rafraichir = useCallback(async () => {
    try {
      const r = await api.get<Session | { utilisateur: null; destination: null }>('auth/session/')
      const s = r.utilisateur ? (r as Session) : null
      setSession(s)
      return s
    } finally {
      setChargement(false)
    }
  }, [])

  useEffect(() => {
    rafraichir().catch(() => setChargement(false))
  }, [rafraichir])

  const deconnecter = useCallback(async () => {
    try {
      await api.post('auth/deconnexion/')
    } finally {
      setSession(null)
    }
  }, [])

  return (
    <Contexte.Provider value={{ chargement, session, rafraichir, definir: setSession, deconnecter }}>
      {children}
    </Contexte.Provider>
  )
}

export function useSession(): ContexteSession {
  const c = useContext(Contexte)
  if (!c) throw new Error('useSession doit être utilisé dans <FournisseurSession>')
  return c
}

/** Traduit la destination renvoyée par l'API en adresse de l'application. */
export function routePour(destination: Destination): string {
  switch (destination.type) {
    case 'admin':
      return '/admin'
    case 'attente':
      return '/attente'
    case 'changer_mot_de_passe':
      return '/mot-de-passe'
    case 'prof':
      return '/prof'
    case 'groupe':
      return `/classe/${destination.groupe}`
    case 'choix_groupe':
      return '/choisir'
    case 'aucun_groupe':
      return '/aucune-classe'
  }
}
