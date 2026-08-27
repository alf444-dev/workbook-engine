#!/usr/bin/env python3
"""Vérifie le plan du livre : courbe, quotas, répartition des exercices.

Le plan contraint la génération. S'il n'est pas reproductible, deux
compilations du même livre demanderaient des leçons différentes ; s'il groupe
les types d'exercices, le livre généré ne ressemblera pas à la voix maison.

    python3 tests/test_plan.py
"""
import json, subprocess, sys, tempfile
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLANIFICATEUR = REPO / "pipeline" / "plan.py"
CONFIG = REPO / "config" / "chinese.json"

# Profil d'essai : une courbe de vocabulaire franchement décroissante.
PROFIL = {
    "lecons": 10, "histoires": 0, "caracteres_distincts": 300,
    "courbe": {"caracteres_nouveaux_premier_tiers": 150,
               "caracteres_nouveaux_dernier_tiers": 20},
    "detail": [{"titre": f"LEÇON {i + 1}", "genre": "chapter",
                "caracteres_nouveaux": v, "mots_prose": 700, "tableaux": 11,
                "dialogues": 2, "repliques": 9, "paires": 44, "sections": 7}
               for i, v in enumerate([60, 50, 45, 35, 30, 25, 20, 15, 12, 8])],
}


def planifier(*args, profil=None):
    tmp = Path(tempfile.mkdtemp(prefix="wb-plan-"))
    (tmp / "content").mkdir()
    (tmp / "content" / "profile.json").write_text(
        json.dumps(profil or PROFIL, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, str(PLANIFICATEUR), "--config", str(CONFIG), *args],
                       cwd=tmp, capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(f"plan.py a échoué :\n{r.stderr}")
    return json.loads((tmp / "content" / "plan.json").read_text(encoding="utf-8"))


checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


plan = planifier()
lecons = plan["lecons"]
cibles = [l["quotas"]["caracteres_nouveaux"]["cible"] for l in lecons]

# ---------------------------------------------------------------- reproductible
ok("deux planifications du même livre sont identiques", planifier() == plan)

# ---------------------------------------------------------------- la courbe
ok("le plan reprend une leçon par titre du livre de référence", len(lecons) == 10)
ok("le vocabulaire nouveau décroît du début à la fin",
   sum(cibles[:3]) > 2 * sum(cibles[-3:]), f"{cibles[:3]} contre {cibles[-3:]}")
ok("rien ne se perd dans la répartition",
   sum(cibles) == plan["totaux"]["caracteres_nouveaux"],
   f"{sum(cibles)} contre {plan['totaux']['caracteres_nouveaux']}")
ok("chaque leçon a une bande autour de sa cible",
   all(l["quotas"]["caracteres_nouveaux"]["min"] <= l["quotas"]["caracteres_nouveaux"]["cible"]
       <= l["quotas"]["caracteres_nouveaux"]["max"] for l in lecons))

# ---------------------------------------------------------------- exercices
actifs = json.load(open(CONFIG))["types_exercices"]["actifs"]
compte = Counter(t for l in lecons for t in l["exercices"])
total = sum(compte.values())
ok("la répartition des exercices suit les parts observées",
   all(abs(compte.get(t, 0) / total - actifs[t]["part"]) < 0.05 for t in actifs),
   str(dict(compte)))
ok("aucun type n'est répété dans une même leçon",
   all(len(set(l["exercices"])) == len(l["exercices"]) for l in lecons),
   str([l["exercices"] for l in lecons if len(set(l["exercices"])) != len(l["exercices"])]))

rares = [t for t in actifs if actifs[t]["observes"] <= 2]
positions = [i for i, l in enumerate(lecons) if any(t in rares for t in l["exercices"])]
ok("les types rares sont étalés, pas groupés au début",
   not positions or max(positions) >= len(lecons) // 2,
   f"types rares en leçons {[p + 1 for p in positions]}")

# ---------------------------------------------------------------- autre longueur
court = planifier("--lecons", "5")
ok("un livre plus court garde une courbe décroissante",
   len(court["lecons"]) == 5
   and court["lecons"][0]["quotas"]["caracteres_nouveaux"]["cible"]
   > court["lecons"][-1]["quotas"]["caracteres_nouveaux"]["cible"])
long = planifier("--lecons", "20")
ok("un livre plus long aussi, et ses totaux suivent",
   len(long["lecons"]) == 20
   and long["totaux"]["caracteres_nouveaux"] > plan["totaux"]["caracteres_nouveaux"],
   str(long["totaux"]))

# ---------------------------------------------------------------- sujets fournis
tmp = Path(tempfile.mkdtemp(prefix="wb-sujets-"))
sujets = tmp / "sujets.txt"
sujets.write_text("SE PRÉSENTER\nCOMMANDER AU RESTAURANT\nDEMANDER SON CHEMIN\n", encoding="utf-8")
sur_mesure = planifier("--titres", str(sujets))
ok("une liste de sujets donne le plan correspondant",
   [l["titre"] for l in sur_mesure["lecons"]]
   == ["SE PRÉSENTER", "COMMANDER AU RESTAURANT", "DEMANDER SON CHEMIN"],
   str([l["titre"] for l in sur_mesure["lecons"]]))

rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
