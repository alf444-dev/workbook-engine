#!/usr/bin/env python3
"""Applique les décisions du professeur à la progression proposée.

La proposition du modèle n'est qu'un brouillon. Ce script en tire le curriculum
**validé**, celui que `plan.py` transmettra ensuite à la génération :

    valider   → l'entrée est retenue telle quelle
    corriger  → l'entrée est remplacée par ce qu'a écrit le professeur
    écarter   → l'entrée disparaît du curriculum
    passer    → l'entrée est retenue, mais signalée comme non relue

Une correction est interprétée par son contenu, pas par un champ à choisir :
si elle contient de l'écriture cible, c'est le mot qui change ; sinon c'est sa
prononciation. Un professeur qui écrit « 犬 inu » corrige les deux.

    python3 pipeline/apply_vocab.py     → content/vocabulaire_valide.json
"""
import json, os, sys

from ids import Numeroteur
from langue import CODE, SCRIPT
from pairs import tc

PROPOSE = "content/vocabulaire_propose.json"
DECISIONS = "content/decisions.json"
OUT = "content/vocabulaire_valide.json"
RAPPORT = "vocabulaire_valide.txt"


def separer(correction):
    """Rend (écriture, prononciation) déduites de ce qu'a écrit le professeur.

    En écriture non latine, ce qui est dans la plage cible est le mot, le reste
    est sa prononciation — « 犬 inu » corrige les deux. En alphabet latin cette
    séparation n'existe pas : la convention est « mot — prononciation », et un
    texte sans tiret corrige le mot seul.
    """
    from langue import MODE
    if MODE == "mots":
        if "—" in correction or " - " in correction:
            mot, _, pron = correction.replace(" - ", "—").partition("—")
            return (mot.strip() or None), (pron.strip() or None)
        return (correction.strip() or None), None
    cible = "".join(c for c in correction if SCRIPT.match(c))
    reste = "".join(c for c in correction if not SCRIPT.match(c)).strip(" —-–\t")
    return (cible or None), (reste or None)


def main():
    if not os.path.exists(PROPOSE):
        sys.exit(f"{PROPOSE} absent — lancer d'abord pipeline/propose_vocab.py")
    propose = json.load(open(PROPOSE))
    decisions = {}
    if os.path.exists(DECISIONS):
        for d in json.load(open(DECISIONS)):
            if d.get("kind") == "vocabulaire":
                decisions[d["item_id"]] = d

    # Les identifiants sont ceux du bundle, reconstruits par la même fonction
    # et dans le même ordre : leçons, puis entrées.
    stable_id = Numeroteur()

    compte = {"retenues": 0, "corrigees": 0, "ecartees": 0, "non_relues": 0}
    lignes = []
    sortie = {"langue": CODE, "lecons": []}
    for lecon in propose["lecons"]:
        entrees = []
        for e in lecon["entrees"]:
            cle = stable_id("vocabulaire", tc(lecon.get("titre", "")), e["ecriture"],
                            f"{e['prononciation']} — {e['sens']}")
            d = decisions.get(cle)
            action = (d or {}).get("action", "aucune")
            if action == "drop":
                compte["ecartees"] += 1
                lignes.append(f"  écartée      {e['ecriture']}  ({e['prononciation']}) "
                              f"— {(d or {}).get('by', '?')}")
                continue
            if action == "fix" and (d.get("value") or "").strip():
                ecriture, prononciation = separer(d["value"].strip())
                avant = f"{e['ecriture']} / {e['prononciation']}"
                if ecriture:
                    e = {**e, "ecriture": ecriture}
                if prononciation:
                    e = {**e, "prononciation": prononciation}
                compte["corrigees"] += 1
                lignes.append(f"  corrigée     {avant}  →  "
                              f"{e['ecriture']} / {e['prononciation']}")
            elif action in ("aucune", "skip"):
                compte["non_relues"] += 1
            else:
                compte["retenues"] += 1
            entrees.append(e)
        sortie["lecons"].append({**lecon, "entrees": entrees})

    os.makedirs("content", exist_ok=True)
    json.dump(sortie, open(OUT, "w"), ensure_ascii=False, indent=1)
    total = sum(len(l["entrees"]) for l in sortie["lecons"])
    entete = ["CURRICULUM VALIDÉ", "=" * 58,
              f"  {total} entrées retenues sur "
              f"{sum(len(l['entrees']) for l in propose['lecons'])} proposées",
              f"  {compte['retenues']} validées, {compte['corrigees']} corrigées, "
              f"{compte['ecartees']} écartées, {compte['non_relues']} non relues", ""]
    open(RAPPORT, "w").write("\n".join(entete + lignes) + "\n")
    print(f"curriculum : {total} entrées retenues "
          f"({compte['corrigees']} corrigées, {compte['ecartees']} écartées, "
          f"{compte['non_relues']} non relues)  → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
