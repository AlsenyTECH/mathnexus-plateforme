/**
 * Les évaluations chronométrées des parcours, reprises du moteur d'origine.
 *
 * Dans un paquet, les boutons et cases à cocher sont des éléments neutres
 * (data-composant="bouton" / "case") : c'est ici que l'application en fait de vrais contrôles,
 * puis branche le chronomètre, l'affichage du sujet, le corrigé et le calcul de la note.
 *
 * Phase 2 : la tentative et la note seront enregistrées sur le serveur. En attendant, la
 * meilleure note reste sur l'appareil.
 */

function transformerControles(racine: HTMLElement): void {
  racine.querySelectorAll<HTMLElement>('[data-composant="bouton"]').forEach((span) => {
    const bouton = document.createElement('button')
    bouton.type = 'button'
    bouton.className = span.className
    bouton.textContent = span.textContent
    span.replaceWith(bouton)
  })
  racine.querySelectorAll<HTMLElement>('[data-composant="case"]').forEach((span) => {
    const caseACocher = document.createElement('input')
    caseACocher.type = 'checkbox'
    caseACocher.dataset.p = span.dataset.p ?? '0'
    span.replaceWith(caseACocher)
  })
}

export function avisSurNote(note: number): string {
  if (note >= 16) return 'Très bien : la partie est acquise, passe à la suite.'
  if (note >= 12) return 'Bien. Reprends les étapes où tu as perdu des points avant de continuer.'
  if (note >= 8)
    return "Pas encore suffisant. Refais les exercices des étapes concernées, puis recommence l'évaluation dans quelques jours."
  return "Reprends la partie depuis le début avant de recommencer l'évaluation."
}

export function formaterNote(n: number): string {
  return String(n).replace('.', ',')
}

/** Monte les évaluations d'une étape. `prefixe` distingue les notes par compte et par parcours. */
export function monterEvaluations(racine: HTMLElement, prefixe: string, rendre: (el: HTMLElement) => void): () => void {
  transformerControles(racine)
  const minuteurs: number[] = []
  racine.querySelectorAll<HTMLElement>('.eval').forEach((ev) => {
    const total = (Number(ev.dataset.min) || 30) * 60
    const cle = `${prefixe}:${ev.dataset.id ?? 'eval'}`
    const q = <T extends Element>(s: string) => ev.querySelector<T & HTMLElement>(s)
    const go = q<HTMLButtonElement>('.ev-go')
    const barre = q('.ev-bar')
    const temps = q('.ev-t')
    const pause = q<HTMLButtonElement>('.ev-pause')
    const fin = q<HTMLButtonElement>('.ev-end')
    const sujet = q('.ev-sujet')
    const corrige = q('.ev-cor')
    const meilleure = q('.ev-best')
    if (!go || !barre || !temps || !pause || !fin || !sujet || !corrige) return
    const cases = Array.from(corrige.querySelectorAll<HTMLInputElement>('input[type=checkbox]'))
    const note = corrige.querySelector('.ev-note strong')
    const avis = corrige.querySelector('.ev-avis')
    let reste = total
    let minuteur: number | null = null

    const afficherMeilleure = () => {
      let b: string | null = null
      try {
        b = localStorage.getItem(cle)
      } catch {
        /* stockage indisponible */
      }
      if (b !== null && meilleure) {
        meilleure.hidden = false
        meilleure.textContent = `Ta meilleure note à cette évaluation : ${formaterNote(Number(b))} / 20`
      }
    }
    const dessiner = () => {
      const m = Math.floor(reste / 60)
      const s = reste % 60
      temps.textContent = `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`
      temps.classList.toggle('low', reste <= 300)
    }
    const arreter = () => {
      if (minuteur !== null) window.clearInterval(minuteur)
      minuteur = null
    }
    const terminer = (tempsEcoule: boolean) => {
      arreter()
      barre.hidden = true
      corrige.hidden = false
      rendre(corrige)
      if (avis) avis.textContent = tempsEcoule ? 'Temps écoulé. Pose ton stylo et corrige ta copie.' : ''
      corrige.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
    }
    const lancer = () => {
      minuteur = window.setInterval(() => {
        reste--
        dessiner()
        if (reste <= 0) {
          reste = 0
          terminer(true)
        }
      }, 1000)
      minuteurs.push(minuteur)
      pause.textContent = 'Pause'
    }
    const noter = () => {
      let s = cases.reduce((acc, c) => acc + (c.checked ? parseFloat(c.dataset.p ?? '0') : 0), 0)
      s = Math.round(s * 4) / 4
      if (note) note.textContent = formaterNote(s)
      if (avis) avis.textContent = avisSurNote(s)
      try {
        const b = parseFloat(localStorage.getItem(cle) ?? '')
        if (isNaN(b) || s > b) localStorage.setItem(cle, String(s))
      } catch {
        /* stockage indisponible */
      }
    }
    cases.forEach((c) => c.addEventListener('change', noter))
    go.addEventListener('click', () => {
      reste = total
      dessiner()
      go.textContent = 'Évaluation en cours'
      go.disabled = true
      barre.hidden = false
      sujet.hidden = false
      rendre(sujet)
      lancer()
      barre.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
    })
    pause.addEventListener('click', () => {
      if (minuteur !== null) {
        arreter()
        pause.textContent = 'Reprendre'
      } else lancer()
    })
    fin.addEventListener('click', () => terminer(false))
    corrige.querySelector('.ev-again')?.addEventListener('click', () => {
      cases.forEach((c) => (c.checked = false))
      if (note) note.textContent = '0'
      if (avis) avis.textContent = ''
      corrige.hidden = true
      sujet.hidden = true
      barre.hidden = true
      go.disabled = false
      go.textContent = "Commencer l'évaluation"
      afficherMeilleure()
    })
    afficherMeilleure()
  })
  return () => minuteurs.forEach((m) => window.clearInterval(m))
}
