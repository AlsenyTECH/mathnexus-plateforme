import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Cadre, Chargement, Protege } from './composants/communs'
import { AucuneClasse, Attente, ChoisirClasse, Connexion, Inscription, MotDePasse } from './pages/Entree'
import { FournisseurSession, routePour, useSession } from './session'

// Chargés à la demande : la page de connexion reste légère sur un téléphone en 3G.
const eleve = () => import('./pages/Eleve')
const prof = () => import('./pages/Prof')
const admin = () => import('./pages/Admin')
const devoirs = () => import('./pages/Devoirs')
const suivi = () => import('./pages/Suivi')
const TableauDeBordClasse = lazy(() => eleve().then((m) => ({ default: m.TableauDeBordClasse })))
const SommaireParcours = lazy(() => eleve().then((m) => ({ default: m.SommaireParcours })))
const LecteurEtape = lazy(() => eleve().then((m) => ({ default: m.LecteurEtape })))
const MesClasses = lazy(() => prof().then((m) => ({ default: m.MesClasses })))
const ClasseProf = lazy(() => prof().then((m) => ({ default: m.ClasseProf })))
const ProgressionProf = lazy(() => prof().then((m) => ({ default: m.ProgressionProf })))
const PageDevoirEleve = lazy(() => devoirs().then((m) => ({ default: m.PageDevoirEleve })))
const SuiviDevoir = lazy(() => devoirs().then((m) => ({ default: m.SuiviDevoir })))
const CorrigerCopie = lazy(() => devoirs().then((m) => ({ default: m.CorrigerCopie })))
const PageCarnet = lazy(() => suivi().then((m) => ({ default: m.PageCarnet })))
const PageFicheEleve = lazy(() => suivi().then((m) => ({ default: m.PageFicheEleve })))
const ComptesEnAttente = lazy(() => admin().then((m) => ({ default: m.ComptesEnAttente })))
const Classes = lazy(() => admin().then((m) => ({ default: m.Classes })))
const Contenus = lazy(() => admin().then((m) => ({ default: m.Contenus })))

/** L'accueil envoie chacun là où l'API l'attend. */
function Accueil() {
  const { chargement, session } = useSession()
  if (chargement) return <Chargement />
  return <Navigate to={session ? routePour(session.destination) : '/connexion'} replace />
}

function Introuvable() {
  return (
    <Cadre titre="Page introuvable">
      <p className="encart">Cette page n'existe pas.</p>
    </Cadre>
  )
}

export function Itineraires() {
  return (
    <Suspense fallback={<Chargement />}>
    <Routes>
      <Route path="/" element={<Accueil />} />
      <Route path="/connexion" element={<Connexion />} />
      <Route path="/inscription" element={<Inscription />} />
      <Route path="/attente" element={<Protege><Attente /></Protege>} />
      <Route path="/mot-de-passe" element={<Protege><MotDePasse /></Protege>} />
      <Route path="/choisir" element={<Protege><ChoisirClasse /></Protege>} />
      <Route path="/aucune-classe" element={<Protege><AucuneClasse /></Protege>} />
      <Route path="/classe/:groupe" element={<Protege><TableauDeBordClasse /></Protege>} />
      <Route path="/classe/:groupe/devoirs/:devoir" element={<Protege><PageDevoirEleve /></Protege>} />
      <Route path="/classe/:groupe/carnet" element={<Protege><PageCarnet /></Protege>} />
      <Route path="/classe/:groupe/:slug" element={<Protege><SommaireParcours /></Protege>} />
      <Route path="/classe/:groupe/:slug/:cle" element={<Protege><LecteurEtape /></Protege>} />
      <Route path="/prof" element={<Protege><MesClasses /></Protege>} />
      <Route path="/prof/:groupe" element={<Protege><ClasseProf /></Protege>} />
      <Route path="/prof/:groupe/devoirs/:devoir" element={<Protege><SuiviDevoir /></Protege>} />
      <Route path="/prof/:groupe/eleves/:eleve" element={<Protege><PageFicheEleve /></Protege>} />
      <Route path="/prof/:groupe/devoirs/:devoir/:eleve" element={<Protege><CorrigerCopie /></Protege>} />
      <Route path="/prof/:groupe/:slug" element={<Protege><ProgressionProf /></Protege>} />
      <Route path="/admin" element={<Protege role="admin"><ComptesEnAttente /></Protege>} />
      <Route path="/admin/classes" element={<Protege role="admin"><Classes /></Protege>} />
      <Route path="/admin/contenus" element={<Protege role="admin"><Contenus /></Protege>} />
      <Route path="*" element={<Introuvable />} />
    </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <FournisseurSession>
      <BrowserRouter>
        <Itineraires />
      </BrowserRouter>
    </FournisseurSession>
  )
}
