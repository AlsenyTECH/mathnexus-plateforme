import { describe, expect, it } from 'vitest'
import { monterAutocorrections } from './autocorrection'

const rien = () => {}

function page(html: string): HTMLElement {
  const racine = document.createElement('div')
  racine.innerHTML = html
  document.body.append(racine)
  return racine
}

describe('auto-vérifications des pages cahier', () => {
  it("corrige un test d'entrée et donne le verdict", () => {
    const r = page(`<div class="qcm" data-role="entree" data-seuil="1">
      <fieldset class="qcm-q" data-bonne="1">
        <label class="qcm-o"><input type="radio" name="q0" value="0"> a</label>
        <label class="qcm-o"><input type="radio" name="q0" value="1"> b</label>
        <p class="qcm-x" hidden>Parce que b.</p></fieldset>
      <div class="qcm-bas"><button type="button">Corriger</button><p class="qcm-res" hidden></p></div></div>`)
    monterAutocorrections(r, rien)
    r.querySelector<HTMLButtonElement>('button')!.click()
    expect(r.querySelector('.qcm-res')!.textContent).toBe('Réponds à toutes les questions.')
    r.querySelectorAll<HTMLInputElement>('input')[1].checked = true
    r.querySelector<HTMLButtonElement>('button')!.click()
    expect(r.querySelector('.qcm-res')!.textContent).toMatch(/^1 sur 1 : tu maîtrises/)
    expect(r.querySelector<HTMLElement>('.qcm-x')!.hidden).toBe(false)
    expect(r.querySelectorAll('.qcm-o')[1].classList.contains('juste')).toBe(true)
  })

  it('corrige un QCM à boutons au clic et compte le score', () => {
    const r = page(`<div class="qcm" data-answer="1"><button class="opt">A</button><button class="opt">B</button>
      <div class="qcm-exp">Explication</div></div>`)
    monterAutocorrections(r, rien)
    const options = r.querySelectorAll<HTMLButtonElement>('button.opt')
    options[0].click()
    expect(options[0].classList.contains('bad') && options[1].classList.contains('good')).toBe(true)
    expect(r.querySelector('.qcm-exp')!.textContent).toMatch(/^Non\./)
    expect(r.querySelector('.qcm-score')!.textContent).toMatch(/^0 \/ 1/)
  })

  it("n'affiche qu'un panneau des quatre temps à la fois", () => {
    const r = page(`<div class="temps"><div class="onglets"><button class="onglet" data-t="0" aria-selected="true">1</button>
      <button class="onglet" data-t="1" aria-selected="false">2</button></div>
      <div class="panneau" data-t="0">un</div><div class="panneau" data-t="1">deux</div></div>`)
    monterAutocorrections(r, rien)
    const [p0, p1] = r.querySelectorAll<HTMLElement>('.panneau')
    expect([p0.hidden, p1.hidden]).toEqual([false, true])
    r.querySelectorAll<HTMLButtonElement>('.onglet')[1].click()
    expect([p0.hidden, p1.hidden]).toEqual([true, false])
  })
})
