#!/usr/bin/env python3
"""La mesure de voix : calibrée sur l'humain, capable de détecter le robotique.

Le résultat du 2 septembre — aucune leçon générée signalée — ne vaut que si
l'instrument sait signaler. On le vérifie dans les deux sens : le livre humain
passe entier, et une leçon écrite exprès comme un modèle sans consigne (phrases
uniformes, tics, listes de trois, rafales) est signalée sur plusieurs signaux.

    python3 tests/test_voix.py
"""
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "pipeline"))
import voix                                                      # noqa: E402

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


BOOK = json.loads((REPO / "content" / "book_typed.json").read_text(encoding="utf-8")) \
    if (REPO / "content" / "book_typed.json").exists() else None
if BOOK is None:
    print("  livre de référence absent — test ignoré")
    print("\n0/0 vérifications passées")
    sys.exit(0)

seuils = voix.bandes(BOOK)
ok("une bande existe pour chaque signal", set(seuils) == set(voix.SIGNAUX),
   str(sorted(seuils)))
ok("le rythme est un plancher, pas un plafond — un modèle est trop régulier",
   "rythme" in voix.PLANCHERS)

humaines = [c for c in BOOK["chapters"] if c["kind"] == "chapter"]
signalees = [c["title"] for c in humaines if voix.verifier(c, seuils)]
ok("aucune leçon humaine n'est signalée (invariant 4)", not signalees,
   str(signalees[:3]))

# ---------------------------------------------------------------- le robot type
# Vingt phrases de longueur quasi identique, ouvertes pareil, truffées de tics.
phrase = ("It's worth noting that this simple approach will truly help you "
          "learn quickly, easily, and effectively. ")
ROBOT = {"kind": "chapter", "num": 99, "title": "ROBOTIQUE", "blocks": [
    {"type": "para", "text": phrase * 10},
    {"type": "para", "text":
        "Let's dive in. Whether you're a beginner, a traveler, or a student, "
        "this lesson is a testament to simple learning. It's important to note "
        "that practice truly matters. " * 4},
]}
d = voix.verifier(ROBOT, seuils)
ok("une leçon robotique est signalée", bool(d), "l'instrument ne détecte rien")
ok("sur au moins deux signaux", len(d) >= 2,
   str([(s, v) for s, v, *_ in d]))
signaux_touches = {s for s, *_ in d}
ok("dont les tics", "tics" in signaux_touches, str(signaux_touches))
# Pas d'assertion sur le rythme : le texte synthétique mêle des phrases de
# seize mots et « Let's dive in. », son écart-type est donc élevé. Le plancher
# se vérifie à part, sur un texte réellement uniforme.
UNIFORME = {"kind": "chapter", "num": 98, "title": "UNIFORME", "blocks": [
    {"type": "para", "text":
        "This lesson will help you learn the words you need every day. " * 20}]}
d2 = voix.verifier(UNIFORME, seuils)
ok("des phrases toutes identiques tombent sous le plancher de rythme",
   any(s == "rythme" and sens == "sous" for s, v, b, sens in d2),
   str(d2))

# ---------------------------------------------------------------- robustesse
ok("une leçon trop courte n'est pas notée — un ratio sur rien ne veut rien dire",
   voix.mesurer({"kind": "chapter", "blocks": [
       {"type": "para", "text": "Short. Very short."}]}) is None)
m = voix.mesurer(humaines[0])
ok("l'écriture cible ne pollue pas la mesure anglaise",
   m is not None and m["_mots"] > 100)
ok("les mesures sont stables d'une exécution à l'autre",
   voix.mesurer(humaines[0]) == m)

rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
