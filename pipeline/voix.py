#!/usr/bin/env python3
"""Ce qui « sent l'IA » dans la prose — mesuré, avec le CN10 pour référence.

Chantier 1.1 du plan produit. Ce que les éditeurs appellent « robotique »
n'est pas un goût, c'est un ensemble de régularités mesurables : des phrases
de longueur uniforme, des tics (« it's worth noting »), des énumérations à
trois termes, des rafales de phrases qui commencent pareil. Le CN10 — écrit
par des humains, relu, publié — donne la référence de ce qu'un texte humain
se permet.

Invariant 4 : aucune bande n'est codée en dur. Chaque seuil est la pire leçon
humaine plus 20 % de marge, calculé sur le livre de référence à l'exécution —
la méthode qui a donné zéro faux positif sur la répétition inter-leçons.

Seule la prose compte : tableaux, dialogues et consignes d'exercices sont la
voix maison, on veut qu'ils se répètent.

    python3 pipeline/voix.py                    # rapport sur content/book.json
    python3 pipeline/voix.py --livre X.json     # sur un autre livre
"""
import json, re, statistics
from pathlib import Path

from lesson_profile import parcours
from pairs import plain

# Liste amorce des tics. Provisoire à dessein : le chantier 1.3 la remplacera
# par ce que les éditeurs suppriment réellement dans leurs réécritures.
TICS = (
    "it's worth noting", "it is worth noting", "let's dive", "let's explore",
    "whether you're", "whether you are", "in today's", "a testament to",
    "delve", "unlock", "unleash", "elevate your", "game-changer",
    "seamlessly", "effortlessly", "in conclusion", "to sum up",
    "the beauty of", "rich tapestry", "embark on", "journey of",
    "it's important to note", "needless to say",
)

MARGE = 0.2
RE_PHRASE = re.compile(r"[^.!?]+[.!?]+")
RE_MOT = re.compile(r"[A-Za-z][A-Za-z'’-]*")
# « X, Y(,) and Z » — l'énumération fétiche des modèles quand elle est à trois.
RE_ENUM = re.compile(r"\b[\w'’-]+(?:\s+[\w'’-]+){0,2},\s+(?:[\w'’-]+(?:\s+[\w'’-]+){0,2},\s+)*"
                     r"(?:and|or)\s+[\w'’-]+", re.I)

SIGNAUX = ("rythme", "tics", "listes_de_trois", "questions", "ponctuation",
           "rafales", "adverbes_ly")
# Pour le rythme, le défaut est d'être TROP régulier : la bande est un plancher.
PLANCHERS = {"rythme"}


def prose(ch):
    """Les paragraphes de prose d'une leçon, hors exercices."""
    out = []
    for bloc, dans_exercice in parcours(ch.get("blocks", [])):
        if dans_exercice or bloc.get("type") not in ("para",):
            continue
        t = plain(bloc.get("text", ""))
        # retirer ce qui n'est pas de l'anglais : l'écriture cible et sa
        # romanisation ne participent pas à la voix anglaise
        t = re.sub(r"[^\x00-\x7F]+", " ", t)
        if t.strip():
            out.append(t)
    return out


def mesurer(ch):
    """Les sept signaux d'une leçon. Rend None si la prose est trop courte
    pour que les ratios veuillent dire quelque chose."""
    paras = prose(ch)
    texte = " ".join(paras)
    phrases = [p.strip() for p in RE_PHRASE.findall(texte) if p.strip()]
    mots = RE_MOT.findall(texte)
    if len(phrases) < 8 or len(mots) < 120:
        return None

    longueurs = [len(RE_MOT.findall(p)) for p in phrases]
    bas = texte.lower()
    tics = sum(bas.count(t) for t in TICS)
    enums = RE_ENUM.findall(texte)
    trois = sum(1 for e in enums
                if len(re.split(r",\s+|\s+(?:and|or)\s+", e, flags=re.I)) == 3)
    questions = texte.count("?")
    ponct = texte.count("—") + texte.count("!")
    debuts = [RE_MOT.match(p).group(0).lower() for p in phrases if RE_MOT.match(p)]
    rafales = sum(1 for a, b in zip(debuts, debuts[1:]) if a == b)
    ly = sum(1 for m in mots if m.lower().endswith("ly"))

    pour_mille = lambda n: round(n * 1000 / len(mots), 2)
    return {
        "rythme": round(statistics.pstdev(longueurs), 2),
        "tics": pour_mille(tics),
        "listes_de_trois": round(trois / len(enums), 3) if enums else 0.0,
        "questions": pour_mille(questions),
        "ponctuation": pour_mille(ponct),
        "rafales": round(rafales / max(1, len(phrases) - 1), 3),
        "adverbes_ly": round(ly / len(mots), 4),
        "_phrases": len(phrases), "_mots": len(mots),
    }


def bandes(book):
    """Les seuils, déduits des leçons humaines du livre de référence."""
    valeurs = {s: [] for s in SIGNAUX}
    for ch in book["chapters"]:
        if ch.get("kind") != "chapter":
            continue
        m = mesurer(ch)
        if m:
            for s in SIGNAUX:
                valeurs[s].append(m[s])
    out = {}
    for s in SIGNAUX:
        if not valeurs[s]:
            continue
        if s in PLANCHERS:
            out[s] = round(min(valeurs[s]) * (1 - MARGE), 3)
        else:
            out[s] = round(max(valeurs[s]) * (1 + MARGE), 3)
    return out


def verifier(ch, seuils):
    """Les signaux d'une leçon hors de la bande humaine. Rend une liste
    (signal, valeur, seuil, sens)."""
    m = mesurer(ch)
    if not m:
        return []
    sorties = []
    for s in SIGNAUX:
        if s not in seuils:
            continue
        if s in PLANCHERS:
            if m[s] < seuils[s]:
                sorties.append((s, m[s], seuils[s], "sous"))
        elif m[s] > seuils[s]:
            sorties.append((s, m[s], seuils[s], "au-dessus"))
    return sorties


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--livre", default="content/book.json")
    ap.add_argument("--reference", default=None,
                    help="livre humain d'où déduire les bandes "
                         "(défaut : le livre lui-même)")
    a = ap.parse_args()

    book = json.loads(Path(a.livre).read_text(encoding="utf-8"))
    reference = (json.loads(Path(a.reference).read_text(encoding="utf-8"))
                 if a.reference else book)
    seuils = bandes(reference)
    print("bandes déduites du livre de référence "
          "(pire leçon humaine, 20 % de marge) :")
    for s in SIGNAUX:
        if s in seuils:
            sens = "≥" if s in PLANCHERS else "≤"
            print(f"  {s:16} {sens} {seuils[s]}")

    signalees = 0
    for ch in book["chapters"]:
        if ch.get("kind") != "chapter":
            continue
        depassements = verifier(ch, seuils)
        if depassements:
            signalees += 1
            print(f"\n  {ch.get('title', '?')[:52]}")
            for s, v, seuil, sens in depassements:
                print(f"    [{s}] {v} ({sens} de {seuil})")
    total = sum(1 for c in book["chapters"] if c.get("kind") == "chapter")
    print(f"\n{signalees}/{total} leçons hors de la bande humaine")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
