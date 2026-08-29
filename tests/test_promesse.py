#!/usr/bin/env python3
"""Le critère de validation du projet, joué en entier à travers le serveur.

docs/NEXT_TASK.md le formule ainsi : « Le team manager dépose un manuscrit,
obtient le PDF, envoie un lien à un professeur qui n'a jamais vu l'outil ;
celui-ci traite sa file ; le manager recompile et les corrections sont dans le
livre. Sans ligne de commande. »

Chaque morceau était testé séparément — le rejeu des décisions, le dépôt, les
files — mais jamais la chaîne entière avec le vrai manuscrit et le vrai
pipeline. C'est pourtant la seule phrase qui dit si l'outil tient sa promesse.

Ignoré si le manuscrit de référence n'est pas là (il n'est pas versionné).

    python3 tests/test_promesse.py
"""
import json, os, shutil, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANUSCRIT = REPO / "input" / "742_CN10_FINAL_Manuscript.docx"

if not MANUSCRIT.exists():
    print("  manuscrit de référence absent — test ignoré")
    print("\n0/0 vérifications passées")
    sys.exit(0)

TMP = Path(tempfile.mkdtemp(prefix="wb-promesse-"))
os.environ["WB_DATA"] = str(TMP)
os.environ["WB_ADMIN_TOKEN"] = "jeton-de-test"
# Le pipeline appelle `python3` et `typst` : on s'assure qu'il trouve les nôtres.
os.environ["PATH"] = os.pathsep.join(
    [str(REPO / ".venv" / "bin"), str(REPO / ".bin"), os.environ.get("PATH", "")])
sys.path.insert(0, str(REPO / "server"))

from fastapi.testclient import TestClient                        # noqa: E402
import store, workspace, app as appmod                           # noqa: E402

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


store.init()
client = TestClient(appmod.app)
client.get("/a/jeton-de-test")                     # le manager ouvre son lien

# ---------------------------------------------------------------- 1. le dépôt
with open(MANUSCRIT, "rb") as f:
    r = client.post("/admin/projects", files={"file": (MANUSCRIT.name, f.read())},
                    data={"name": "CN10"})
ok("le manuscrit est accepté", r.status_code == 200, r.text[:200])
pid = r.json()["id"]
projet = client.get(f"/admin/projects/{pid}").json()
ok("le livre se construit sans ligne de commande", projet["status"] == "ready",
   f"{projet['status']} — {str(projet.get('log'))[-300:]}")
ok("le PDF est là",
   client.get(f"/admin/projects/{pid}/book.pdf").status_code == 200)
ok("les rapports aussi",
   client.get(f"/admin/projects/{pid}/reports/validation_report.txt").status_code == 200)

# ---------------------------------------------------------------- 2. le lien du professeur
lien = next(l["url"] for l in projet["links"] if l["role"] == "teacher")
jeton = lien.rsplit("/", 1)[1]
prof = TestClient(appmod.app)                      # un navigateur qui n'a rien vu
suite = prof.get(f"/r/{jeton}", follow_redirects=True)
ok("le professeur ouvre sa file depuis le lien seul", suite.status_code == 200,
   str(suite.status_code))

file_prof = prof.get(f"/p/{pid}/teacher/bundle.json")
ok("sa file lui est servie", file_prof.status_code == 200, file_prof.text[:150])
items = file_prof.json()["items"]
ok("elle ne contient que ses items",
   items and all(i["queue"] == "teacher" for i in items), str(len(items)))
ok("il ne voit pas les files des autres",
   prof.get(f"/p/{pid}/manager/bundle.json").status_code == 403)

# ---------------------------------------------------------------- 3. il tranche
item = items[0]
CORRECTION = "zhè shì yī gè test"
r = prof.post(f"/p/{pid}/teacher/decisions",
              json={"item_id": item["id"], "action": "fix",
                    "value": CORRECTION, "by": "professeur"})
ok("sa correction est enregistrée", r.status_code == 200, r.text[:150])
ok("elle lui est rendue s'il revient",
   prof.get(f"/p/{pid}/teacher/decisions").json().get(item["id"], {}).get("value")
   == CORRECTION)

# ---------------------------------------------------------------- 4. le manager recompile
avant = json.loads((workspace.workspace(pid) / "content" / "book.json")
                   .read_text(encoding="utf-8"))
ok("avant recompilation, le livre ne porte pas encore la correction",
   CORRECTION not in json.dumps(avant, ensure_ascii=False))

r = client.post(f"/admin/projects/{pid}/recompile")
ok("la recompilation part", r.status_code == 200, r.text[:150])
projet = client.get(f"/admin/projects/{pid}").json()
ok("et aboutit", projet["status"] == "ready",
   f"{projet['status']} — {str(projet.get('log'))[-300:]}")

apres = json.loads((workspace.workspace(pid) / "content" / "book.json")
                   .read_text(encoding="utf-8"))
ok("la correction du professeur est dans le livre",
   CORRECTION in json.dumps(apres, ensure_ascii=False),
   "introuvable dans content/book.json")

rapport = client.get(f"/admin/projects/{pid}/reports/decisions_report.txt")
ok("le rapport des décisions la mentionne",
   rapport.status_code == 200 and CORRECTION in rapport.text,
   rapport.text[-300:] if rapport.status_code == 200 else str(rapport.status_code))

# ---------------------------------------------------------------- 5. rien n'est perdu
ok("la décision survit à la recompilation",
   prof.get(f"/p/{pid}/teacher/decisions").json().get(item["id"], {}).get("value")
   == CORRECTION)
# L'identifiant d'un item est dérivé de son contenu. Une correction change ce
# contenu, donc l'identifiant : l'item revient dans la file en portant la
# prononciation que le professeur vient d'écrire. C'est voulu — bundle.py :
# « un contenu modifié fait réapparaître l'item comme non traité, c'est le sens
# sûr de l'erreur ». Ce qu'on vérifie, c'est donc qu'il voit bien SON texte, et
# pas un item fantôme portant l'ancien.
file2 = prof.get(f"/p/{pid}/teacher/bundle.json").json()["items"]
memes = [i for i in file2
         if i.get("zh") == item.get("zh") and i.get("lesson") == item.get("lesson")]
ok("une correction qui ne satisfait pas le contrôle revient dans la file",
   bool(memes), "l'item a disparu sans que la paire soit valide")
ok("et elle revient en portant le texte du professeur, pas l'ancien",
   memes and memes[0].get("pinyin") == CORRECTION,
   str([m.get("pinyin") for m in memes]))
ok("la file ne garde pas de doublon de l'ancien item",
   not any(i["id"] == item["id"] for i in file2))

shutil.rmtree(TMP, ignore_errors=True)
rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
