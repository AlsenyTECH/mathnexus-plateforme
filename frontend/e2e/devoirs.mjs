/**
 * Scénario de bout en bout des devoirs, dans Chrome :
 * le prof donne un travail → l'élève écrit sa réponse, ajoute une photo et l'envoie → la copie
 * apparaît « à corriger » → le prof note, commente et rend la copie → l'élève lit sa correction.
 * Puis l'admin passe dans son espace élève (classe M1 MCS) et ouvre un parcours.
 *
 *   BASE=http://127.0.0.1:5173 CHROME=/usr/bin/google-chrome node e2e/devoirs.mjs
 *
 * Il faut l'API avec initialiser_plateforme + preparer_pilote, l'admin 771000000 (mot de passe
 * MDP_ADMIN, déjà changé) et une élève 772223344 (MDP_ELEVE) dans « Prépa ECG1 — Cathy ».
 */
import { chromium } from 'playwright-core'
import { mkdirSync, writeFileSync } from 'node:fs'

const BASE = process.env.BASE ?? 'http://127.0.0.1:5173'
const MDP_ADMIN = process.env.MDP_ADMIN ?? 'Cahier-quadrille-2026'
const MDP_ELEVE = process.env.MDP_ELEVE ?? 'Cathy-Prepa-2026'
const CAPTURES = process.env.CAPTURES ?? 'e2e/captures'
mkdirSync(CAPTURES, { recursive: true })

const navigateur = await chromium.launch({ executablePath: process.env.CHROME ?? '/usr/bin/google-chrome', args: ['--no-sandbox'] })
let n = 0
const etape = (t) => console.log(`${++n}. ${t}`)
const attendre = (cond, msg) => { if (!cond) throw new Error('ÉCHEC : ' + msg) }
const erreurs = []

async function connecter(telephone, mdp, largeur) {
  const contexte = await navigateur.newContext({ viewport: { width: largeur, height: 900 }, locale: 'fr-FR' })
  const p = await contexte.newPage()
  p.on('pageerror', (e) => erreurs.push(e.message))
  await p.goto(BASE + '/connexion')
  await p.getByLabel('Numéro de téléphone').fill(telephone)
  await p.getByLabel('Mot de passe').fill(mdp)
  await p.getByRole('button', { name: /Se connecter/ }).click()
  await p.waitForURL((u) => !u.pathname.startsWith('/connexion'))
  return p
}

// Une petite photo de copie (JPEG) fabriquée par le navigateur lui-même.
const photo = 'e2e/captures/copie.jpg'
{
  const p = await (await navigateur.newContext()).newPage()
  const base64 = await p.evaluate(() => {
    const c = document.createElement('canvas'); c.width = 800; c.height = 600
    const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, 800, 600)
    g.fillStyle = '#1c3bb0'; g.font = '48px serif'; g.fillText('Ma copie : A × B = …', 60, 300)
    return c.toDataURL('image/jpeg', 0.9).split(',')[1]
  })
  writeFileSync(photo, Buffer.from(base64, 'base64'))
}

// 1. Le prof donne un travail à la classe de Cathy
const prof = await connecter('771000000', MDP_ADMIN, 1200)
etape('Admin connecté : ' + new URL(prof.url()).pathname)
await prof.getByRole('link', { name: 'Espace prof' }).click()
await prof.getByRole('link', { name: /Prépa ECG1/ }).click()
await prof.getByRole('button', { name: /Donner du travail/ }).click()
await prof.getByLabel('Titre', { exact: true }).fill('Évaluation du jour — produit de matrices')
await prof.getByLabel('Consigne', { exact: true }).fill('Calcule A × B pour les matrices de l’exercice 3, puis envoie la photo de ta copie.')
await prof.screenshot({ path: `${CAPTURES}/d1-donner-du-travail.png`, fullPage: true })
await prof.getByRole('button', { name: 'Donner ce travail' }).click()
await prof.getByText('Évaluation du jour — produit de matrices').waitFor()
etape('Travail donné à la classe')

// Une étape du parcours donnée en devoir, pour vérifier les listes déroulantes
await prof.getByRole('button', { name: /Donner du travail/ }).click()
await prof.locator('select[name=type]').selectOption('etape')
await prof.locator('select[name=parcours]').selectOption('prepa-algebre-lineaire')
await prof.waitForFunction(() => document.querySelector('select[name=cle_etape] option') !== null)
await prof.getByRole('button', { name: 'Donner ce travail' }).click()
await prof.locator('.ligne-devoir').nth(1).waitFor()
etape('Étape de parcours donnée en devoir')
await prof.screenshot({ path: `${CAPTURES}/d2-classe-prof.png`, fullPage: true })

// 2. L'élève (téléphone) voit ses devoirs, répond et envoie une photo
const eleve = await connecter('772223344', MDP_ELEVE, 390)
await eleve.getByText('Mes devoirs').waitFor()
await eleve.screenshot({ path: `${CAPTURES}/d3-tableau-eleve.png`, fullPage: true })
await eleve.getByRole('link', { name: /produit de matrices/ }).click()
await eleve.getByPlaceholder(/Écris ta réponse/).fill('A × B = (2 1 ; 4 3)')
await eleve.locator('input[type=file]').setInputFiles(photo)
await eleve.locator('.galerie img').first().waitFor()
await eleve.getByRole('button', { name: 'Envoyer à mon prof' }).click()
await eleve.getByText('Ta copie est envoyée').waitFor()
etape('Copie envoyée avec une photo')
await eleve.screenshot({ path: `${CAPTURES}/d4-copie-envoyee.png`, fullPage: true })

// 3. Le prof voit la copie « à corriger », note et rend
await prof.getByRole('link', { name: 'Espace prof' }).click()
await prof.getByText(/À corriger \(1\)/).waitFor()
await prof.screenshot({ path: `${CAPTURES}/d5-a-corriger.png`, fullPage: true })
await prof.getByRole('link', { name: /Cathy Monteiro — Évaluation du jour/ }).click()
await prof.locator('.galerie img').first().waitFor()
await prof.getByLabel(/Note sur/).fill('16.5')
await prof.getByLabel("Mot pour l'élève").fill('Très bien. Attention aux signes sur la deuxième ligne.')
await prof.getByLabel('Correction rédigée').fill('A × B se calcule ligne par colonne…')
await prof.getByRole('button', { name: "Rendre la copie à l'élève" }).click()
await prof.getByText('Copie rendue').waitFor()
etape('Copie corrigée et rendue')
await prof.screenshot({ path: `${CAPTURES}/d6-correction.png`, fullPage: true })

// 4. L'élève lit sa correction
await eleve.reload()
await eleve.getByText('Ta correction').waitFor()
attendre(await eleve.getByText('16.5 / 20').isVisible(), 'la note est affichée')
etape('Correction lue par l’élève')
await eleve.screenshot({ path: `${CAPTURES}/d7-correction-eleve.png`, fullPage: true })

// 5. L'admin dans son espace élève (classe M1 MCS)
await prof.getByRole('link', { name: 'Espace élève' }).click()
await prof.getByText(/Complexité/).first().waitFor()
etape('Espace élève de l’admin : ' + (await prof.locator('.carte-parcours').count()) + ' parcours')
await prof.screenshot({ path: `${CAPTURES}/d8-espace-eleve.png`, fullPage: true })

attendre(erreurs.length === 0, 'erreurs JavaScript : ' + erreurs.join(' | '))
await navigateur.close()
console.log('Scénario des devoirs : tout est passé.')
