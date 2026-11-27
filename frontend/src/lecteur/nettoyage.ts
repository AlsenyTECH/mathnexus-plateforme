import DOMPurify from 'dompurify'

/**
 * Le serveur a déjà refusé tout paquet contenant du code. Par défense en profondeur, le
 * navigateur nettoie quand même chaque fragment avec DOMPurify avant de l'insérer.
 */
export function nettoyer(html: string): string {
  return DOMPurify.sanitize(html, {
    ADD_ATTR: ['hidden', 'crossorigin'],
    FORBID_TAGS: ['style', 'form', 'input', 'button', 'textarea', 'select'],
    ALLOW_DATA_ATTR: true,
  })
}
