"""Vercel lit pyproject.toml, Docker et le poste local lisent requirements.txt : mêmes dépendances."""
import tomllib
from pathlib import Path

ICI = Path(__file__).resolve().parent


def test_dependances_identiques():
    projet = tomllib.loads((ICI / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    lignes = [
        ligne.strip() for ligne in (ICI / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.startswith("#")
    ]
    assert sorted(projet) == sorted(lignes)
