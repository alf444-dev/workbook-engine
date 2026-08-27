#!/usr/bin/env python3
"""Vérifie que les identifiants d'items survivent à une recompilation.

Les décisions des relecteurs sont stockées côté serveur sous l'id de l'item.
Un id instable ferait pointer une décision vers un autre contenu, sans erreur
visible. Ce test fige la propriété : même contenu ⇒ même id, contenu modifié ⇒
id différent, et jamais l'inverse.

    python3 tests/test_bundle_ids.py
"""
import copy, json, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parent.parent
BUNDLE = REPO / "pipeline" / "bundle.py"

from fixture_book import BOOK, FAUTIF, PAIRES_ATTENDUES

def compile_bundle(book):
    """Lance bundle.py sur un manuscrit, dans un répertoire neuf."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "content").mkdir()
        (tmp / "content" / "book_typed.json").write_text(
            json.dumps(book, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, str(BUNDLE)], cwd=tmp,
                           capture_output=True, text=True)
        if r.returncode:
            raise AssertionError(f"bundle.py a échoué :\n{r.stderr}")
        return json.loads((tmp / "output" / "review.json").read_text(encoding="utf-8"))


def resolve(book, target):
    """Suit une adresse d'item jusqu'au texte visé — ce que fera l'application
    des décisions à content/book.json."""
    node = book
    for step in target["path"]:
        node = node[step]
    if target["field"] is None:
        return node
    return node[target["field"]]


def ids(bundle, kind=None):
    return [i["id"] for i in bundle["items"] if kind is None or i["kind"] == kind]


checks = []

def ok(nom, condition, detail=""):
    checks.append((nom, bool(condition), detail))


# ---------------------------------------------------------------- 1. déterminisme
a, b = compile_bundle(BOOK), compile_bundle(BOOK)
ok("deux compilations du même manuscrit donnent les mêmes ids", ids(a) == ids(b),
   f"{ids(a)}\n    vs {ids(b)}")
ok("les ids ne sont pas positionnels",
   all(not i["id"].split("-")[-1].isdigit() or len(i["id"].split("-")[1]) == 10
       for i in a["items"]))

# ------------------------------------------------- 2. un chapitre inséré en tête
decale = copy.deepcopy(BOOK)
decale["chapters"].insert(0, {"kind": "section", "num": 0, "title": "PREFACE", "blocks": []})
c = compile_bundle(decale)
ok("un chapitre inséré avant ne change aucun id", ids(a) == ids(c),
   f"{ids(a)}\n    vs {ids(c)}")
ok("...mais les adresses, elles, suivent le décalage",
   [i["target"]["path"] for i in a["items"] if i["target"]]
   != [i["target"]["path"] for i in c["items"] if i["target"]])

# ------------------------------------------------- 3. un contenu modifié
edite = copy.deepcopy(BOOK)
edite["chapters"][1]["blocks"][1]["text"] = "Wrong: {zh:你的老师呢？} {py:Nǐ shi?} here."
d = compile_bundle(edite)
avant, apres = set(ids(a)), set(ids(d))
ok("modifier une prononciation ne change que l'id de cet item",
   len(avant - apres) == 1 and len(apres - avant) == 1,
   f"disparus {sorted(avant - apres)}, apparus {sorted(apres - avant)}")

# ------------------------------------------------- 4. doublons
ok("un doublon exact reçoit un id distinct",
   len(set(ids(a))) == len(ids(a)),
   f"{len(ids(a))} items, {len(set(ids(a)))} ids")
ok("les deux exemplaires du doublon partagent le même préfixe",
   sum(1 for i in ids(a, "pinyin") if i.endswith("-2")) == 1, str(ids(a, "pinyin")))

# ------------------------------------------------- 5. les adresses retombent juste
for it in a["items"]:
    if not it["target"]:
        continue
    trouve = resolve(BOOK, it["target"])
    if it["kind"] == "pinyin":
        ok(f"adresse résolue — {it['title']}", it["pinyin"] in str(trouve),
            f"{it['target']} → {str(trouve)[:80]!r}")
    else:
        ok(f"adresse résolue — {it['title']}", trouve.get("type") == "exercise",
            f"{it['target']} → {str(trouve)[:80]!r}")
ok("les items d'answer key n'ont pas d'adresse",
   all(i["target"] is None for i in a["items"] if i["kind"] == "answerkey"))

# ------------------------------------------------- 6. statistiques honnêtes
ok("les paires vérifiées sont comptées, pas codées en dur",
   a["stats"]["pairs_checked"] == PAIRES_ATTENDUES,
   f"{a['stats']['pairs_checked']} au lieu de {PAIRES_ATTENDUES}")
ok("le nom du projet est dérivé du manuscrit",
   a["project"] == "Learn Chinese", a["project"])
ok("le schéma d'id est versionné dans le bundle", a.get("id_scheme") == 1)

# ---------------------------------------------------------------- verdict
rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
