import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ErreurApi } from '../api/client'
import type { Sommaire } from '../api/types'
import { nettoyer } from '../lecteur/nettoyage'
import { avisSurNote, monterEvaluations } from '../lecteur/evaluation'
import { figuresConnues, monterFigures } from '../lecteur/figures'
import { etapeAReprendre, lireListe } from '../utilitaires'
import { routePour } from '../session'

function reponse(statut: number, corps?: unknown) {
  return new Response(corps === undefined ? null : JSON.stringify(corps), { status: statut })
}

describe('client API', () => {
  beforeEach(() => {
    document.cookie = 'csrftoken=jeton-de-test'
  })
  afterEach(() => vi.restoreAllMocks())

  it('envoie le jeton CSRF sur les requêtes qui modifient', async () => {
    const f = vi.spyOn(globalThis, 'fetch').mockResolvedValue(reponse(200, { ok: true }))
    await api.post('auth/connexion/', { telephone: '771234567' })
    const [url, options] = f.mock.calls[0]
    expect(url).toBe('/api/auth/connexion/')
    expect((options!.headers as Record<string, string>)['X-CSRFToken']).toBe('jeton-de-test')
    expect(options!.credentials).toBe('same-origin')
  })

  it("n'envoie pas de jeton sur une lecture", async () => {
    const f = vi.spyOn(globalThis, 'fetch').mockResolvedValue(reponse(200, []))
    await api.get('groupes/')
    expect((f.mock.calls[0][1]?.headers as Record<string, string>)['X-CSRFToken']).toBeUndefined()
  })

  it('transforme les erreurs DRF en messages lisibles', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(reponse(400, { telephone: ['Numéro de téléphone invalide.'] }))
    const e = await api.post<never>('auth/inscription/', {}).catch((x: ErreurApi) => x)
    expect(e).toBeInstanceOf(ErreurApi)
    expect(e.champs()).toEqual({ telephone: 'Numéro de téléphone invalide.' })
  })

  it('explique la limitation des tentatives', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(reponse(429, {}))
    const e = await api.post<never>('auth/connexion/', {}).catch((x: ErreurApi) => x)
    expect(e.message).toMatch(/Trop de tentatives/)
  })

  it('accepte une réponse vide (204)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }))
    await expect(api.post('auth/deconnexion/')).resolves.toBeUndefined()
  })
})

describe('redirection', () => {
  it('traduit chaque destination de l’API en adresse', () => {
    expect(routePour({ type: 'groupe', groupe: 'abc' })).toBe('/classe/abc')
    expect(routePour({ type: 'attente' })).toBe('/attente')
    expect(routePour({ type: 'admin' })).toBe('/admin')
    expect(routePour({ type: 'prof' })).toBe('/prof')
    expect(routePour({ type: 'choix_groupe', groupes: ['a', 'b'] })).toBe('/choisir')
    expect(routePour({ type: 'changer_mot_de_passe' })).toBe('/mot-de-passe')
    expect(routePour({ type: 'aucun_groupe' })).toBe('/aucune-classe')
  })

  it('reprend à la première étape accessible non validée', () => {
    const e = (cle: string, accessible: boolean, validee: boolean) =>
      ({ cle, titre: cle, duree_min: null, acces: 'inscrit', ouverte: true, accessible, raison: null, validee, ouverte_eleves: true }) as const
    const s = { parties: [{ cle: 'p', titre: 'P', etapes: [e('a', true, true), e('b', false, false), e('c', true, false)] }] } as unknown as Sommaire
    expect(etapeAReprendre(s)).toBe('c')
  })
})

describe('nettoyage du contenu (défense en profondeur)', () => {
  it('retire scripts et gestionnaires, garde les composants', () => {
    const propre = nettoyer(
      '<p onclick="vol()">Cours</p><script>vol()</script><img src=x onerror="vol()">' +
        '<div class="graph" data-fig="plan" data-alt="Plan"></div><div class="ev-sujet" hidden>Sujet</div>' +
        '<a href="javascript:vol()">lien</a><form><input></form>',
    )
    expect(propre).not.toMatch(/onclick|onerror|<script|javascript:|<form|<input/)
    expect(propre).toContain('data-fig="plan"')
    expect(propre).toContain('hidden')
  })
})

describe('graphiques', () => {
  it('connaît les figures des deux parcours', () => {
    expect(figuresConnues()).toEqual(expect.arrayContaining(['plan', 'second-degre', 'asymptote', 'branche']))
  })

  it('échappe data-alt (correctif de sécurité)', () => {
    const racine = document.createElement('div')
    racine.innerHTML = nettoyer('<div class="graph" data-fig="plan" data-alt="x&quot; onmouseover=&quot;vol()"></div>')
    const demonter = monterFigures(racine)
    const canevas = racine.querySelector('canvas')!
    expect(canevas.getAttribute('onmouseover')).toBeNull()
    expect(canevas.getAttribute('aria-label')).toBe('x" onmouseover="vol()')
    demonter()
  })

  it('signale une figure inconnue au lieu de planter', () => {
    const racine = document.createElement('div')
    racine.innerHTML = '<div class="graph" data-fig="inconnue"></div>'
    monterFigures(racine)()
    expect(racine.textContent).toMatch(/pas encore disponible/)
  })
})

describe('évaluations', () => {
  const EVAL = `
  <div class="eval" data-min="45" data-id="p1">
    <div class="ev-intro"><span role="button" data-composant="bouton" class="btn ev-go">Commencer l'évaluation</span>
      <p class="ev-best" hidden></p></div>
    <div class="ev-bar" hidden><p class="ev-t">45:00</p>
      <span role="button" data-composant="bouton" class="btn ghost ev-pause">Pause</span>
      <span role="button" data-composant="bouton" class="btn ev-end">J'ai terminé</span></div>
    <div class="ev-sujet" hidden>Sujet</div>
    <div class="ev-cor" hidden>
      <span data-composant="case" data-p="1.5"></span><span data-composant="case" data-p="1"></span>
      <div class="ev-score"><p class="ev-note">Ta note : <strong>0</strong> / 20</p><p class="ev-avis"></p>
      <span role="button" data-composant="bouton" class="btn ghost ev-again">Recommencer</span></div>
    </div>
  </div>`

  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
  })
  afterEach(() => vi.useRealTimers())

  it('déroule une évaluation : sujet, chronomètre, corrigé, note', () => {
    const racine = document.createElement('div')
    document.body.append(racine)
    racine.innerHTML = nettoyer(EVAL)
    const rendre = vi.fn()
    const demonter = monterEvaluations(racine, 'note:eleve1:nombres-complexes', rendre)
    const go = racine.querySelector<HTMLButtonElement>('button.ev-go')!
    expect(go).not.toBeNull()
    go.click()
    expect(racine.querySelector<HTMLElement>('.ev-sujet')!.hidden).toBe(false)
    vi.advanceTimersByTime(3000)
    expect(racine.querySelector('.ev-t')!.textContent).toBe('44:57')
    racine.querySelector<HTMLButtonElement>('button.ev-end')!.click()
    expect(racine.querySelector<HTMLElement>('.ev-cor')!.hidden).toBe(false)
    const cases = racine.querySelectorAll<HTMLInputElement>('input[type=checkbox]')
    expect(cases).toHaveLength(2)
    cases[0].click()
    cases[1].click()
    expect(racine.querySelector('.ev-note strong')!.textContent).toBe('2,5')
    expect(localStorage.getItem('note:eleve1:nombres-complexes:p1')).toBe('2.5')
    expect(rendre).toHaveBeenCalled()
    demonter()
    racine.remove()
  })

  it('donne un avis selon la note', () => {
    expect(avisSurNote(17)).toMatch(/acquise/)
    expect(avisSurNote(5)).toMatch(/depuis le début/)
  })
})

describe('import de liste', () => {
  it('lit une liste collée depuis un tableur', () => {
    expect(lireListe('Fatou ; Ba ; 77 300 00 01\nIbou\tFall\t77 300 00 02\n\nligne incomplète')).toEqual([
      { prenom: 'Fatou', nom: 'Ba', telephone: '77 300 00 01' },
      { prenom: 'Ibou', nom: 'Fall', telephone: '77 300 00 02' },
    ])
  })
})
