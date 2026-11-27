"""Photos de copies : vérifiées à l'octet près, gardées petites."""
from django.conf import settings

TAILLE_MAX = getattr(settings, "PHOTO_TAILLE_MAX", 3 * 1024 * 1024)
NOMBRE_MAX = 8
SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
)


def type_image(donnees: bytes):
    """Le vrai type d'une image, lu dans ses premiers octets (jamais dans son nom ni son en-tête HTTP)."""
    for signature, mime in SIGNATURES:
        if donnees.startswith(signature):
            return mime
    if len(donnees) > 12 and donnees[:4] == b"RIFF" and donnees[8:12] == b"WEBP":
        return "image/webp"
    return None


def verifier(fichier):
    """Renvoie (données, type) ou lève ValueError avec un message pour l'utilisateur."""
    if fichier is None:
        raise ValueError("Aucune photo reçue.")
    if fichier.size > TAILLE_MAX:
        raise ValueError(f"Photo trop lourde (au plus {TAILLE_MAX // (1024 * 1024)} Mo).")
    donnees = fichier.read()
    mime = type_image(donnees)
    if mime is None:
        raise ValueError("Seules les photos JPEG, PNG ou WebP sont acceptées.")
    return donnees, mime
