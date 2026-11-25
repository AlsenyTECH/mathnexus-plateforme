/**
 * Client de l'API Django.
 *
 * L'application et l'API partagent la même origine : la session est un cookie HttpOnly
 * que le navigateur envoie tout seul. Pour toute requête qui modifie quelque chose,
 * Django exige le jeton CSRF : on le lit dans le cookie `csrftoken` et on le renvoie
 * dans l'en-tête X-CSRFToken.
 */

export class ErreurApi extends Error {
  statut: number
  donnees: Record<string, unknown>

  constructor(statut: number, donnees: Record<string, unknown>) {
    super(messageDErreur(statut, donnees))
    this.statut = statut
    this.donnees = donnees
  }

  /** Les erreurs par champ renvoyées par DRF : { telephone: ["…"], mot_de_passe: ["…"] } */
  champs(): Record<string, string> {
    const resultat: Record<string, string> = {}
    for (const [cle, valeur] of Object.entries(this.donnees)) {
      if (cle === 'detail') continue
      resultat[cle] = Array.isArray(valeur) ? valeur.join(' ') : String(valeur)
    }
    return resultat
  }
}

function messageDErreur(statut: number, donnees: Record<string, unknown>): string {
  if (typeof donnees.detail === 'string') return donnees.detail
  if (statut === 429) return 'Trop de tentatives. Attends une minute avant de réessayer.'
  if (statut === 403) return "Tu n'as pas accès à cette page."
  if (statut === 404) return 'Page introuvable.'
  if (statut >= 500) return 'Le serveur rencontre un problème. Réessaie dans un instant.'
  return 'La demande a été refusée.'
}

export function lireCookie(nom: string): string | null {
  const trouve = document.cookie.split('; ').find((c) => c.startsWith(nom + '='))
  return trouve ? decodeURIComponent(trouve.slice(nom.length + 1)) : null
}

let jetonDemande: Promise<void> | null = null

/** Pose le cookie CSRF une fois, au premier besoin. */
async function assurerJetonCsrf(): Promise<void> {
  if (lireCookie('csrftoken')) return
  jetonDemande ??= fetch('/api/auth/csrf/', { credentials: 'same-origin' }).then(() => undefined)
  await jetonDemande
  jetonDemande = null
}

type Methode = 'GET' | 'POST' | 'PATCH' | 'DELETE'

export async function requete<T>(methode: Methode, chemin: string, corps?: unknown): Promise<T> {
  const entetes: Record<string, string> = { Accept: 'application/json' }
  let body: BodyInit | undefined
  if (methode !== 'GET') {
    await assurerJetonCsrf()
    entetes['X-CSRFToken'] = lireCookie('csrftoken') ?? ''
    if (corps instanceof FormData) {
      body = corps
    } else if (corps !== undefined) {
      entetes['Content-Type'] = 'application/json'
      body = JSON.stringify(corps)
    }
  }
  const reponse = await fetch('/api/' + chemin.replace(/^\//, ''), {
    method: methode,
    headers: entetes,
    body,
    credentials: 'same-origin',
  })
  if (reponse.status === 204) return undefined as T
  const texte = await reponse.text()
  let donnees: unknown = {}
  try {
    donnees = texte ? JSON.parse(texte) : {}
  } catch {
    donnees = { detail: texte.slice(0, 200) }
  }
  if (!reponse.ok) throw new ErreurApi(reponse.status, (donnees ?? {}) as Record<string, unknown>)
  return donnees as T
}

export const api = {
  get: <T>(chemin: string) => requete<T>('GET', chemin),
  post: <T>(chemin: string, corps?: unknown) => requete<T>('POST', chemin, corps),
  patch: <T>(chemin: string, corps?: unknown) => requete<T>('PATCH', chemin, corps),
  delete: <T>(chemin: string) => requete<T>('DELETE', chemin),
}
