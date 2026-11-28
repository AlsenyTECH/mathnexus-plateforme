import { describe, expect, it } from 'vitest'
import { depuis, lienWhatsApp } from './utilitaires'

describe('outils de la V1', () => {
  it('fabrique un lien WhatsApp avec le numéro au format international', () => {
    expect(lienWhatsApp('Bonjour & bravo', '+221 77 666 55 44')).toBe('https://wa.me/221776665544?text=Bonjour%20%26%20bravo')
    expect(lienWhatsApp('Salut')).toBe('https://wa.me/?text=Salut')
  })

  it('dit depuis quand', () => {
    expect(depuis(null)).toBe('jamais')
    expect(depuis(new Date().toISOString())).toBe("aujourd'hui")
    expect(depuis(new Date(Date.now() - 3 * 86_400_000 - 1000).toISOString())).toBe('il y a 3 j')
  })
})
