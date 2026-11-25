"""Normalisation des numéros de téléphone au format international (E.164).

Un numéro sénégalais saisi « 77 123 45 67 » devient « +221771234567 ».
"""
import re

from django.core.exceptions import ValidationError

INDICATIF_PAR_DEFAUT = "+221"
_FORMAT_E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def normaliser_telephone(valeur: str) -> str:
    brut = re.sub(r"[\s.\-()]", "", str(valeur or ""))
    if brut.startswith("00"):
        brut = "+" + brut[2:]
    if not brut.startswith("+"):
        # Numéro local sénégalais : 9 chiffres commençant par 7 (mobiles) ou 3 (fixes).
        if re.fullmatch(r"[37]\d{8}", brut):
            brut = INDICATIF_PAR_DEFAUT + brut
        else:
            raise ValidationError("Numéro de téléphone invalide.")
    if not _FORMAT_E164.match(brut):
        raise ValidationError("Numéro de téléphone invalide.")
    return brut
