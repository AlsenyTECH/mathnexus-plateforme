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
