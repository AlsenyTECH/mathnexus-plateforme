import type { Sommaire } from './api/types'

/** La première étape accessible non validée : là où l'élève doit reprendre. */
export function etapeAReprendre(s: Sommaire): string | null {
  const etapes = s.parties.flatMap((p) => p.etapes).filter((e) => e.accessible)
  return (etapes.find((e) => !e.validee) ?? etapes[0])?.cle ?? null
}

/** Le numéro de chaque étape dans tout le parcours (1, 2, 3… à travers les parties). */
export function numeroterEtapes(s: Sommaire): Record<string, number> {
  const numeros: Record<string, number> = {}
  s.parties.flatMap((p) => p.etapes).forEach((e, i) => (numeros[e.cle] = i + 1))
  return numeros
}

/** Lit une liste collée depuis un tableur : « Prénom ; Nom ; Téléphone » par ligne. */
export function lireListe(texte: string): { prenom: string; nom: string; telephone: string }[] {
  return texte
    .split(/\r?\n/)
    .map((l) => l.split(/[;\t,]/).map((x) => x.trim()))
    .filter((c) => c.length >= 3 && c[0] && c[2])
    .map(([prenom, nom, telephone]) => ({ prenom, nom, telephone }))
}

/**
 * Réduit une photo de copie avant l'envoi : 1600 px au plus sur le grand côté, en JPEG.
 * Une photo de téléphone passe ainsi de 3-5 Mo à environ 300 Ko (moins de données mobiles).
 * Si le navigateur ne sait pas la lire, on envoie le fichier d'origine (le serveur vérifie).
 */
export async function compresserImage(fichier: File, cote = 1600, qualite = 0.82): Promise<Blob> {
  try {
    const image = await createImageBitmap(fichier)
    const echelle = Math.min(1, cote / Math.max(image.width, image.height))
    const toile = document.createElement('canvas')
    toile.width = Math.round(image.width * echelle)
    toile.height = Math.round(image.height * echelle)
    toile.getContext('2d')?.drawImage(image, 0, 0, toile.width, toile.height)
    image.close()
    const blob = await new Promise<Blob | null>((ok) => toile.toBlob(ok, 'image/jpeg', qualite))
    return blob ?? fichier
  } catch {
    return fichier
  }
}
