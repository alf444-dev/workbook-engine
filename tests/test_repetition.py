#!/usr/bin/env python3
"""Répétition d'une leçon à l'autre — ce que le modèle doit éviter, et ce que
le contrôle doit attraper.

La règle est calibrée sur le livre humain : aucune de ses leçons ne doit être
signalée (invariant 4). Une leçon qui recopie la prose d'une autre doit l'être.

    python3 tests/test_repetition.py
"""
import copy, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "pipeline"))
import repetition                                                # noqa: E402

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


def lecon(titre, paragraphes):
    return {"kind": "chapter", "num": 1, "title": titre,
            "blocks": [{"type": "para", "text": p} for p in paragraphes]}


A = lecon("A", [
    "You don't need to memorize every character before you start speaking with people.",
    "Take a look at how a simple greeting works in a shop, then try it yourself.",
    "The good news is that Chinese verbs never change their form for tense or person.",
])
B = lecon("B", [
    "You don't need to worry about gender or plurals when you build a sentence.",
    "Take a look at how numbers combine, and the pattern becomes obvious very fast.",
    "Once you know how to count to ten, everything up to ninety-nine follows naturally.",
])
C_neuve = lecon("C", [
    "Prices in China are usually shown on a small display at the counter.",
    "Most vendors will happily repeat a number if you ask them to say it again.",
    "Bargaining is common in markets but almost never in chain stores.",
])
C_recyclee = lecon("C", [
    "You don't need to memorize every character before you start speaking with people.",
    "Take a look at how a simple greeting works in a shop, then try it yourself.",
    "The good news is that Chinese verbs never change their form for tense or person.",
    "Prices in China are usually shown on a small display at the counter.",
])

# ------------------------------------------------- ce qu'on donne au modèle
deja = repetition.deja_employees([A, B])
ok("les débuts de paragraphe répétés sont relevés",
   "you don't need to" in deja["ouvertures"] and "take a look at" in deja["ouvertures"],
   str(deja["ouvertures"]))
ok("un début employé une seule fois ne l'est pas",
   "once you know how" not in deja["ouvertures"], str(deja["ouvertures"]))
ok("les suites de mots communes à deux leçons sont relevées",
   "take a look at how" in deja["tournures"], str(deja["tournures"]))
ok("une suite qui diverge au cinquième mot n'est pas une répétition",
   not any(t.startswith("you don't need to") for t in deja["tournures"]), str(deja["tournures"]))
ok("sans leçon précédente, rien à éviter et le prompt n'en parle pas",
   repetition.deja_employees([]) == {"tournures": [], "ouvertures": []}
   and repetition.formuler(repetition.deja_employees([])) == "")
bloc = repetition.formuler(deja)
ok("le bloc de prompt nomme la plainte et liste les débuts",
   "répétitif" in bloc and "« you don't need to… »" in bloc, bloc[:200])

# ------------------------------------------------- ce qu'on mesure après
ok("une leçon neuve ne reprend rien", repetition.part_reprise(C_neuve, [A, B]) == 0.0)
part = repetition.part_reprise(C_recyclee, [A, B])
ok("une leçon qui recopie trois paragraphes sur quatre est massivement reprise",
   part > 0.6, f"{part:.1%}")
ok("la première leçon d'un livre ne reprend rien", repetition.part_reprise(A, []) == 0.0)

# ------------------------------------------------- le seuil, sur le livre humain
livre = REPO / "content" / "book_typed.json"
if livre.exists():
    book = json.loads(livre.read_text(encoding="utf-8"))
    lecture = [c for c in book["chapters"] if c["kind"] in ("chapter", "story")]
    seuil, pire = repetition.seuil_du_livre(lecture)
    ok("le seuil vient du livre, avec 20 % de marge", abs(seuil - round(pire * 1.2, 4)) < 1e-9,
       f"seuil {seuil}, pire {pire}")
    ok("le livre humain ne dépasse jamais son propre seuil",
       all(repetition.part_reprise(ch, lecture[:i]) <= seuil for i, ch in enumerate(lecture)))
    ok("le seuil reste bas : la prose humaine se répète peu d'une leçon à l'autre",
       seuil < 0.15, f"{seuil:.1%}")
    ok("les en-têtes de tableaux ne comptent pas comme répétition",
       all("what they mean" not in t for t in
           repetition.deja_employees(lecture[:10])["tournures"]))
else:
    print("  (livre de référence absent : seuil non vérifié — lancer ./run.sh)")

# ------------------------------------------------- bilan
for nom, cond, detail in checks:
    print(f"  {'✓' if cond else '✗'} {nom}" + (f"   — {detail}" if not cond and detail else ""))
n_ok = sum(1 for _, c, _ in checks if c)
print(f"\n{n_ok}/{len(checks)} vérifications passées")
sys.exit(0 if n_ok == len(checks) else 1)
