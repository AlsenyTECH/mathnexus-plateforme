// @ts-check
/**
 * Composant « évaluation » (format 2 des paquets).
 *
 * PARTAGÉ : ce fichier est la référence ; le moteur de contenu en garde une copie exacte,
 * surveillée par empreinte (comme controle.py pour paquet.py). D'où trois règles :
 *   1. aucune dépendance (ni React, ni bibliothèque) : du JavaScript du navigateur ;
 *   2. tout ce qui dépend de l'hôte arrive par `services` : la plateforme y branche son API
 *      (réponses gardées sur le serveur), le site public une correction locale ;
 *   3. les types sont écrits en commentaires JSDoc et vérifiés par TypeScript (`// @ts-check`).
 *
 * Interface commune à tous les composants partagés :
 *   monter(element, donnees, services) → demonter()
 *
 * Déroulé : accueil → une question par écran (chronomètre si durée) → correction.
 * Le temps passé sur chaque question est mesuré ici (question affichée ET onglet visible),
 * envoyé avec chaque réponse ; le serveur le plafonne par le temps réellement écoulé.
 *
 * Sécurité : le HTML reçu (consigne, énoncés, choix, explications) passe toujours par
 * `services.nettoyer` avant d'être inséré ; tout le reste est écrit avec textContent.
 */

/** @typedef {'choix_unique' | 'choix_multiple'} TypeQuestion */
/** @typedef {{cle: string, type: TypeQuestion, enonce: string, choix: string[], points: number}} Question */
/** @typedef {{choix: number[] | null, temps_ms: number}} ReponseEnregistree */
/** @typedef {{cle: string, bonnes: number[], explication: string, juste: boolean, points_obtenus: number}} Correction */
/**
 * @typedef {{cle: string, titre: string, role: string, consigne: string, duree_min: number | null,
 *   seuil: number | null, total: number, nombre_questions: number}} Presentation
 */
/**
 * @typedef {{id: string, commencee_le: string, terminee_le: string | null, fin: string | null,
 *   score: number | null, total: number, reussie: boolean | null}} ResumeTentative
 */
/** @typedef {Presentation & {en_cours: string | null, tentatives: ResumeTentative[]}} Accueil */
/**
 * @typedef {ResumeTentative & {evaluation: Presentation, secondes_restantes: number | null,
 *   terminee: boolean, questions: Question[], reponses: Record<string, ReponseEnregistree>,
 *   correction?: Correction[]}} EtatTentative
 */
/**
 * @typedef {object} Services
 * @property {(cle: string) => Promise<Accueil>} charger
 * @property {(cle: string) => Promise<EtatTentative>} commencer
 * @property {(id: string) => Promise<EtatTentative>} reprendre
 * @property {(id: string, question: string, choix: number[] | null, temps_ms: number) =>
 *   Promise<{temps_ms: number, secondes_restantes: number | null}>} repondre
 * @property {(id: string, temps: Record<string, number>) => Promise<EtatTentative>} terminer
 * @property {(html: string) => string} nettoyer   HTML sûr (DOMPurify sur la plateforme)
 * @property {(element: HTMLElement) => void} rendre  rend les formules TeX d'un élément
 * @property {(erreur: unknown) => boolean} [estClose]  l'erreur dit-elle « tentative terminée » ?
 * @property {() => number} [horloge]  millisecondes (performance.now par défaut ; remplacée dans les tests)
 */

const ROLES = { entree: "Test d'entrée", sortie: 'Test de sortie', evaluation: 'Évaluation' }
const LETTRES = 'abcdefghijkl'

/** 2.5 → « 2,5 » @param {number} n */
function nombre(n) {
  return String(n).replace('.', ',')
}

/** 272 secondes → « 04:32 » @param {number} secondes */
function minutes(secondes) {
  const m = Math.floor(secondes / 60)
  const s = secondes % 60
  return `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`
}

/**
 * Fabrique un élément : el('p', 'evd-infos', 'texte').
 * @param {string} balise
 * @param {string} [classe]
 * @param {string} [texte]
 * @returns {HTMLElement}
 */
function el(balise, classe, texte) {
  const e = document.createElement(balise)
  if (classe) e.className = classe
  if (texte !== undefined) e.textContent = texte
  return e
}

/** @param {string} texte @param {string} [classe] @returns {HTMLButtonElement} */
function bouton(texte, classe = 'btn') {
  const b = /** @type {HTMLButtonElement} */ (el('button', classe, texte))
  b.type = 'button'
  return b
}

/**
 * Monte une évaluation dans `element` (l'emplacement <div data-composant="evaluation">).
 * @param {HTMLElement} element
 * @param {{cle: string}} donnees
 * @param {Services} services
 * @returns {() => void} demonter : arrête les minuteurs et envoie le dernier temps mesuré
 */
export function monter(element, donnees, services) {
  const horloge = services.horloge ?? (() => performance.now())
  const racine = el('div', 'evd')
  element.replaceChildren(racine)

  // --- État -------------------------------------------------------------------------------
  /** @type {EtatTentative | null} */
  let tentative = null
  let index = 0                          // question affichée
  /** @type {Record<string, number[] | null>} */
  let choix = {}                         // réponses en cours, par clé de question
  /** @type {Record<string, number>} */
  let temps = {}                         // temps actif cumulé (ms), par clé de question
  /** @type {number | null} */
  let debut = null                       // horloge() quand la question affichée est devenue active
  /** @type {number | null} */
  let restant = null                     // secondes avant l'échéance (null : pas de chronomètre)
  /** @type {ReturnType<typeof setInterval> | null} */
  let minuteur = null
  let file = Promise.resolve()           // les envois partent un par un, dans l'ordre
  let detruit = false
  /** @type {HTMLElement | null} */
  let afficheurTemps = null
  /** @type {HTMLElement | null} */
  let statut = null

  const questionCourante = () => (tentative ? tentative.questions[index] : null)

  // --- Mesure du temps actif --------------------------------------------------------------
  // Le temps ne compte que si une question est à l'écran et que l'onglet est visible.
  function demarrerChrono() {
    if (questionCourante() && !tentative?.terminee && document.visibilityState !== 'hidden') debut = horloge()
  }
  function arreterChrono() {
    const q = questionCourante()
    if (q && debut !== null) temps[q.cle] = (temps[q.cle] ?? 0) + (horloge() - debut)
    debut = null
  }
  /** @param {string} cle */
  function tempsDe(cle) {
    const enCours = questionCourante()?.cle === cle && debut !== null ? horloge() - debut : 0
    return Math.round((temps[cle] ?? 0) + enCours)
  }
  function surVisibilite() {
    if (document.visibilityState === 'hidden') arreterChrono()
    else demarrerChrono()
  }
  document.addEventListener('visibilitychange', surVisibilite)

  // --- Échanges avec l'hôte ---------------------------------------------------------------
  /** @param {string} message */
  function signaler(message) {
    if (statut) statut.textContent = message
  }

  /** Envoie la réponse (et le temps) d'une question ; les envois sont mis en file. @param {string} cle */
  function envoyer(cle) {
    const t = tentative
    if (!t || t.terminee) return file
    const valeur = choix[cle] ?? null
    const ms = tempsDe(cle)
    file = file
      .then(() => services.repondre(t.id, cle, valeur, ms))
      .then((r) => {
        if (r.secondes_restantes !== null && r.secondes_restantes !== undefined) restant = r.secondes_restantes
        signaler('')
      })
      .catch((erreur) => {
        if (services.estClose?.(erreur)) return relireCorrection()
        signaler("Réponse non enregistrée : vérifie ta connexion. Elle sera renvoyée à ta prochaine action.")
      })
    return file
  }

  async function relireCorrection() {
    if (!tentative) return
    afficherCorrection(await services.reprendre(tentative.id))
  }

  /** @param {Promise<EtatTentative>} promesse */
  async function ouvrir(promesse) {
    try {
      const t = await promesse
      if (detruit) return
      if (t.terminee) return afficherCorrection(t)
      tentative = t
      choix = {}
      temps = {}
      for (const [cle, r] of Object.entries(t.reponses)) {
        choix[cle] = r.choix
        temps[cle] = r.temps_ms
      }
      restant = t.secondes_restantes
      // Reprise : on revient à la première question sans réponse.
      const libre = t.questions.findIndex((q) => !choix[q.cle])
      index = libre === -1 ? 0 : libre
      lancerMinuteur()
      afficherQuestion()
    } catch (erreur) {
      afficherErreur(erreur)
    }
  }

  async function terminer() {
    if (!tentative || tentative.terminee) return
    arreterMinuteur()
    arreterChrono()
    await file
    /** @type {Record<string, number>} */
    const tous = {}
    for (const q of tentative.questions) tous[q.cle] = tempsDe(q.cle)
    try {
      afficherCorrection(await services.terminer(tentative.id, tous))
    } catch (erreur) {
      if (services.estClose?.(erreur)) return relireCorrection()
      signaler("La fin de l'évaluation n'a pas été enregistrée : vérifie ta connexion et réessaie.")
      lancerMinuteur()
      demarrerChrono()
    }
  }

  // --- Chronomètre de l'évaluation (l'échéance réelle est tenue par le serveur) ------------
  function lancerMinuteur() {
    arreterMinuteur()
    if (restant === null) return
    minuteur = setInterval(() => {
      if (restant === null) return
      restant = Math.max(0, restant - 1)
      dessinerTemps()
      if (restant === 0) void terminer()
    }, 1000)
  }
  function arreterMinuteur() {
    if (minuteur !== null) clearInterval(minuteur)
    minuteur = null
  }
  function dessinerTemps() {
    if (!afficheurTemps || restant === null) return
    afficheurTemps.textContent = minutes(restant)
    afficheurTemps.classList.toggle('bas', restant <= 60)
  }

  // --- Écrans ------------------------------------------------------------------------------
  /** @param {Presentation} p @param {HTMLElement} parent */
  function entete(p, parent) {
    parent.append(el('p', 'lab', ROLES[/** @type {keyof typeof ROLES} */ (p.role)] ?? 'Évaluation'))
    parent.append(el('h3', 'evd-titre', p.titre))
  }

  /** @param {Presentation} p */
  function infos(p) {
    const morceaux = [
      `${p.nombre_questions} question${p.nombre_questions > 1 ? 's' : ''}`,
      `${nombre(p.total)} point${p.total > 1 ? 's' : ''}`,
    ]
    if (p.seuil !== null) morceaux.push(`réussi à partir de ${nombre(p.seuil)}`)
    morceaux.push(p.duree_min ? `${p.duree_min} min chronométrées` : 'sans limite de temps')
    return el('p', 'evd-infos', morceaux.join(' · '))
  }

  /** @param {unknown} erreur */
  function afficherErreur(erreur) {
    const message = erreur instanceof Error ? erreur.message : String(erreur)
    racine.replaceChildren(el('p', 'evd-erreur', `Évaluation indisponible : ${message}`))
  }

  async function afficherAccueil() {
    let a
    try {
      a = await services.charger(donnees.cle)
    } catch (erreur) {
      return afficherErreur(erreur)
    }
    if (detruit) return
    const boite = el('div', 'evd-accueil')
    entete(a, boite)
    if (a.consigne) {
      const consigne = el('div', 'evd-consigne')
      consigne.innerHTML = services.nettoyer(a.consigne)
      boite.append(consigne)
    }
    boite.append(infos(a))
    if (a.tentatives.length) {
      const liste = el('ul', 'evd-historique')
      for (const t of a.tentatives.slice(0, 5)) {
        const date = new Date(t.commencee_le).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
        const issue = t.reussie === true ? ' · réussie' : t.reussie === false ? ' · pas encore réussie' : ''
        liste.append(el('li', '', `${date} : ${nombre(t.score ?? 0)} / ${nombre(t.total)}${issue}`))
      }
      boite.append(el('p', 'evd-sous-titre', 'Tes tentatives'), liste)
    }
    const go = bouton(a.en_cours ? 'Reprendre' : a.tentatives.length ? 'Recommencer' : 'Commencer')
    const enCours = a.en_cours
    go.addEventListener('click', () => {
      go.disabled = true
      void ouvrir(enCours ? services.reprendre(enCours) : services.commencer(donnees.cle))
    })
    const actions = el('div', 'evd-actions')
    actions.append(go)
    boite.append(actions)
    racine.replaceChildren(boite)
    services.rendre(boite)
  }

  /** @param {number} i */
  function aller(i) {
    arreterChrono()
    const q = questionCourante()
    if (q) void envoyer(q.cle) // enregistre le temps de la question qu'on quitte
    index = i
    afficherQuestion()
  }

  /** @param {Question} q @param {number} k */
  function choisir(q, k) {
    const actuel = choix[q.cle] ?? []
    let nouveau
    if (q.type === 'choix_unique') nouveau = [k]
    else nouveau = actuel.includes(k) ? actuel.filter((x) => x !== k) : [...actuel, k].sort((a, b) => a - b)
    choix[q.cle] = nouveau.length ? nouveau : null
    arreterChrono() // compte le temps jusqu'au clic ; afficherQuestion le relance
    void envoyer(q.cle)
    afficherQuestion()
  }

  function afficherQuestion() {
    const t = tentative
    const q = questionCourante()
    if (!t || !q) return
    const n = t.questions.length
    const boite = el('div', 'evd-question')

    // Barre : position, chronomètre
    const barre = el('div', 'evd-barre')
    barre.append(el('p', 'evd-position', `Question ${index + 1} / ${n}`))
    afficheurTemps = null
    if (restant !== null) {
      afficheurTemps = el('p', 'evd-temps')
      afficheurTemps.setAttribute('role', 'timer')
      barre.append(afficheurTemps)
    }
    boite.append(barre)

    // Pastilles : aller directement à une question ; celles déjà répondues sont marquées
    const pastilles = el('div', 'evd-pastilles')
    t.questions.forEach((autre, i) => {
      const p = bouton(String(i + 1), 'evd-pastille' + (choix[autre.cle] ? ' repondue' : '') + (i === index ? ' actuelle' : ''))
      p.setAttribute('aria-label', `Question ${i + 1}${choix[autre.cle] ? ' (répondue)' : ''}`)
      if (i === index) p.setAttribute('aria-current', 'step')
      p.addEventListener('click', () => i !== index && aller(i))
      pastilles.append(p)
    })
    boite.append(pastilles)

    const enonce = el('div', 'evd-enonce')
    enonce.innerHTML = services.nettoyer(q.enonce)
    boite.append(enonce)
    const multiple = q.type === 'choix_multiple'
    boite.append(el('p', 'evd-aide', (multiple ? 'Plusieurs réponses possibles' : 'Une seule réponse') +
      ` · ${nombre(q.points)} point${q.points > 1 ? 's' : ''}`))

    // Les choix : de vrais boutons, annoncés comme boutons radio ou cases par les lecteurs d'écran
    const liste = el('div', 'evd-choix')
    liste.setAttribute('role', multiple ? 'group' : 'radiogroup')
    q.choix.forEach((html, k) => {
      const coche = (choix[q.cle] ?? []).includes(k)
      const b = bouton('', 'evd-option' + (coche ? ' choisie' : ''))
      b.setAttribute('role', multiple ? 'checkbox' : 'radio')
      b.setAttribute('aria-checked', String(coche))
      const contenu = el('span', 'evd-option-texte')
      contenu.innerHTML = services.nettoyer(html)
      b.append(el('span', 'evd-lettre', `${LETTRES[k]})`), contenu)
      b.addEventListener('click', () => choisir(q, k))
      liste.append(b)
    })
    boite.append(liste)

    statut = el('p', 'evd-statut')
    statut.setAttribute('aria-live', 'polite')
    boite.append(statut)

    // Navigation et fin
    const nav = el('div', 'evd-nav')
    const prec = bouton('← Question précédente', 'btn ghost')
    prec.disabled = index === 0
    prec.addEventListener('click', () => aller(index - 1))
    const suiv = bouton('Question suivante →', 'btn ghost')
    suiv.disabled = index === n - 1
    suiv.addEventListener('click', () => aller(index + 1))
    const fin = bouton("Terminer l'évaluation")
    fin.addEventListener('click', () => {
      const sans = t.questions.filter((x) => !choix[x.cle]).length
      if (!sans) return void terminer()
      confirmation.hidden = false
      texteConfirmation.textContent = `${sans} question${sans > 1 ? 's' : ''} sans réponse. Terminer quand même ?`
    })
    nav.append(prec, suiv, fin)
    boite.append(nav)

    // Confirmation dans la page (pas de fenêtre du navigateur)
    const confirmation = el('div', 'evd-confirmation')
    const texteConfirmation = el('p')
    confirmation.hidden = true
    const oui = bouton('Oui, terminer')
    oui.addEventListener('click', () => void terminer())
    const non = bouton('Continuer', 'btn ghost')
    non.addEventListener('click', () => { confirmation.hidden = true })
    confirmation.append(texteConfirmation, oui, non)
    boite.append(confirmation)

    racine.replaceChildren(boite)
    dessinerTemps()
    services.rendre(boite)
    demarrerChrono()
  }

  /** @param {EtatTentative} t */
  function afficherCorrection(t) {
    arreterMinuteur()
    debut = null
    tentative = t
    afficheurTemps = null
    const p = t.evaluation
    const boite = el('div', 'evd-correction')
    entete(p, boite)

    const resultat = el('div', 'evd-resultat' + (t.reussie === false ? ' rate' : ''))
    resultat.append(el('p', 'evd-score', `${nombre(t.score ?? 0)} / ${nombre(t.total)}`))
    if (t.reussie !== null && p.seuil !== null) {
      resultat.append(el('p', 'evd-verdict', t.reussie
        ? `Réussi (il fallait ${nombre(p.seuil)} points).`
        : `Pas encore : il faut ${nombre(p.seuil)} points. Relis l'étape puis recommence.`))
    }
    if (t.fin === 'temps_ecoule') resultat.append(el('p', 'evd-verdict', 'Temps écoulé : les réponses données avant la fin ont été corrigées.'))
    boite.append(resultat)

    const corrections = new Map((t.correction ?? []).map((c) => [c.cle, c]))
    t.questions.forEach((q, i) => {
      const c = corrections.get(q.cle)
      const donnee = t.reponses[q.cle]?.choix ?? []
      const bloc = el('div', 'evd-corr ' + (c?.juste ? 'juste' : 'faux'))
      const titre = el('p', 'evd-corr-titre',
        `Question ${i + 1} — ${c?.juste ? 'juste' : donnee.length ? 'faux' : 'sans réponse'} · ` +
        `${nombre(c?.points_obtenus ?? 0)} / ${nombre(q.points)}`)
      const enonce = el('div', 'evd-enonce')
      enonce.innerHTML = services.nettoyer(q.enonce)
      const liste = el('ul', 'evd-corr-choix')
      q.choix.forEach((html, k) => {
        const bonne = c?.bonnes.includes(k) ?? false
        const choisie = donnee.includes(k)
        const li = el('li', (bonne ? 'bonne' : '') + (choisie ? ' choisie' : ''))
        const texte = el('span')
        texte.innerHTML = services.nettoyer(html)
        li.append(el('span', 'evd-lettre', `${LETTRES[k]})`), texte)
        const marques = [bonne ? 'bonne réponse' : '', choisie ? 'ta réponse' : ''].filter(Boolean)
        if (marques.length) li.append(el('span', 'evd-marque', marques.join(' · ')))
        liste.append(li)
      })
      bloc.append(titre, enonce, liste)
      if (c?.explication) {
        const ex = el('div', 'evd-explication')
        ex.innerHTML = services.nettoyer(c.explication)
        bloc.append(ex)
      }
      boite.append(bloc)
    })

    const encore = bouton('Recommencer', 'btn ghost')
    encore.addEventListener('click', () => {
      encore.disabled = true
      void ouvrir(services.commencer(donnees.cle))
    })
    const actions = el('div', 'evd-actions')
    actions.append(encore)
    boite.append(actions)
    racine.replaceChildren(boite)
    services.rendre(boite)
  }

  void afficherAccueil()

  return function demonter() {
    detruit = true
    arreterMinuteur()
    arreterChrono()
    document.removeEventListener('visibilitychange', surVisibilite)
    const q = questionCourante()
    if (q && tentative && !tentative.terminee) void envoyer(q.cle) // dernier temps mesuré
  }
}
