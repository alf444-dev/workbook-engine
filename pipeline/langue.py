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

# Les langues créées depuis le site vivent sur le disque persistant, pas dans
# l'image : `config/` est reconstruit à chaque déploiement, une langue ajoutée
# par le team manager y disparaîtrait sans prévenir. On regarde donc le disque
# d'abord, le dépôt ensuite.
def dossiers():
    donnees = os.environ.get("WB_DATA")
    lieux = [Path(donnees) / "config"] if donnees else []
    return lieux + [RACINE / "config"]


def _chemin(nom=None):
    nom = nom or os.environ.get("WB_LANGUE", DEFAUT)
    for dossier in dossiers():
        candidat = dossier / f"{nom}.json"
        if candidat.exists():
            return candidat
    return RACINE / "config" / f"{nom}.json"


def disponibles():
    """Toutes les langues connues, disque persistant et dépôt confondus."""
    noms = set()
    for dossier in dossiers():
        if dossier.exists():
            noms |= {p.stem for p in dossier.glob("*.json")}
    return sorted(noms)


def charger(nom=None):
    chemin = _chemin(nom)
    if not chemin.exists():
        raise FileNotFoundError(
            f"config de langue introuvable : {chemin}. "
            f"Langues disponibles : {', '.join(sorted(disponibles()))}")
    return json.load(open(chemin, encoding="utf-8"))


CONFIG = charger()
ECRITURE = CONFIG.get("ecriture", {})

NOM = CONFIG.get("langue", "?")
CODE = CONFIG.get("code", "?")
# Nom anglais : les messages affichés sur le site sont en anglais.
ANGLAIS = CONFIG.get("nom_anglais") or NOM.capitalize()

# Plage Unicode de l'écriture enseignée. Sans elle, impossible de compter le
# vocabulaire ni de distinguer la langue cible de la langue d'explication.
PLAGE = ECRITURE.get("plage_unicode", "一-鿿")
# Mode de comptage du vocabulaire : « caracteres » (chinois, japonais…) ou
# « mots » (langues à alphabet latin, où la cible partage l'alphabet de la
# langue d'explication et où compter des caractères n'a pas de sens).
MODE = ECRITURE.get("mode", "caracteres")
# Une plage vide (mode mots) donne une expression qui ne matche jamais : tout
# ce qui compte des caractères cibles en trouve zéro, ce qui est le bon compte.
SCRIPT = re.compile(f"[{PLAGE}]" if PLAGE else r"(?!x)x")

# Signes diacritiques de la romanisation : ils servent à ne pas confondre le
# pinyin (ou le rōmaji) avec de l'anglais quand on mesure le style.
DIACRITIQUES = set(ECRITURE.get("diacritiques_romanisation", ""))

# Signature de l'écriture : ce qu'un texte réellement écrit dans cette langue
# contient, et qu'un texte d'une autre langue ne contient pas. Indispensable
# parce que la plage Unicode ne suffit pas : les kanji japonais et les
# sinogrammes chinois occupent le **même bloc**, si bien qu'une leçon
# entièrement chinoise passe un contrôle « écriture cible » pour le japonais.
# C'est exactement ce qui a produit un livre chinois vendu comme japonais.
SIGNATURE = re.compile(f"[{ECRITURE['signature']}]") if ECRITURE.get("signature") else None

# Ce qu'un texte de cette langue ne peut pas contenir (des kana dans un livre
# de chinois, par exemple). Facultatif.
EXCLUT = re.compile(f"[{ECRITURE['exclut']}]") if ECRITURE.get("exclut") else None


def langue_plausible(textes, seuil=0.6):
    """Ces textes sont-ils écrits dans la langue cible ?

    Rend (verdict, message). Sans signature déclarée, on ne prétend pas
    trancher : c'est un contrôle qui se tait plutôt que de crier au loup.
    """
    if MODE == "mots":
        # Impossible de prouver que c'est de l'espagnol et pas de l'italien :
        # on vérifie seulement qu'aucune écriture non latine ne s'est glissée.
        textes_pleins = [t for t in textes if t]
        if not textes_pleins:
            return False, "no text at all"
        if EXCLUT:
            fautifs = [t for t in textes_pleins if EXCLUT.search(t)]
            if fautifs:
                return False, (f"{len(fautifs)}/{len(textes_pleins)} entries use a "
                               f"non-Latin script — e.g. “{fautifs[0][:30]}”")
        return True, ""
    echantillon = [t for t in textes if t and SCRIPT.search(t)]
    if not echantillon:
        return False, f"no text in the {ANGLAIS} writing system"
    if EXCLUT:
        fautifs = [t for t in echantillon if EXCLUT.search(t)]
        if fautifs:
            return False, (f"{len(fautifs)}/{len(echantillon)} entries use a writing "
                           f"system foreign to {ANGLAIS} — e.g. “{fautifs[0][:30]}”")
    if not SIGNATURE:
        return True, ""
    portent = [t for t in echantillon if SIGNATURE.search(t)]
    part = len(portent) / len(echantillon)
    if part < seuil:
        return False, (f"only {len(portent)}/{len(echantillon)} entries carry the "
                       f"{ANGLAIS} signature ({part:.0%}, threshold {seuil:.0%}) — "
                       f"e.g. “{next(t for t in echantillon if not SIGNATURE.search(t))[:30]}”")
    return True, ""


# Nom du contrôle automatique de prononciation, ou None. Absent, la file du
# professeur natif est vide : c'est lui qui porte alors toute la vérification.
VERIFICATION = ECRITURE.get("verification_prononciation") or None


# Titre du livre. Il était écrit en dur dans le convertisseur et dans le
# template : un livre de japonais est sorti avec « LEARN CHINESE » sur la
# couverture et sur chacune de ses 238 pages.
def titres_du_livre():
    return {"book_title": f"LEARN {ANGLAIS.upper()}",
            "book_subtitle": "FOR BEGINNERS",
            "cover_title": f"LEARN {ANGLAIS.upper()}",
            "cover_subtitle": "FOR ADULT BEGINNERS"}


def resume():
    return (f"{NOM} ({CODE}) — écriture {PLAGE!r}, "
            f"prononciation vérifiée par {VERIFICATION or 'personne (file professeur seule)'}")
