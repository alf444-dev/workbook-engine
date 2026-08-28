#!/usr/bin/env python3
"""La langue enseignée, déclarée une fois, lue partout.

Tout ce qui dépend de la langue vit dans `config/<langue>.json` : la plage
Unicode de son écriture, les signes de sa romanisation, la vérification de
prononciation disponible. Le moteur, lui, n'en sait rien — c'est ce qui permet
d'ajouter le japonais en écrivant un fichier de config, sans toucher au code.

    WB_LANGUE=japanese python3 pipeline/glossary.py

Note sur les noms de champs : dans les blocs, `zh` désigne **l'écriture cible**
et `pinyin` **la prononciation**, quelle que soit la langue. Ces noms sont
hérités du premier livre. Les renommer toucherait le convertisseur, le
template Typst, la console et les décisions déjà enregistrées, pour un gain
purement cosmétique : on les garde, et on les documente.
"""
import json, os, re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DEFAUT = "chinese"


def _chemin(nom=None):
    nom = nom or os.environ.get("WB_LANGUE", DEFAUT)
    return RACINE / "config" / f"{nom}.json"


def charger(nom=None):
    chemin = _chemin(nom)
    if not chemin.exists():
        raise FileNotFoundError(
            f"config de langue introuvable : {chemin}. "
            f"Langues disponibles : {', '.join(sorted(p.stem for p in (RACINE / 'config').glob('*.json')))}")
    return json.load(open(chemin, encoding="utf-8"))


CONFIG = charger()
ECRITURE = CONFIG.get("ecriture", {})

NOM = CONFIG.get("langue", "?")
CODE = CONFIG.get("code", "?")

# Plage Unicode de l'écriture enseignée. Sans elle, impossible de compter le
# vocabulaire ni de distinguer la langue cible de la langue d'explication.
PLAGE = ECRITURE.get("plage_unicode", "一-鿿")
SCRIPT = re.compile(f"[{PLAGE}]")

# Signes diacritiques de la romanisation : ils servent à ne pas confondre le
# pinyin (ou le rōmaji) avec de l'anglais quand on mesure le style.
DIACRITIQUES = set(ECRITURE.get("diacritiques_romanisation", ""))

# Nom du contrôle automatique de prononciation, ou None. Absent, la file du
# professeur natif est vide : c'est lui qui porte alors toute la vérification.
VERIFICATION = ECRITURE.get("verification_prononciation") or None


def resume():
    return (f"{NOM} ({CODE}) — écriture {PLAGE!r}, "
            f"prononciation vérifiée par {VERIFICATION or 'personne (file professeur seule)'}")
