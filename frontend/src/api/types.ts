/** Les formes des réponses de l'API (voir le README du dépôt). */

export type Destination =
  | { type: 'admin' }
  | { type: 'attente' }
  | { type: 'changer_mot_de_passe' }
  | { type: 'prof' }
  | { type: 'groupe'; groupe: string }
  | { type: 'choix_groupe'; groupes: string[] }
  | { type: 'aucun_groupe' }

export interface Utilisateur {
  id: string
  prenom: string
  nom: string
  telephone: string
  email: string
  statut: 'en_attente' | 'actif' | 'suspendu' | 'archive'
  doit_changer_mot_de_passe: boolean
  est_admin: boolean
}

export interface Session {
  utilisateur: Utilisateur
  destination: Destination
}

export interface Groupe {
  id: string
  nom: string
  cycle: 'lycee' | 'prepa' | 'universite'
  organisation: string
  organisation_nom: string
  annee: number
  annee_libelle: string
  mon_role: 'eleve' | 'prof' | 'admin' | null
}

export interface Avancement {
  validees: number
  total: number
}

export interface ResumeParcours {
  slug: string
  titre: string
  matiere: string
  description: string
  ouverture: 'tout' | 'progressive'
  version: number
  avancement: Avancement
}

export type Acces = 'public' | 'inscrit' | 'premium'
export type Raison = 'premium' | 'pas_encore_ouverte' | null

export interface EtapeSommaire {
  cle: string
  titre: string
  duree_min: number | null
  acces: Acces
  ouverte: boolean
  accessible: boolean
  raison: Raison
  validee: boolean
  /** Ouverte pour les élèves (utile au prof, qui voit tout). */
  ouverte_eleves: boolean
}

export interface PartieSommaire {
  cle: string
  titre: string
  etapes: EtapeSommaire[]
}

export interface Sommaire extends ResumeParcours {
  parties: PartieSommaire[]
}

export interface EtapeLue {
  cle: string
  titre: string
  partie: string
  duree_min: number | null
  acces: Acces
  html: string
  validee: boolean
  precedente: string | null
  suivante: string | null
}

export interface Membre {
  utilisateur: string
  prenom: string
  nom: string
  role: 'eleve' | 'prof'
  valide_le: string | null
}

export interface TableauProgression {
  etapes: { cle: string; titre: string }[]
  eleves: { utilisateur: string; prenom: string; nom: string; validees: string[]; derniere_activite: string | null }[]
}

export interface CompteEnAttente {
  id: string
  prenom: string
  nom: string
  telephone: string
  email: string
  niveau_declare: string
  etablissement_frequente: string
  telephone_parent: string
  date_joined: string
  demandes: { inscription: string; groupe: string; groupe_nom: string }[]
}

export interface GroupeAdmin {
  id: string
  nom: string
  cycle: Groupe['cycle']
  organisation: string
  annee: number
  code_inscription: string
  inscriptions_ouvertes: boolean
  validation_automatique: boolean
  archive: boolean
  effectif: number
}

export interface ResumeVersion {
  id: string
  parcours: string
  numero: number
  statut: 'brouillon' | 'publiee' | 'archivee'
  importee_le: string
  publiee_le: string | null
  nombre_etapes: number
}

export interface ParcoursCatalogue {
  slug: string
  titre: string
  matiere: string
  cycle: string
  versions: ResumeVersion[]
  groupes: string[]
}
