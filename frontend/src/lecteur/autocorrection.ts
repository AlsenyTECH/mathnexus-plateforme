/**
 * Les petites interactions des pages « cahier » d'origine, refaites ici sans leur JavaScript
 * (un paquet ne contient jamais de script) :
 *
 * - les QCM d'auto-vérification des Fondements MCS : <div class="qcm" data-role="entree|sortie"
 *   data-seuil="3"> avec des <fieldset class="qcm-q" data-bonne="1"> et un bouton « Corriger » ;
 * - les QCM à boutons de Réseau & Sécurité : <div class="qcm" data-answer="1"> avec des .opt ;
 * - les onglets des « quatre temps » d'un nœud : .onglet[data-t] et .panneau[data-t].
 *
 * Ces QCM servent à l'élève à se situer : la correction est déjà dans la page (rien de secret),
 * elle est donc faite ici, dans le navigateur. Les évaluations notées passent, elles, par le
 * serveur (module evaluations).
 */

type Rendre = (el: HTMLElement) => void

/** QCM d'entrée et de sortie des Fondements : on coche, puis « Corriger ». */
function qcmAvecBouton(qcm: HTMLElement, numero: number, rendre: Rendre): void {
  const questions = Array.from(qcm.querySelectorAll<HTMLElement>('.qcm-q[data-bonne]'))
  // Le <form> d'origine isolait les boutons radio ; ici on rend leurs noms uniques dans l'étape.
  questions.forEach((q, i) => {
    q.querySelectorAll<HTMLInputElement>('input[type="radio"]').forEach((r) => { r.name = `qcm${numero}-q${i}` })
  })
  const bouton = qcm.querySelector<HTMLButtonElement>('.qcm-bas button') ?? qcm.querySelector<HTMLButtonElement>('button')
  const resultat = qcm.querySelector<HTMLElement>('.qcm-res')
  bouton?.addEventListener('click', () => {
    let bonnes = 0
    let repondues = 0
    for (const q of questions) {
      const bonne = Number(q.dataset.bonne)
      const options = Array.from(q.querySelectorAll<HTMLElement>('.qcm-o'))
      options.forEach((o) => o.classList.remove('juste', 'faux'))
      const choisi = q.querySelector<HTMLInputElement>('input:checked')
      if (!choisi) continue
      repondues++
      const ok = Number(choisi.value) === bonne
      if (ok) bonnes++
      choisi.closest('.qcm-o')?.classList.add(ok ? 'juste' : 'faux')
      options[bonne]?.classList.add('juste')
      const explication = q.querySelector<HTMLElement>('.qcm-x')
      if (explication) explication.hidden = false
    }
    if (!resultat) return
    resultat.hidden = false
    const total = questions.length
    if (repondues < total) {
      resultat.className = 'qcm-res ko'
      resultat.textContent = 'Réponds à toutes les questions.'
      return
    }
    const reussi = bonnes >= Number(qcm.dataset.seuil || total)
    resultat.className = `qcm-res ${reussi ? 'ok' : 'ko'}`
    if (qcm.dataset.role === 'entree') {
      resultat.textContent = reussi
        ? `${bonnes} sur ${total} : tu maîtrises déjà l'essentiel. Va directement au temps 4, ou passe au nœud suivant.`
        : `${bonnes} sur ${total} : ce nœud est fait pour toi. Commence par le temps 1.`
    } else {
      resultat.textContent = reussi
        ? `${bonnes} sur ${total} : test réussi. Tu peux valider l'étape en bas de la page.`
        : `${bonnes} sur ${total} : reprends les explications ci-dessus, puis réessaie.`
    }
    rendre(qcm)
  })
}

/** QCM à boutons de Réseau & Sécurité : un clic sur une réponse la corrige aussitôt. */
function qcmABoutons(racine: HTMLElement): void {
  const qcms = Array.from(racine.querySelectorAll<HTMLElement>('.qcm[data-answer]'))
  if (!qcms.length) return
  const score = document.createElement('p')
  score.className = 'qcm-score'
  score.setAttribute('role', 'status')
  qcms[qcms.length - 1].after(score)
  let repondues = 0
  let justes = 0
  for (const qcm of qcms) {
    const bonne = Number(qcm.dataset.answer)
    const options = Array.from(qcm.querySelectorAll<HTMLButtonElement>('button.opt'))
    const explication = qcm.querySelector<HTMLElement>('.qcm-exp')
    options.forEach((option, k) => {
      option.addEventListener('click', () => {
        if (qcm.dataset.fait) return
        qcm.dataset.fait = '1'
        repondues++
        const ok = k === bonne
        if (ok) justes++
        options.forEach((x, i) => {
          x.disabled = true
          if (i === bonne) x.classList.add('good')
          else if (i === k) x.classList.add('bad')
        })
        if (explication) {
          const verdict = document.createElement('b')
          verdict.textContent = ok ? 'Juste. ' : 'Non. '
          explication.prepend(verdict)
          explication.classList.add('on')
        }
        if (repondues === qcms.length) {
          const n = qcms.length
          score.textContent = `${justes} / ${n} — ${
            justes === n ? 'Parfait. Passe au TP.' : justes >= n - 1 ? 'Bon. Relis le point manqué.' : "Reprends le mécanisme avant d'aller plus loin."
          }`
          score.classList.add('on')
        }
      })
    })
  }
}

/** Les onglets « Comprendre / Démontrer / Implémenter / S'exercer » d'un nœud. */
function onglets(racine: HTMLElement, rendre: Rendre): void {
  racine.querySelectorAll<HTMLElement>('.temps').forEach((bloc) => {
    const tous = Array.from(bloc.querySelectorAll<HTMLElement>('.onglet[data-t]'))
    if (!tous.length) return
    const ouvrir = (t: number, defiler: boolean) => {
      tous.forEach((o) => {
        const actif = Number(o.dataset.t) === t
        o.setAttribute('aria-selected', String(actif))
        if (actif) o.classList.add('vu')
      })
      bloc.querySelectorAll<HTMLElement>('.panneau[data-t]').forEach((p) => { p.hidden = Number(p.dataset.t) !== t })
      rendre(bloc)
      if (defiler) bloc.scrollIntoView({ block: 'start', behavior: 'smooth' })
    }
    tous.forEach((o) => o.addEventListener('click', () => ouvrir(Number(o.dataset.t), false)))
    bloc.querySelectorAll<HTMLElement>('.aller[data-t]').forEach((b) => b.addEventListener('click', () => ouvrir(Number(b.dataset.t), true)))
    const actif = tous.find((o) => o.getAttribute('aria-selected') === 'true') ?? tous[0]
    ouvrir(Number(actif.dataset.t), false)
  })
}

export function monterAutocorrections(racine: HTMLElement, rendre: Rendre): void {
  racine.querySelectorAll<HTMLElement>('.qcm').forEach((qcm, i) => {
    if (qcm.querySelector('.qcm-q[data-bonne]')) qcmAvecBouton(qcm, i, rendre)
  })
  qcmABoutons(racine)
  onglets(racine, rendre)
}
