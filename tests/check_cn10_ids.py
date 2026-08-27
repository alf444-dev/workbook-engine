#!/usr/bin/env python3
"""Test d'acceptation sur le manuscrit réel — à lancer après ./run.sh.

Vérifie sur le CN10 entier ce que tests/test_bundle_ids.py vérifie sur un
manuscrit d'essai : ids uniques, stables d'une compilation à l'autre, et
adresses qui retombent sur le bon contenu dans content/book.json.

    python3 tests/check_cn10_ids.py
"""
import json, subprocess, sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REVIEW = REPO / "output" / "review.json"
BOOK = REPO / "content" / "book.json"

if not REVIEW.exists() or not BOOK.exists():
    sys.exit("lancer ./run.sh d'abord")

def compile_bundle():
    r = subprocess.run([sys.executable, "pipeline/bundle.py"], cwd=REPO,
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"bundle.py a échoué :\n{r.stderr}")
    return REVIEW.read_bytes()

# on recompile d'abord, pour ne pas mesurer un review.json périmé
avant = compile_bundle()
bundle = json.loads(avant.decode("utf-8"))
book = json.loads(BOOK.read_text(encoding="utf-8"))
items = bundle["items"]

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))

# 1. unicité sur le volume réel
ids = [i["id"] for i in items]
doublons = [k for k, n in Counter(ids).items() if n > 1]
ok(f"{len(ids)} ids tous distincts", not doublons, str(doublons))

# 2. stabilité : on recompile le bundle et on compare
apres_octets = compile_bundle()
apres = json.loads(apres_octets.decode("utf-8"))
ok("recompiler le bundle ne change aucun id",
   [i["id"] for i in apres["items"]] == ids,
   f"{len(set(ids) ^ {i['id'] for i in apres['items']})} ids divergents")
ok("le bundle est reproductible octet pour octet", apres_octets == avant)

# 3. les adresses retombent sur le bon contenu de book.json
def conteneur(target):
    """Suit `path` jusqu'à l'objet qui porte le texte visé."""
    node = book
    for step in target["path"]:
        node = node[step]
    return node

rates = 0
exemples = []
for it in items:
    t = it.get("target")
    if not t:
        continue
    try:
        node = conteneur(t)
        if it["kind"] != "pinyin":
            bon = isinstance(node, dict) and node.get("type") == "exercise"
        elif t["field"] == "pinyin":
            # ligne de dialogue : écriture et prononciation sont deux champs
            bon = node.get("zh") == it["zh"] and node.get("pinyin") == it["pinyin"]
        else:
            # paragraphe ou cellule de tableau : la paire est dans le texte
            texte = node[t["field"]]
            bon = it["zh"] in texte and it["pinyin"] in texte
    except (KeyError, IndexError, TypeError) as e:
        bon, node = False, f"{type(e).__name__} sur {t['path']}"
    if not bon:
        rates += 1
        exemples.append(f"{it['id']} ({it['kind']}, field={t['field']!r}) → {str(node)[:70]!r}")

avec_adresse = sum(1 for i in items if i.get("target"))
ok(f"{avec_adresse} adresses résolues dans content/book.json sans exception",
   rates == 0, "\n      ".join(exemples[:5]))

# 4. couverture : qui a une adresse, qui n'en a pas
sans = Counter(i["kind"] for i in items if not i.get("target"))
ok("seuls les items d'answer key sont sans adresse",
   set(sans) <= {"answerkey"}, str(dict(sans)))

for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\nfiles : {bundle['queues']}   paires vérifiées : {bundle['stats']['pairs_checked']}")
rates_ = [c for c in checks if not c[1]]
print(f"{len(checks) - len(rates_)}/{len(checks)} vérifications passées")
sys.exit(1 if rates_ else 0)
