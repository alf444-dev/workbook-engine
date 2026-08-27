#!/usr/bin/env python3
"""Confronte un plan au livre réel — la courbe vaut-elle mieux qu'une moyenne ?

Un plan n'a d'intérêt que s'il encadre les vraies leçons. On le vérifie sur le
livre validé : combien de ses leçons tombent dans la bande prévue par le plan ?
Et surtout : est-ce mieux qu'un plan plat, qui donnerait le même quota à toutes
les leçons ? Si la courbe n'apporte rien, autant ne pas la porter.

    python3 pipeline/check_plan.py
"""
import json, sys

PLAN = "content/plan.json"
PROFIL = "content/profile.json"
TOLERANCE = 0.5


def bande(cible, tolerance=TOLERANCE):
    return int(cible * (1 - tolerance)), max(1, int(cible * (1 + tolerance)))


def taux(reels, cibles):
    """Part des leçons dont la valeur réelle tombe dans la bande prévue."""
    dedans = sum(1 for reel, cible in zip(reels, cibles)
                 if bande(cible)[0] <= reel <= bande(cible)[1])
    return dedans, len(reels)


def main():
    plan = json.load(open(PLAN))
    profil = json.load(open(PROFIL))
    reelles = [l for l in profil["detail"] if l["genre"] == "chapter"]
    if len(reelles) != len(plan["lecons"]):
        sys.exit(f"plan de {len(plan['lecons'])} leçons contre {len(reelles)} dans le livre : "
                 "relancer plan.py sans --lecons")

    print(f"plan de {len(reelles)} leçons confronté au livre mesuré\n")

    reels = [l["caracteres_nouveaux"] for l in reelles]
    courbe = [l["quotas"]["caracteres_nouveaux"]["cible"] for l in plan["lecons"]]
    plat = [round(sum(reels) / len(reels))] * len(reels)

    a, n = taux(reels, courbe)
    b, _ = taux(reels, plat)
    print(f"  vocabulaire nouveau")
    print(f"    plan en courbe   {a:>3}/{n} leçons dans la bande   ({a / n:.0%})")
    print(f"    plan plat        {b:>3}/{n} leçons dans la bande   ({b / n:.0%})")
    verdict = ("la courbe apporte" if a > b else
               "la courbe n'apporte rien" if a == b else "la courbe dégrade")
    print(f"    → {verdict}\n")

    print("  quotas à cible constante (le reste du plan)")
    for champ in ("mots_prose", "tableaux", "dialogues", "repliques", "paires", "sections"):
        if champ not in plan["lecons"][0]["quotas"]:
            continue
        reels_c = [l[champ] for l in reelles]
        cibles = [l["quotas"][champ]["cible"] for l in plan["lecons"]]
        d, m = taux(reels_c, cibles)
        print(f"    {champ:<14} {d:>3}/{m}   ({d / m:.0%})")

    return 0 if a >= b else 1


if __name__ == "__main__":
    sys.exit(main())
