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
  /** Les classes où le compte travaille comme élève (bouton « Espace élève »). */
  classes_eleve: { id: string; nom: string }[]
  /** Le compte enseigne (ou administre) : bouton « Espace prof ». */
  enseigne: boolean
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

// --- Devoirs ---------------------------------------------------------------------------

export type TypeDevoir = 'etape' | 'evaluation' | 'libre'
export type StatutDevoir = 'a_faire' | 'en_retard' | 'rendu' | 'fait' | 'corrige'

export interface Devoir {
  id: string
  groupe: string
  groupe_nom: string
  type: TypeDevoir
  titre: string
  consigne: string
  date_limite: string | null
  note_sur: number
  parcours: string | null
  parcours_titre: string | null
  cle_etape: string | null
  cle_evaluation: string | null
  eleve: string | null
  eleve_nom: string | null
  cree_le: string
  duree_min: number | null
  sujet_masque: boolean
  pieces: PieceJointe[]
}

export interface PieceJointe {
  id: string
  nom: string
  type_mime: string
  taille: number
  url: string
}

export interface EtatDevoir {
  statut: StatutDevoir
  commence_le: string | null
  fin_prevue: string | null
  hors_temps: boolean
  rendu_le: string | null
  note: number | null
  corrige_le: string | null
  score: number | null
  total: number | null
  tentative_terminee_le: string | null
}

export interface PhotoCopie {
  id: string
  taille: number
  url: string
}

export interface Rendu {
  texte: string
  rendu_le: string | null
  note: number | null
  commentaire: string
  correction: string
  corrige_le: string | null
  photos: PhotoCopie[]
  photos_correction: PhotoCopie[]
}

export interface DevoirProf extends Devoir {
  effectif: number
  a_corriger: number
  termines: number
  corriges: number
}

export type DevoirEleve = Devoir & EtatDevoir & { vue: 'eleve'; rendu: Rendu | null }

export type SuiviDevoir = Devoir & {
  vue: 'prof'
  eleves: (EtatDevoir & { eleve: string; prenom: string; nom: string })[]
}

export type CopieEleve = EtatDevoir & {
  devoir: Devoir
  eleve: { id: string; prenom: string; nom: string }
  rendu: Rendu | null
}

export interface CopieACorriger {
  devoir: string
  titre: string
  groupe: string
  groupe_nom: string
  eleve: string
  prenom: string
  nom: string
  rendu_le: string
}

export interface EvaluationResume {
  cle: string
  titre: string
  cle_etape: string
  etape_titre: string
  duree_min: number | null
  total: number
}

// --- Séance du jour, carnet d'erreurs, suivi -------------------------------------------------

export interface SeanceDuJour {
  date: string
  devoirs: {
    id: string; titre: string; type: TypeDevoir; date_limite: string | null; duree_min: number | null
    statut: StatutDevoir; commence_le: string | null; pour_aujourd_hui: boolean; sujet_masque: boolean
  }[]
  etapes: {
    parcours: string; parcours_titre: string; cle: string; titre: string; duree_min: number | null
    partie: string; commencee: boolean
  }[]
  autres_parcours: number
  revisions: number
}

export interface EntreeCarnet {
  id: string
  groupe: string
  question: { enonce: string; choix: string[]; type: string; multiple: boolean }
  evaluation: string
  parcours: string
  parcours_titre: string
  cle_etape: string
  etape_titre: string
  ajoutee_le: string
  a_revoir_le: string
  due: boolean
  revisions: number
  reussites_de_suite: number
  maitrisee_le: string | null
}

export interface Carnet {
  a_revoir: number
  en_cours: number
  maitrisees: number
  entrees: EntreeCarnet[]
}

export interface ReponseCarnet {
  juste: boolean
  bonnes: number[]
  explication: string
  entree: EntreeCarnet
}

export interface LigneSuivi {
  eleve: string
  prenom: string
  nom: string
  devoirs: number
  termines: number
  en_retard: number
  a_corriger: number
  moyenne: number | null
  etapes_validees: number
  etapes_total: number
  carnet_a_revoir: number
  carnet_maitrisees: number
  derniere_activite: string | null
}

export interface FicheEleve extends LigneSuivi {
  telephone: string
  telephone_parent: string
  derniere_connexion: string | null
  liste_devoirs: (EtatDevoir & { id: string; titre: string; type: TypeDevoir; date_limite: string | null; note_sur: number; sur_20: number | null })[]
  evaluations: { titre: string; parcours_titre: string; score: number | null; total: number | null; terminee_le: string; reussie: boolean | null }[]
  progression: { slug: string; titre: string; validees: number; total: number; derniere_ouverture: string | null }[]
}

export interface Bilan {
  jours: number
  texte: string
  telephone_parent: string
  telephone: string
  travaux_faits: number
  travaux_donnes: number
  en_retard: number
  etapes: number
  moyenne: number | null
}
