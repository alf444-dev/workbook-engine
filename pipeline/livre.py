#!/usr/bin/env python3
"""Où trouver le livre de référence, quel que soit son nom du moment.

Dans un projet de génération, le livre qui sert de modèle est déposé sous
`content/book_typed.json`, puis renommé `content/reference_typed.json` une fois
ses mesures prises — sinon ses items apparaîtraient dans les files de relecture
du nouveau livre, qui ne le concernent pas.

Ce détail a coûté une série de leçons : `assemble.py` connaissait les deux noms,
`generate.py` n'en connaissait qu'un et échouait sur
`FileNotFoundError: content/book_typed.json`. La règle vit désormais à un seul
endroit ; deux copies auraient fini par diverger de nouveau.
"""
import json
from pathlib import Path

NOMS = ("content/book_typed.json", "content/reference_typed.json")


def chemin():
    """Le premier des deux noms qui existe."""
    for nom in NOMS:
        if Path(nom).exists():
            return nom
    raise FileNotFoundError("aucun livre de référence : " + " ni ".join(NOMS))


def charger():
    with open(chemin(), encoding="utf-8") as f:
        return json.load(f)
