#!/usr/bin/env python3
"""Charge les secrets depuis un fichier .env, sans dépendance.

La clé de génération ne doit apparaître ni dans le dépôt, ni dans un historique
de commandes, ni dans une conversation. Elle vit dans un `.env` à la racine,
ignoré par git, que seul le code lit.

En production, rien de tout ça : Render fournit les variables d'environnement,
et le `.env` est simplement absent.
"""
import os
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def charger(chemin=None):
    """Verse les clés du .env dans l'environnement, sans écraser l'existant."""
    fichier = Path(chemin) if chemin else RACINE / ".env"
    if not fichier.exists():
        return []
    poses = []
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, _, valeur = ligne.partition("=")
        cle = cle.strip()
        valeur = valeur.strip().strip('"').strip("'")
        if cle and cle not in os.environ:
            os.environ[cle] = valeur
            poses.append(cle)
    return poses
