import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { monterComposants } from '../lecteur/composants'
import { nettoyer } from '../lecteur/nettoyage'
import { monter, type EtatTentative, type Services } from '../partages/evaluation.js'

/**
 * Le composant évaluation, testé avec un faux serveur (des fonctions espionnées par vi.fn)
 * et une horloge que le test fait avancer à la main : on peut ainsi vérifier le temps mesuré
 * à la milliseconde près.
 */

const PRESENTATION = {
  cle: 'demo-qcm-sortie', titre: 'Test de sortie', role: 'sortie', consigne: '<p>Réponds à tout.</p>',
  duree_min: null, seuil: 2, total: 3, nombre_questions: 3,
}

const QUESTIONS: EtatTentative['questions'] = [
  { cle: 'module', type: 'choix_unique', enonce: '<p>Module de 3 + 4i ?</p>', choix: ['5', '7', '25'], points: 1 },
  { cle: 'conjugue', type: 'choix_unique', enonce: '<p>Conjugué de 2 − 5i ?</p>', choix: ['2 + 5i', '−2 + 5i'], points: 1 },
  { cle: 'reels', type: 'choix_multiple', enonce: '<p>Lesquels sont réels ?</p>', choix: ['i²', 'i³', '(1+i)(1−i)'], points: 1 },
]

function etat(autres: Partial<EtatTentative> = {}): EtatTentative {
  return {
    id: 't1', commencee_le: '2026-11-27T10:00:00Z', terminee_le: null, fin: null, score: null, total: 3,
    reussie: null, evaluation: PRESENTATION, secondes_restantes: null, terminee: false, questions: QUESTIONS,
    reponses: {}, ...autres,
  }
}

const CORRIGEE = etat({
  terminee: true, terminee_le: '2026-11-27T10:05:00Z', fin: 'terminee', score: 2, reussie: true,
  reponses: { module: { choix: [0], temps_ms: 4000 }, conjugue: { choix: [1], temps_ms: 3000 }, reels: { choix: [0, 2], temps_ms: 9000 } },
  correction: [
    { cle: 'module', bonnes: [0], explication: '<p>Racine de 25.</p>', juste: true, points_obtenus: 1 },
    { cle: 'conjugue', bonnes: [0], explication: '', juste: false, points_obtenus: 0 },
    { cle: 'reels', bonnes: [0, 2], explication: '', juste: true, points_obtenus: 1 },
  ],
})

let maintenant = 0
let element: HTMLElement
let demonter: () => void

function fauxServeur(autres: Partial<Services> = {}) {
  return {
    charger: vi.fn().mockResolvedValue({ ...PRESENTATION, en_cours: null, tentatives: [] }),
    commencer: vi.fn().mockResolvedValue(etat()),
    reprendre: vi.fn().mockResolvedValue(etat()),
    repondre: vi.fn().mockResolvedValue({ temps_ms: 0, secondes_restantes: null }),
    terminer: vi.fn().mockResolvedValue(CORRIGEE),
    nettoyer,
    rendre: vi.fn(),
    estClose: (e: unknown) => e === 'close',
    horloge: () => maintenant,
    ...autres,
  } satisfies Services
}

const attendre = () => new Promise((r) => setTimeout(r, 0))

function boutonNomme(texte: string | RegExp): HTMLButtonElement {
  const b = Array.from(element.querySelectorAll('button')).find((x) =>
    typeof texte === 'string' ? x.textContent === texte : texte.test(x.textContent ?? ''))
  if (!b) throw new Error(`Bouton « ${texte} » introuvable dans : ${element.textContent}`)
  return b
}

const options = () => Array.from(element.querySelectorAll<HTMLButtonElement>('.evd-option'))

async function lancer(services: Services) {
  demonter = monter(element, { cle: 'demo-qcm-sortie' }, services)
  await attendre()
}

async function commencer(services: Services) {
  await lancer(services)
  boutonNomme('Commencer').click()
  await attendre()
}

function rendreVisible(visible: boolean) {
  Object.defineProperty(document, 'visibilityState', { value: visible ? 'visible' : 'hidden', configurable: true })
  document.dispatchEvent(new Event('visibilitychange'))
}

beforeEach(() => {
  maintenant = 0
  element = document.createElement('div')
  document.body.append(element)
  rendreVisible(true)
})

afterEach(() => {
  demonter?.()
  element.remove()
  vi.useRealTimers()
})

describe('évaluation : accueil', () => {
  it('présente sans montrer de question', async () => {
    await lancer(fauxServeur())
    expect(element.textContent).toContain('Test de sortie')
    expect(element.textContent).toContain('3 questions · 3 points · réussi à partir de 2 · sans limite de temps')
    expect(element.textContent).not.toContain('Module de 3 + 4i')
    expect(boutonNomme('Commencer')).toBeTruthy()
  })

  it('propose de reprendre une tentative en cours et retrouve ses réponses', async () => {
    const s = fauxServeur({
      charger: vi.fn().mockResolvedValue({ ...PRESENTATION, en_cours: 't1', tentatives: [] }),
      reprendre: vi.fn().mockResolvedValue(etat({ reponses: { module: { choix: [0], temps_ms: 5000 } } })),
    })
    await lancer(s)
    boutonNomme('Reprendre').click()
    await attendre()
    expect(s.reprendre).toHaveBeenCalledWith('t1')
    expect(element.textContent).toContain('Question 2 / 3') // première question sans réponse
    element.querySelector<HTMLButtonElement>('.evd-pastille')!.click()
    expect(options()[0].getAttribute('aria-checked')).toBe('true')
  })

  it("affiche l'erreur si l'évaluation ne se charge pas", async () => {
    await lancer(fauxServeur({ charger: vi.fn().mockRejectedValue(new Error('Page introuvable.')) }))
    expect(element.textContent).toContain('Évaluation indisponible : Page introuvable.')
  })
})

describe('évaluation : réponses et temps par question', () => {
  it('envoie chaque choix avec le temps passé sur la question', async () => {
    const s = fauxServeur()
    await commencer(s)
    expect(element.textContent).toContain('Question 1 / 3')
    maintenant = 4000
    options()[1].click()
    await attendre()
    expect(s.repondre).toHaveBeenLastCalledWith('t1', 'module', [1], 4000)
    expect(options()[1].getAttribute('aria-checked')).toBe('true')
    maintenant = 5500 // changer d'avis : le temps continue de s'ajouter
    options()[0].click()
    await attendre()
    expect(s.repondre).toHaveBeenLastCalledWith('t1', 'module', [0], 5500)
  })

  it("ne compte pas le temps où l'onglet est caché", async () => {
    const s = fauxServeur()
    await commencer(s)
    maintenant = 1000
    rendreVisible(false)
    maintenant = 61_000 // une minute ailleurs
    rendreVisible(true)
    maintenant = 63_000
    options()[0].click()
    await attendre()
    expect(s.repondre).toHaveBeenLastCalledWith('t1', 'module', [0], 3000)
  })

  it("enregistre le temps d'une question qu'on quitte sans répondre", async () => {
    const s = fauxServeur()
    await commencer(s)
    maintenant = 2500
    boutonNomme('Question suivante →').click()
    await attendre()
    expect(s.repondre).toHaveBeenLastCalledWith('t1', 'module', null, 2500)
    expect(element.textContent).toContain('Question 2 / 3')
  })

  it('choix multiple : chaque clic ajoute ou retire un choix', async () => {
    const s = fauxServeur()
    await commencer(s)
    element.querySelectorAll<HTMLButtonElement>('.evd-pastille')[2].click()
    await attendre()
    expect(element.textContent).toContain('Plusieurs réponses possibles')
    options()[0].click()
    options()[2].click()
    await attendre()
    expect(s.repondre).toHaveBeenLastCalledWith('t1', 'reels', [0, 2], 0)
    options()[0].click()
    await attendre()
    expect(s.repondre).toHaveBeenLastCalledWith('t1', 'reels', [2], 0)
  })

  it('le HTML reçu est nettoyé avant affichage', async () => {
    const piege = [{ ...QUESTIONS[0], enonce: '<p>Q</p><img src="x" onerror="alert(1)">' }, ...QUESTIONS.slice(1)]
    await commencer(fauxServeur({ commencer: vi.fn().mockResolvedValue(etat({ questions: piege })) }))
    expect(element.querySelector('img')).not.toBeNull()
    expect(element.querySelector('[onerror]')).toBeNull()
  })

  it("signale une réponse non enregistrée sans perdre le choix", async () => {
    const s = fauxServeur({ repondre: vi.fn().mockRejectedValue(new Error('réseau')) })
    await commencer(s)
    options()[0].click()
    await attendre()
    expect(element.textContent).toContain('Réponse non enregistrée')
    expect(options()[0].getAttribute('aria-checked')).toBe('true')
  })
})

describe('évaluation : fin et correction', () => {
  it('demande confirmation si des questions restent sans réponse, puis corrige', async () => {
    const s = fauxServeur()
    await commencer(s)
    maintenant = 4000
    options()[0].click()
    await attendre()
    boutonNomme("Terminer l'évaluation").click()
    expect(element.textContent).toContain('2 questions sans réponse. Terminer quand même ?')
    expect(s.terminer).not.toHaveBeenCalled()
    maintenant = 6000
    boutonNomme('Oui, terminer').click()
    await attendre()
    await attendre()
    expect(s.terminer).toHaveBeenCalledWith('t1', { module: 6000, conjugue: 0, reels: 0 })
    expect(element.textContent).toContain('2 / 3')
    expect(element.textContent).toContain('Réussi (il fallait 2 points).')
    expect(element.textContent).toContain('Racine de 25.')
    expect(element.textContent).toContain('Question 2 — faux · 0 / 1')
    expect(element.querySelectorAll('.evd-corr-choix li.bonne').length).toBe(4)
    expect(boutonNomme('Recommencer')).toBeTruthy()
  })

  it("termine tout seul quand le chronomètre arrive à zéro", async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    const s = fauxServeur({ commencer: vi.fn().mockResolvedValue(etat({ secondes_restantes: 3 })) })
    await commencer(s)
    expect(element.querySelector('.evd-temps')?.textContent).toBe('00:03')
    vi.advanceTimersByTime(2000)
    expect(element.querySelector('.evd-temps')?.textContent).toBe('00:01')
    vi.advanceTimersByTime(1000)
    await attendre()
    await attendre()
    expect(s.terminer).toHaveBeenCalled() // sans confirmation
    expect(element.textContent).toContain('2 / 3')
  })

  it('une tentative close ailleurs (409) affiche la correction', async () => {
    const s = fauxServeur({
      repondre: vi.fn().mockRejectedValue('close'),
      reprendre: vi.fn().mockResolvedValue(CORRIGEE),
    })
    await commencer(s)
    options()[0].click()
    await attendre()
    await attendre()
    expect(s.reprendre).toHaveBeenCalledWith('t1')
    expect(element.textContent).toContain('Réussi')
  })

  it('en quittant la page, le dernier temps mesuré est envoyé', async () => {
    const s = fauxServeur()
    await commencer(s)
    maintenant = 7000
    demonter()
    await attendre()
    expect(s.repondre).toHaveBeenLastCalledWith('t1', 'module', null, 7000)
  })
})

describe('registre des composants', () => {
  it("sans contexte (vitrine, aperçu), l'évaluation est seulement annoncée", () => {
    element.innerHTML = '<div data-composant="evaluation" data-cle="x"></div>'
    monterComposants(element, null, () => {})()
    expect(element.textContent).toContain('elle se passe depuis la classe')
  })

  it("avec contexte, l'évaluation est chargée depuis l'API de la classe", async () => {
    const f = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ...PRESENTATION, en_cours: null, tentatives: [] }), { status: 200 }))
    element.innerHTML = '<div data-composant="evaluation" data-cle="demo-qcm-sortie"></div><div data-composant="qcm">statique</div>'
    demonter = monterComposants(element, { groupe: 'g1', slug: 'demo' }, () => {})
    await attendre()
    await attendre()
    expect(f.mock.calls[0][0]).toBe('/api/groupes/g1/parcours/demo/evaluations/demo-qcm-sortie/')
    expect(element.textContent).toContain('Test de sortie')
    expect(element.textContent).toContain('statique') // les composants statiques restent tels quels
    f.mockRestore()
  })
})
