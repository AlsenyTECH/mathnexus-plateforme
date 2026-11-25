/**
 * Scénario de bout en bout dans un vrai navigateur (Chrome) :
 * inscription avec code de classe → attente → validation par l'admin → classe → lecture d'une étape
 * (formules, graphique) → validation → étape premium refusée → espace prof.
 *
 *   CODE=<code de classe> BASE=http://127.0.0.1:5173 CHROME=/usr/bin/google-chrome node e2e/scenario.mjs
 *
 * Il faut l'API Django avec les deux parcours importés et rattachés, et un admin 771000000.
 */
import { chromium } from 'playwright-core'
import { mkdirSync } from 'node:fs'

const BASE = process.env.BASE ?? 'http://127.0.0.1:5173'
const CODE = process.env.CODE
const MDP_ADMIN = process.env.MDP_ADMIN ?? 'Cahier-quadrille-2026'
const CAPTURES = process.env.CAPTURES ?? 'e2e/captures'
mkdirSync(CAPTURES, { recursive: true })

const navigateur = await chromium.launch({ executablePath: process.env.CHROME ?? '/usr/bin/google-chrome', args: ['--no-sandbox'] })
const erreursConsole = []
// Refus voulus par le scénario : l'évaluation premium et l'étape pas encore ouverte.
const REFUS_ATTENDUS = [/\/etapes\/eval-p1\/$/, /\/etude-de-fonction\/etapes\/regles\/$/]
let n = 0
const etape = (t) => console.log(`${++n}. ${t}`)
const attendre = (cond, msg) => { if (!cond) throw new Error('ÉCHEC : ' + msg) }

async function page(nom, largeur = 390) {
  const contexte = await navigateur.newContext({ viewport: { width: largeur, height: 844 }, locale: 'fr-FR' })
  const p = await contexte.newPage()
  // Les « Failed to load resource » sont contrôlés plus finement par les réponses ci-dessous.
  p.on('console', (m) => m.type() === 'error' && !m.text().startsWith('Failed to load resource') && erreursConsole.push(`[${nom}] ${m.text()}`))
  p.on('response', (r) => {
    if (r.status() >= 400 && !(r.status() === 403 && REFUS_ATTENDUS.some((re) => re.test(r.url()))))
      erreursConsole.push(`[${nom}] ${r.status()} ${r.url()}`)
  })
  p.on('pageerror', (e) => erreursConsole.push(`[${nom}] ${e.message}`))
  return p
}
const capture = (p, nom) => p.screenshot({ path: `${CAPTURES}/${nom}.png`, fullPage: false })

try {
  // --- L'élève, sur téléphone ---
  const eleve = await page('élève')
  await eleve.goto(`${BASE}/inscription?code=${CODE}`)
  await eleve.getByLabel('Prénom').fill('Awa')
  await eleve.getByLabel('Nom', { exact: true }).fill('Ndiaye')
  await eleve.getByLabel('Numéro de téléphone').fill('77 123 45 67')
  await eleve.getByLabel('Mot de passe').fill('Cahier-quadrille-2026')
  await eleve.getByLabel("Téléphone d'un parent").fill('76 555 44 33')
  await eleve.getByLabel(/J'accepte les conditions/).check()
  await capture(eleve, '01-inscription')
  await eleve.getByRole('button', { name: 'Créer mon compte' }).click()
  await eleve.getByText('Ton compte est en attente').waitFor()
  etape("Inscription avec le code de classe : l'élève arrive sur la page d'attente")
  await capture(eleve, '02-attente')

  // --- L'admin, sur ordinateur ---
  const admin = await page('admin', 1280)
  await admin.goto(`${BASE}/connexion`)
  await admin.getByLabel('Numéro de téléphone').fill('771000000')
  await admin.getByLabel('Mot de passe').fill(MDP_ADMIN)
  await admin.getByRole('button', { name: 'Se connecter' }).click()
  await admin.getByText('Awa Ndiaye').waitFor()
  attendre(await admin.getByText('Demande : Terminale S2').isVisible(), 'la demande de classe est affichée')
  await capture(admin, '03-admin-comptes')
  await admin.getByRole('button', { name: 'Valider' }).click()
  await admin.getByText('Aucun compte en attente.').waitFor()
  etape("L'admin voit la demande et valide le compte")

  // --- Retour de l'élève ---
  await eleve.getByRole('button', { name: 'Vérifier maintenant' }).click()
  await eleve.getByText('Nombres complexes').first().waitFor()
  attendre(eleve.url().includes('/classe/'), 'redirection vers la classe')
  etape("L'élève est redirigé directement dans sa classe")
  await capture(eleve, '04-classe')

  await eleve.getByText('Nombres complexes').first().click()
  await eleve.getByRole('link', { name: /Commencer le parcours/ }).click()
  await eleve.locator('.lesson h2').waitFor()
  etape(`Lecteur ouvert sur « ${await eleve.locator('.lesson h2').textContent()} »`)

  await eleve.goto(eleve.url().replace(/\/[^/]+$/, '/conjugue'))
  await eleve.locator('.katex').first().waitFor()
  const formules = await eleve.locator('.katex').count()
  await eleve.locator('.graph canvas').first().scrollIntoViewIfNeeded()
  await eleve.waitForTimeout(300)
  const pixels = await eleve.locator('.graph canvas').first().evaluate((c) => {
    const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data
    let colores = 0
    for (let i = 0; i < d.length; i += 4) if (d[i + 3] > 0 && !(d[i] > 240 && d[i + 1] > 240 && d[i + 2] > 240)) colores++
    return colores
  })
  attendre(formules > 20, `formules rendues (${formules})`)
  attendre(pixels > 1000, `graphique dessiné (${pixels} pixels)`)
  etape(`Étape « Le conjugué » : ${formules} formules KaTeX, graphique dessiné (${pixels} pixels colorés)`)
  await capture(eleve, '05-lecteur-graphique')
  const avant = await eleve.locator('.g-read').first().textContent()
  await eleve.locator('.graph input[type=range]').first().fill('-2')
  const apres = await eleve.locator('.g-read').first().textContent()
  attendre(avant !== apres, 'le curseur fait réagir le graphique')
  etape('Le curseur du graphique fait réagir la figure')

  await eleve.getByRole('button', { name: /J'ai compris/ }).click()
  await eleve.waitForURL(/\/plan$/)
  await eleve.locator('.side .nav-list a.done').first().waitFor()
  attendre((await eleve.locator('.side .nav-list a.done').count()) === 1, 'une étape validée dans le sommaire')
  etape('« J\'ai compris » valide l\'étape et passe à la suivante')

  await eleve.goto(eleve.url().replace(/\/[^/]+$/, '/eval-p1'))
  await eleve.getByText("Cette étape fait partie de l'offre Premium.").waitFor()
  etape("L'évaluation premium est refusée avec un message clair")
  await capture(eleve, '06-premium')

  // --- L'admin comme prof : progression et évaluation ---
  await admin.goto(`${BASE}/prof`)
  await admin.getByRole('link', { name: /Terminale S2/ }).click()
  await admin.getByRole('link', { name: 'Nombres complexes' }).click()
  await admin.getByText('Progression des élèves').waitFor()
  attendre(await admin.getByRole('cell', { name: 'Awa Ndiaye' }).isVisible(), "l'élève figure dans le tableau")
  etape("Le prof voit la progression d'Awa")
  await capture(admin, '07-prof-progression')

  await admin.goto(`${BASE}/prof`)
  await admin.getByRole('link', { name: /Terminale S2/ }).click()
  await admin.getByRole('link', { name: 'Étude de fonction' }).click()
  await admin.getByText('Ouvrir les étapes au fil du cours').waitFor()
  await admin.locator('.ligne-ouverture', { hasText: 'Le domaine de définition' }).getByRole('button', { name: 'Ouvrir' }).click()
  await admin.locator('.ligne-ouverture', { hasText: 'Le domaine de définition' }).getByText('Ouverte').waitFor()
  etape('Le prof ouvre « Le domaine de définition » pour la classe')

  const urlClasse = eleve.url().replace(/\/nombres-complexes\/.*/, '')
  await eleve.goto(`${urlClasse}/etude-de-fonction/domaine`)
  await eleve.locator('.lesson h2').waitFor()
  etape("L'élève lit maintenant cette étape d'Étude de fonction")
  await eleve.goto(`${urlClasse}/etude-de-fonction/regles`)
  await eleve.getByText("Cette étape n'est pas encore ouverte par ton prof.").waitFor()
  etape('Les étapes non ouvertes restent fermées')

  // Une évaluation complète, vue par l'admin (qui a accès au premium)
  const urlAdmin = `${BASE}${new URL(urlClasse).pathname}/nombres-complexes/eval-p1`
  await admin.goto(urlAdmin)
  await admin.getByRole('button', { name: "Commencer l'évaluation" }).click()
  await admin.locator('.ev-sujet').waitFor({ state: 'visible' })
  await admin.getByRole('button', { name: "J'ai terminé" }).click()
  await admin.locator('.ev-cor input[type=checkbox]').first().check()
  await admin.locator('.ev-cor input[type=checkbox]').nth(1).check()
  const note = await admin.locator('.ev-note strong').textContent()
  attendre(note === '2', `note calculée (${note})`)
  etape(`Évaluation chronométrée : sujet, corrigé, barème coché → note ${note} / 20`)
  await capture(admin, '08-evaluation')

  attendre(erreursConsole.length === 0, 'aucune erreur dans la console :\n' + erreursConsole.join('\n'))
  etape('Aucune erreur dans la console, aucune réponse en erreur hors des deux refus voulus')
  console.log('\nSCÉNARIO RÉUSSI')
} catch (e) {
  console.error(e.message)
  if (erreursConsole.length) console.error('Console :\n' + erreursConsole.join('\n'))
  process.exitCode = 1
} finally {
  await navigateur.close()
}
