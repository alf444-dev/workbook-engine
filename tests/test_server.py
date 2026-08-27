#!/usr/bin/env python3
"""Vérifie ce qui protège les manuscrits et les décisions.

Sans comptes, c'est le lien qui fait l'autorisation : ces propriétés-là sont
tout ce qui empêche un professeur externe de voir le reste du livre, et une
décision de disparaître. Elles ne doivent pas pouvoir régresser en silence.

    python3 tests/test_server.py
"""
import json, os, shutil, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="wb-test-"))
os.environ["WB_DATA"] = str(TMP)                  # avant l'import : store lit l'env
sys.path.insert(0, str(REPO / "server"))

from fastapi.testclient import TestClient         # noqa: E402
import store, workspace, app as appmod            # noqa: E402

REVIEW = {
    "project": "Essai", "source": "essai.docx", "id_scheme": 1,
    "stats": {"lessons": 1, "blocks": 1, "exercises": 1, "pairs_checked": 3},
    "lessons": [{"id": 0, "title": "Leçon", "kind": "chapter", "section": "—"}],
    "items": [
        {"id": "pinyin-aaa", "kind": "pinyin", "queue": "teacher", "lesson": "Leçon",
         "lesson_id": 0, "title": "你好", "detail": "…", "target": None},
        {"id": "exercise-bbb", "kind": "exercise", "queue": "editor", "lesson": "Leçon",
         "lesson_id": 0, "title": "Ex", "detail": "…", "target": None},
        {"id": "answerkey-ccc", "kind": "answerkey", "queue": "manager", "lesson": "Leçon",
         "lesson_id": 0, "title": "AK", "detail": "…", "target": None},
    ],
}

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))

store.init()
pid = store.create_project("Essai", "essai.docx")
ws = workspace.workspace(pid)
(ws / "output").mkdir(parents=True, exist_ok=True)
(ws / "output" / "review.json").write_text(json.dumps(REVIEW, ensure_ascii=False), encoding="utf-8")
(ws / "output" / "book.pdf").write_bytes(b"%PDF-1.7\n")
jetons = {l["role"]: l["token"] for l in store.links_for(pid)}

client = TestClient(appmod.app)

# ---------------------------------------------------------------- le lien fait l'autorisation
ok("sans lien, la console est refusée",
   client.get(f"/p/{pid}/teacher/", follow_redirects=False).status_code == 403)
ok("un jeton inventé est refusé", client.get("/r/nimportequoi").status_code == 404)
ok("le site se déclare non indexable",
   "Disallow: /" in client.get("/robots.txt").text
   and "noindex" in client.get("/robots.txt").headers.get("X-Robots-Tag", ""))
ok("aucune fuite par le Referer",
   client.get("/robots.txt").headers.get("Referrer-Policy") == "no-referrer")

r = client.get(f"/r/{jetons['teacher']}", follow_redirects=False)
ok("le lien redirige vers une URL qui ne contient plus le jeton",
   r.status_code == 303 and jetons["teacher"] not in r.headers["location"],
   r.headers.get("location", ""))
client.get(f"/r/{jetons['teacher']}")            # pose le cookie dans le client

# ---------------------------------------------------------------- cloisonnement des files
b = client.get(f"/p/{pid}/teacher/bundle.json").json()
ok("le professeur ne reçoit que sa file",
   [i["id"] for i in b["items"]] == ["pinyin-aaa"] and b["role"] == "teacher",
   str([i["id"] for i in b["items"]]))
ok("le professeur n'atteint pas le livre complet",
   client.get(f"/p/{pid}/teacher/book.pdf").status_code == 403)
ok("le professeur ne peut pas trancher un item du manager",
   client.post(f"/p/{pid}/teacher/decisions",
               json={"item_id": "answerkey-ccc", "action": "ok"}).status_code == 404)
ok("un cookie de professeur n'ouvre pas la file de l'éditeur",
   client.get(f"/p/{pid}/editor/bundle.json").status_code == 403)

# ---------------------------------------------------------------- journal des décisions
client.post(f"/p/{pid}/teacher/decisions",
            json={"item_id": "pinyin-aaa", "action": "ok", "by": "Wei"})
client.post(f"/p/{pid}/teacher/decisions",
            json={"item_id": "pinyin-aaa", "action": "fix", "value": "nǐ hǎo", "by": "Ling"})
courant = client.get(f"/p/{pid}/teacher/decisions").json()
ok("l'état courant d'un item est sa dernière décision",
   courant["pinyin-aaa"]["action"] == "fix" and courant["pinyin-aaa"]["by"] == "Ling",
   str(courant))
ok("rien n'est écrasé : les deux décisions sont au journal",
   len(store.history(pid, "pinyin-aaa")) == 2)
ok("une action inconnue est refusée",
   client.post(f"/p/{pid}/teacher/decisions",
               json={"item_id": "pinyin-aaa", "action": "supprimer"}).status_code == 400)

# ---------------------------------------------------------------- révocation
store.revoke(jetons["teacher"])
ok("un lien révoqué ne donne plus rien",
   client.get(f"/p/{pid}/teacher/bundle.json").status_code == 403)
ok("les décisions déjà prises survivent à la révocation",
   len(store.current(pid)) == 1)

shutil.rmtree(TMP, ignore_errors=True)
rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
