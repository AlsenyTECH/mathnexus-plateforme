/**
 * Scénario de bout en bout de la V1 (Chrome) : évaluation du jour chronométrée avec sujet en photo,
 * séance du jour, copie avec photo, correction au stylo, commentaires réutilisables, copie suivante,
 * tableau de classe, fiche élève, bilan parent, mot de passe réinitialisé, carnet d'erreurs.
 *
 *   BASE=http://127.0.0.1:5173 GROUPE_DEMO=<id> MDP_DEMO=<mdp> node e2e/v1.mjs
 *
 * Données : initialiser_plateforme + preparer_pilote + preparer_demo ; admin 771000000 ;
 * dans « Prépa ECG1 — Cathy » : Cathy 772223344 (parent renseigné) et Awa 773334455.
 */
import { chromium } from 'playwright-core'
import { mkdirSync, writeFileSync } from 'node:fs'

const BASE = process.env.BASE ?? 'http://127.0.0.1:5173'
const C = process.env.CAPTURES ?? 'e2e/captures'
mkdirSync(C, { recursive: true })
const navigateur = await chromium.launch({ executablePath: process.env.CHROME ?? '/usr/bin/google-chrome', args: ['--no-sandbox'] })
let n = 0
const etape = (t) => console.log(`${++n}. ${t}`)
const attendre = (cond, msg) => { if (!cond) throw new Error('ÉCHEC : ' + msg) }
const erreurs = []

async function connecter(telephone, mdp, largeur = 390) {
  const ctx = await navigateur.newContext({ viewport: { width: largeur, height: 900 }, locale: 'fr-FR' })
  const p = await ctx.newPage()
  p.on('pageerror', (e) => erreurs.push(e.message))
  await p.goto(BASE + '/connexion')
  await p.getByLabel('Numéro de téléphone').fill(telephone)
  await p.getByLabel('Mot de passe').fill(mdp)
  await p.getByRole('button', { name: /Se connecter/ }).click()
  await p.waitForURL((u) => !u.pathname.startsWith('/connexion'))
  return p
}

// Une photo de sujet et une photo de copie, fabriquées par le navigateur
async function image(texte, fichier) {
  const p = await (await navigateur.newContext()).newPage()
  const b64 = await p.evaluate((t) => {
    const c = document.createElement('canvas'); c.width = 900; c.height = 600
    const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, 900, 600)
    g.fillStyle = '#123'; g.font = '40px serif'; g.fillText(t, 40, 300)
    return c.toDataURL('image/jpeg', 0.9).split(',')[1]
  }, texte)
  writeFileSync(fichier, Buffer.from(b64, 'base64'))
  await p.close()
}
await image('Exercice : calculer A² pour A = (1 2 ; 3 4)', `${C}/sujet.jpg`)
await image('Copie : A² = (7 10 ; 15 22)', `${C}/copie.jpg`)

// 1. Le prof donne l'évaluation du jour, chronométrée, sujet en photo
const prof = await connecter('771000000', 'Cahier-quadrille-2026', 1200)
await prof.getByRole('link', { name: 'Espace prof' }).click()
await prof.getByRole('link', { name: /Prépa ECG1/ }).click()
await prof.getByRole('button', { name: /Donner du travail/ }).click()
await prof.getByLabel('Titre', { exact: true }).fill('Évaluation du jour — puissances de matrices')
await prof.locator('textarea[name=consigne]').fill('Calcule \\(A^2\\), puis \\(A^3\\).')
await prof.locator('input[name=duree_min]').fill('15')
await prof.locator('input[type=file][accept*=pdf]').setInputFiles(`${C}/sujet.jpg`)
await prof.getByRole('button', { name: 'Donner ce travail' }).click()
await prof.getByText('Évaluation du jour — puissances de matrices').waitFor()
const wa = await prof.locator('a.whatsapp').first().getAttribute('href')
attendre(wa.startsWith('https://wa.me/?text=') && decodeURIComponent(wa).includes('15 min'), 'lien WhatsApp du devoir')
etape('Évaluation chronométrée donnée, avec sujet en photo et lien WhatsApp')

// 2. Cathy : séance du jour, commencer, chronomètre, copie avec photo
const cathy = await connecter('772223344', 'Cathy-Prepa-2026')
await cathy.locator('.seance').getByText('puissances de matrices').waitFor()
await cathy.screenshot({ path: `${C}/v1-1-seance.png`, fullPage: true })
await cathy.locator('.seance').getByText('puissances de matrices').click()
await cathy.getByRole('button', { name: 'Commencer' }).waitFor()
attendre(await cathy.locator('.pieces').count() === 0, 'le sujet est caché avant de commencer')
await cathy.getByRole('button', { name: 'Commencer' }).click()
await cathy.locator('.chronometre').waitFor()
await cathy.locator('.pieces img').waitFor()
attendre(await cathy.locator('.texte-libre .katex').count() > 0, 'formules du sujet rendues')
await cathy.screenshot({ path: `${C}/v1-2-chrono.png`, fullPage: true })
await cathy.getByPlaceholder(/Écris ta réponse/).fill('A² = (7 10 ; 15 22)')
await cathy.locator('.ajout-photos input[type=file]').setInputFiles(`${C}/copie.jpg`)
await cathy.locator('.galerie img').first().waitFor()
await cathy.getByRole('button', { name: 'Envoyer à mon prof' }).click()
await cathy.getByText('Ta copie est envoyée').waitFor()
etape('Cathy : séance du jour → commencer → chronomètre → sujet → copie envoyée')

// 3. Awa rend aussi (pour « copie suivante »)
const awa = await connecter('773334455', 'Awa-Prepa-2026')
await awa.locator('.seance').getByText('puissances de matrices').click()
await awa.getByRole('button', { name: 'Commencer' }).click()
await awa.getByPlaceholder(/Écris ta réponse/).fill('Je trouve (7 10 ; 15 22).')
await awa.getByRole('button', { name: 'Envoyer à mon prof' }).click()
await awa.getByText('Ta copie est envoyée').waitFor()
etape('Awa : copie envoyée')

// 4. Le prof corrige Cathy : stylo sur la photo, commentaire, rendre, copie suivante
await prof.getByRole('link', { name: 'Espace prof' }).click()
await prof.getByText(/À corriger \(2\)/).waitFor()
await prof.getByRole('link', { name: /Cathy Monteiro — Évaluation du jour/ }).click()
await prof.getByRole('button', { name: 'Annoter au stylo' }).click()
const toile = prof.locator('.annotation-toile')
await prof.waitForFunction(() => document.querySelector('.annotation-toile')?.width > 300)
const b = await toile.boundingBox()
await prof.mouse.move(b.x + b.width * 0.2, b.y + b.height * 0.6)
await prof.mouse.down()
for (let i = 1; i <= 10; i++) await prof.mouse.move(b.x + b.width * (0.2 + i * 0.05), b.y + b.height * (0.6 + (i % 2) * 0.03))
await prof.mouse.up()
await prof.screenshot({ path: `${C}/v1-3-annotation.png` })
await prof.getByRole('button', { name: 'Ajouter à la correction' }).click()
await prof.locator('.annotation').waitFor({ state: 'detached' })
await prof.locator('.formulaire-correction .galerie img').first().waitFor()
await prof.getByLabel(/Note sur/).fill('17')
await prof.getByLabel("Mot pour l'élève").fill('Très bien, attention aux signes.')
await prof.getByRole('button', { name: "Rendre la copie à l'élève" }).click()
await prof.getByText('Copie rendue').waitFor()
await prof.screenshot({ path: `${C}/v1-4-correction.png`, fullPage: true })
await prof.locator('.succes').getByRole('link', { name: /Copie suivante : Awa/ }).click()
await prof.locator('.puce', { hasText: 'Très bien, attention aux signes.' }).click()
attendre((await prof.getByLabel("Mot pour l'élève").inputValue()).includes('attention aux signes'), 'commentaire réutilisé')
await prof.getByLabel(/Note sur/).fill('12')
await prof.getByRole('button', { name: "Rendre la copie à l'élève" }).click()
await prof.getByText('Copie rendue').waitFor()
etape('Correction : stylo sur la photo, note, commentaire, copie suivante, commentaire réutilisé')

// 5. Tableau de classe, fiche élève, bilan parent, mot de passe
await prof.getByRole('link', { name: '← Évaluation du jour — puissances de matrices' }).click()
await prof.getByRole('link', { name: '← La classe' }).click()
await prof.locator('.tableau-suivi').getByRole('link', { name: 'Cathy Monteiro' }).waitFor()
const ligne = await prof.locator('.tableau-suivi tr', { hasText: 'Cathy' }).innerText()
attendre(ligne.includes('17,0/20'), 'moyenne de Cathy dans le tableau : ' + ligne)
await prof.screenshot({ path: `${C}/v1-5-tableau.png`, fullPage: true })
await prof.locator('.tableau-suivi').getByRole('link', { name: 'Cathy Monteiro' }).click()
await prof.locator('.bilan textarea').waitFor()
await prof.waitForFunction(() => document.querySelector('.bilan textarea')?.value.includes('17/20'))
const parent = await prof.getByRole('link', { name: 'Envoyer au parent sur WhatsApp' }).getAttribute('href')
attendre(parent.startsWith('https://wa.me/221776665544?text='), 'WhatsApp du parent')
await prof.screenshot({ path: `${C}/v1-6-fiche.png`, fullPage: true })
prof.once('dialog', (d) => d.accept())
await prof.getByRole('button', { name: /nouveau mot de passe provisoire/ }).click()
const mdp = await prof.locator('.mdp').innerText()
etape('Tableau de classe, fiche élève, bilan parent prêt pour WhatsApp, mot de passe provisoire : ' + mdp)

// Cathy se reconnecte avec le mot de passe provisoire : on lui demande d'en choisir un
const cathy2 = await connecter('772223344', mdp)
attendre(cathy2.url().includes('mot-de-passe'), 'changement de mot de passe demandé : ' + cathy2.url())
etape('Cathy se connecte avec le mot de passe provisoire → changement demandé')

// 6. Carnet d'erreurs : l'élève de démo rate le QCM, puis le révise
const demo = await connecter('770000001', process.env.MDP_DEMO)
const G = process.env.GROUPE_DEMO
await demo.evaluate(async (g) => {
  const csrf = () => document.cookie.split('; ').find((c) => c.startsWith('csrftoken='))?.split('=')[1]
  const appel = (url, corps, methode = 'POST') => fetch(url, { method: methode, headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() }, body: JSON.stringify(corps ?? {}) }).then((r) => r.json())
  const t = await appel(`/api/groupes/${g}/parcours/demo-evaluations/evaluations/demo-qcm-sortie/tentatives/`)
  for (const q of t.questions) await appel(`/api/tentatives/${t.id}/reponses/${q.cle}/`, { choix: [q.choix.length - 1], temps_ms: 800 }, 'PUT')
  await appel(`/api/tentatives/${t.id}/terminer/`, { temps: {} })
}, G)
await demo.goto(`${BASE}/classe/${G}`)
await demo.locator('.seance').getByText(/de ton carnet d'erreurs/).click()
await demo.locator('.carnet-question').waitFor()
await demo.locator('.choix-carnet .choix').first().click()
await demo.getByRole('button', { name: 'Vérifier' }).click()
await demo.locator('.verdict').waitFor()
await demo.screenshot({ path: `${C}/v1-7-carnet.png`, fullPage: true })
etape('Carnet d\'erreurs : question ratée retrouvée dans la séance, révisée, corrigée')

attendre(erreurs.length === 0, 'erreurs JavaScript : ' + erreurs.join(' | '))
await navigateur.close()
console.log('Scénario V1 : tout est passé.')
