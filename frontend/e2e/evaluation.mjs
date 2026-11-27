/**
 * Scénario de bout en bout des évaluations (format 2) dans Chrome :
 * connexion de l'élève → étape avec le QCM de sortie → réponses → rechargement (reprise) →
 * fin et correction → évaluation chronométrée commencée.
 *
 * Préparer la base et lancer les deux serveurs, puis :
 *   cd backend && python manage.py preparer_demo --mot-de-passe Cahier-quadrille-2026
 *   GROUPE=<id affiché> BASE=http://127.0.0.1:5173 CHROME=/usr/bin/google-chrome node e2e/evaluation.mjs
 */
import { chromium } from 'playwright-core'
import { mkdirSync } from 'node:fs'

const BASE = process.env.BASE ?? 'http://127.0.0.1:5173'
const GROUPE = process.env.GROUPE
const TELEPHONE = process.env.TELEPHONE ?? '770000001'
const MDP = process.env.MDP ?? 'Cahier-quadrille-2026'
const CAPTURES = process.env.CAPTURES ?? 'e2e/captures'
if (!GROUPE) throw new Error('GROUPE manquant (identifiant affiché par preparer_demo)')
mkdirSync(CAPTURES, { recursive: true })

let n = 0
const etape = (t) => console.log(`${++n}. ${t}`)
const verifier = (cond, msg) => { if (!cond) throw new Error('ÉCHEC : ' + msg) }

const navigateur = await chromium.launch({ executablePath: process.env.CHROME ?? '/usr/bin/google-chrome', args: ['--no-sandbox'] })
const erreurs = []
const contexte = await navigateur.newContext({ viewport: { width: 390, height: 844 }, locale: 'fr-FR' })
const p = await contexte.newPage()
p.on('pageerror', (e) => erreurs.push(e.message))
p.on('response', (r) => r.status() >= 400 && erreurs.push(`${r.status()} ${r.url()}`))
const requetes = []
p.on('request', (r) => r.url().includes('/api/tentatives/') && requetes.push(`${r.method()} ${r.url()} ${r.postData() ?? ''}`))
const reponsesRecues = []
p.on('response', async (r) => {
  if (r.url().includes('/evaluations/') || r.url().includes('/tentatives/')) reponsesRecues.push(await r.text().catch(() => ''))
})

try {
  await p.goto(`${BASE}/connexion`)
  await p.getByLabel('Numéro de téléphone').fill(TELEPHONE)
  await p.getByLabel('Mot de passe').fill(MDP)
  await p.getByRole('button', { name: 'Se connecter' }).click()
  await p.waitForURL(/\/classe\//)
  etape("L'élève se connecte et arrive dans sa classe")

  await p.goto(`${BASE}/classe/${GROUPE}/demo-evaluations/module-conjugue`)
  await p.locator('.evd-titre').waitFor()
  verifier((await p.locator('.evd-infos').textContent()).includes('3 questions'), "l'accueil annonce 3 questions")
  verifier(await p.locator('.lbody .katex').count() > 0, 'les formules du cours sont rendues')
  await p.locator('.evd').screenshot({ path: `${CAPTURES}/eval-01-accueil.png` })
  etape("L'accueil de l'évaluation s'affiche dans l'étape")

  await p.getByRole('button', { name: 'Commencer' }).click()
  await p.getByText('Question 1 / 3').waitFor()
  verifier(await p.locator('.evd-enonce .katex').count() > 0, "l'énoncé est rendu en KaTeX")
  await p.waitForTimeout(1200)
  await p.getByRole('radio').first().click()
  await p.waitForResponse((r) => r.url().includes('/reponses/module/') && r.status() === 200)
  etape('Question 1 : réponse a) enregistrée (PUT accepté, jeton CSRF compris)')

  await p.locator('.evd').getByRole('button', { name: 'Question suivante →' }).click()
  await p.getByText('Question 2 / 3').waitFor()
  await p.waitForTimeout(800)
  await p.getByRole('radio').nth(0).click() // faux exprès
  await p.waitForResponse((r) => r.url().includes('/reponses/conjugue/'))
  await p.locator('.evd').screenshot({ path: `${CAPTURES}/eval-02-question.png` })
  etape('Question 2 : réponse a) (fausse exprès) enregistrée')

  await p.reload()
  await p.getByRole('button', { name: 'Reprendre' }).click()
  await p.getByText('Question 3 / 3').waitFor()
  etape('Après un rechargement : « Reprendre » ramène à la première question sans réponse')

  await p.getByRole('checkbox').nth(0).click()
  await p.waitForResponse((r) => r.url().includes('/reponses/reels/'))
  await p.getByRole('checkbox').nth(2).click()
  await p.waitForResponse((r) => r.url().includes('/reponses/reels/'))
  await p.locator('.evd').getByRole('button', { name: "Terminer l'évaluation" }).click()
  await p.locator('.evd-score').waitFor()
  const score = await p.locator('.evd-score').textContent()
  verifier(score === '2 / 3', `score 2 / 3 (obtenu : ${score})`)
  verifier((await p.locator('.evd-verdict').textContent()).startsWith('Réussi'), 'réussi au seuil de 2')
  verifier(await p.locator('.evd-explication .katex').count() > 0, 'les explications sont rendues')
  await p.locator('.evd').screenshot({ path: `${CAPTURES}/eval-03-correction.png` })
  etape(`Correction : ${score}, réussi, explications affichées`)

  const avantFin = reponsesRecues.slice(0, -1).join('\n')
  verifier(!avantFin.includes('"bonnes"') && !avantFin.includes('"explication"'), 'rien de la correction avant la fin')
  etape(`${reponsesRecues.length - 1} réponses du serveur avant la fin : aucune ne contient « bonnes » ni « explication »`)

  await p.goto(`${BASE}/classe/${GROUPE}/demo-evaluations/evaluation-c`)
  await p.getByRole('button', { name: 'Commencer' }).click()
  await p.locator('.evd-temps').waitFor()
  const t1 = await p.locator('.evd-temps').textContent()
  await p.waitForTimeout(2100)
  const t2 = await p.locator('.evd-temps').textContent()
  verifier(t1 !== t2 && t1.startsWith('0'), `le chronomètre tourne (${t1} → ${t2})`)
  await p.locator('.evd').screenshot({ path: `${CAPTURES}/eval-04-chrono.png` })
  etape(`Évaluation chronométrée : ${t1} → ${t2}`)

  verifier(erreurs.length === 0, 'aucune erreur : ' + erreurs.join(' | '))
  console.log('Scénario terminé sans erreur.')
} finally {
  await navigateur.close()
}
