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
  // Fondements MCS
  '\\F': '\\mathbb{F}',
  '\\P': '\\mathbb{P}',
  '\\A': '\\mathbb{A}',
  '\\Ker': '\\operatorname{Ker}',
  '\\Img': '\\operatorname{Im}',
  '\\pgcd': '\\operatorname{pgcd}',
  '\\ppcm': '\\operatorname{ppcm}',
  '\\ord': '\\operatorname{ord}',
  '\\Card': '\\operatorname{Card}',
  '\\rg': '\\operatorname{rg}',
  '\\car': '\\operatorname{car}',
  '\\Tr': '\\operatorname{Tr}',
  '\\Nm': '\\operatorname{N}',
  '\\Gal': '\\operatorname{Gal}',
  '\\Frob': '\\operatorname{Frob}',
  '\\wt': '\\operatorname{wt}',
  '\\dmin': 'd_{\\min}',
  '\\Fq': '\\mathbb{F}_q',
  '\\Fp': '\\mathbb{F}_p',
  '\\Zn': '\\mathbb{Z}/n\\mathbb{Z}',
  '\\Znz': '(\\mathbb{Z}/n\\mathbb{Z})^{\\times}',
  '\\legendre': '\\left(\\frac{#1}{#2}\\right)',
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
