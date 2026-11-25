import 'katex/dist/katex.min.css'
import renderMathInElement from 'katex/contrib/auto-render'

/** Les macros utilisées dans les parcours (reprises des réglages MathJax d'origine). */
export const MACROS: Record<string, string> = {
  '\\R': '\\mathbb{R}',
  '\\N': '\\mathbb{N}',
  '\\C': '\\mathbb{C}',
  '\\Z': '\\mathbb{Z}',
  '\\Q': '\\mathbb{Q}',
  '\\Re': '\\operatorname{Re}',
  '\\Im': '\\operatorname{Im}',
  '\\Vect': '\\operatorname{Vect}',
  '\\vect': '\\overrightarrow{#1}',
  '\\dlim': '\\displaystyle\\lim',
  '\\Cf': '\\mathcal{C}_f',
}

/** Rend en place les formules \( … \) et \[ … \] d'un élément. */
export function rendreFormules(racine: HTMLElement): void {
  renderMathInElement(racine, {
    delimiters: [
      { left: '\\[', right: '\\]', display: true },
      { left: '\\(', right: '\\)', display: false },
    ],
    macros: { ...MACROS },
    throwOnError: false,
    errorColor: 'var(--rouge)',
    ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code', 'option'],
  })
}
