#!/usr/bin/env python3
"""Rejoue les décisions des relecteurs sur content/book.json.

`convert.py` réécrit `content/book.json` depuis le docx à chaque exécution : y
inscrire les corrections serait détruit au dépôt suivant. Les décisions sont
donc une **couche rejouée après la conversion**, à chaque compilation. Le
manuscrit reste la source, la correction reste une donnée à part, et les deux
peuvent évoluer sans s'écraser.

Sans `content/decisions.json`, cette étape ne fait rien : la ligne de commande
se comporte exactement comme avant.

Seules les corrections de prononciation modifient le livre. Les décisions des
files éditeur et manager sont enregistrées et rapportées, mais pas appliquées :
un exercice mal apparié se corrige dans le manuscrit, et le corrigé est dérivé
des exercices — jamais recopié (invariant 2).
"""
import json, os, sys
from collections import Counter, defaultdict

from pairs import ecrire_pinyin, lire, parcourir

BOOK = "content/book.json"
DECISIONS = "content/decisions.json"
RAPPORT = "decisions_report.txt"


def main():
    if not os.path.exists(DECISIONS):
        print("décisions : aucune (content/decisions.json absent)")
        return

    book = json.load(open(BOOK))
    decisions = json.load(open(DECISIONS))

    # Index de secours : où se trouve chaque paire dans le livre d'aujourd'hui.
    # Sert quand l'adresse enregistrée ne correspond plus — un manuscrit remanié
    # décale les blocs sans que la correction cesse d'être valable.
    ailleurs = defaultdict(list)
    for _, zh, py, _, target in parcourir(book):
        ailleurs[(zh, py)].append(target)

    compte = Counter()
    lignes = []

    for d in decisions:
        etiquette = f"{d.get('by') or '?'} · {d.get('lesson') or '—'} · {d.get('zh') or d.get('item_id')}"

        if d.get("action") != "fix" or not (d.get("value") or "").strip():
            compte["triage"] += 1
            continue
        if d.get("kind") != "pinyin":
            compte["hors_portee"] += 1
            lignes.append(f"  non appliquée  {etiquette}\n"
                          f"                 file « {d.get('kind')} » : à corriger dans le manuscrit")
            continue

        zh, py, valeur = d.get("zh"), d.get("pinyin"), d["value"].strip()
        target = d.get("target")

        if target and lire(book, target) == (zh, py):
            ecrire_pinyin(book, target, valeur)
            compte["appliquees"] += 1
            lignes.append(f"  appliquée      {etiquette}\n"
                          f"                 « {py} » → « {valeur} »")
            continue

        if target and lire(book, target) == (zh, valeur):
            compte["deja"] += 1
            continue

        candidats = ailleurs.get((zh, py), [])
        if len(candidats) == 1:
            ecrire_pinyin(book, candidats[0], valeur)
            compte["relocalisees"] += 1
            lignes.append(f"  relocalisée    {etiquette}\n"
                          f"                 « {py} » → « {valeur} » (le bloc avait bougé)")
        elif len(candidats) > 1:
            compte["ambigues"] += 1
            lignes.append(f"  ambiguë        {etiquette}\n"
                          f"                 {len(candidats)} emplacements possibles, rien appliqué")
        else:
            compte["sans_objet"] += 1
            lignes.append(f"  sans objet     {etiquette}\n"
                          f"                 cette paire n'est plus dans le manuscrit")

    json.dump(book, open(BOOK, "w"), ensure_ascii=False, indent=1)

    entete = [
        "DÉCISIONS DES RELECTEURS APPLIQUÉES AU LIVRE",
        "=" * 60,
        f"  {compte['appliquees']:>4} corrections appliquées",
        f"  {compte['relocalisees']:>4} appliquées après relocalisation du bloc",
        f"  {compte['deja']:>4} déjà en place",
        f"  {compte['ambigues']:>4} ambiguës (non appliquées)",
        f"  {compte['sans_objet']:>4} sans objet (contenu disparu du manuscrit)",
        f"  {compte['hors_portee']:>4} hors portée (exercices, corrigés)",
        f"  {compte['triage']:>4} validations ou passages (sans effet sur le livre)",
        "",
    ]
    open(RAPPORT, "w").writelines("\n".join(entete + lignes) + "\n")

    posees = compte["appliquees"] + compte["relocalisees"]
    reste = compte["ambigues"] + compte["sans_objet"]
    print(f"décisions : {posees} correction(s) appliquée(s)"
          + (f", {reste} non applicable(s)" if reste else "")
          + f"  → {RAPPORT}")


if __name__ == "__main__":
    main()
