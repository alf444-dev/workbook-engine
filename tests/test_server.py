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

# ---------------------------------------------------------------- schéma d'identifiants
# `id_scheme` était écrit dans chaque file et lu par personne : changer le calcul
# aurait fait réapparaître comme neufs des items déjà tranchés, en silence.
import importlib.util as _iu2                                    # noqa: E402
_spec = _iu2.spec_from_file_location("ids_test", REPO / "pipeline" / "ids.py")
_ids = _iu2.module_from_spec(_spec); _spec.loader.exec_module(_ids)

vieux = store.create_project("Ancien schéma", "x.docx")
ws_v = workspace.workspace(vieux) / "output"
ws_v.mkdir(parents=True, exist_ok=True)


def poser_bundle(schema):
    (ws_v / "review.json").write_text(json.dumps({
        "project": "x", "source": "x.docx", "id_scheme": schema,
        "stats": {"lessons": 0, "blocks": 0, "exercises": 0, "pairs_checked": 0},
        "lessons": [], "items": []}), encoding="utf-8")


jeton_v = next(l["token"] for l in store.links_for(vieux) if l["role"] == "teacher")
cv = TestClient(appmod.app)
cv.get(f"/r/{jeton_v}", follow_redirects=True)

poser_bundle(_ids.ID_SCHEME)
ok("un livre au schéma courant n'est pas signalé",
   cv.get(f"/p/{vieux}/teacher/bundle.json").json()["ids_perimes"] is False)

poser_bundle(_ids.ID_SCHEME - 1)
ok("un livre construit sous un ancien schéma est signalé",
   cv.get(f"/p/{vieux}/teacher/bundle.json").json()["ids_perimes"] is True)

poser_bundle(None)
ok("une file sans schéma déclaré l'est aussi",
   cv.get(f"/p/{vieux}/teacher/bundle.json").json()["ids_perimes"] is True)

# ---------------------------------------------------------------- livre pas encore prêt
# La page de relecture distingue trois cas d'après ce corps de réponse : il doit
# donc porter l'état, pas seulement l'étape.
attente = store.create_project("Pas prêt", "x.docx")
store.set_status(attente, "running", step="3/7  typing exercises and linking answers")
jeton_att = next(l["token"] for l in store.links_for(attente) if l["role"] == "teacher")
ca = TestClient(appmod.app)
ca.get(f"/r/{jeton_att}", follow_redirects=True)
r_att = ca.get(f"/p/{attente}/teacher/bundle.json")
ok("un livre pas encore compilé répond 503", r_att.status_code == 503, str(r_att.status_code))
ok("et dit où il en est", r_att.json().get("step", "").startswith("3/7"), r_att.text[:120])
ok("et dans quel état il est", r_att.json().get("status") == "running", r_att.text[:120])

store.set_status(attente, "failed", log="boum")
r_ech = ca.get(f"/p/{attente}/teacher/bundle.json")
ok("un livre en échec le dit aussi", r_ech.json().get("status") == "failed",
   r_ech.text[:120])

# ---------------------------------------------------------------- secrets au journal
faux = "sk-ant-api03-" + "A" * 40
masque = store.masquer_secrets(f"Illegal header value b'{faux}\\n'")
ok("une clé qui traîne dans un traceback est masquée avant d'être écrite",
   faux not in masque and "[masqué]" in masque, masque)
ok("le reste du message est conservé", "Illegal header value" in masque, masque)
ok("un journal sans secret n'est pas touché",
   store.masquer_secrets("2 leçons écrites") == "2 leçons écrites")
ok("un journal vide ne casse rien", store.masquer_secrets(None) is None)

# Un secret déjà écrit avant que le masquage existe doit être retiré aussi.
pid_sale = store.create_project("fuite", "manuscrit.docx")
with store.connect() as cx:
    cx.execute("UPDATE projects SET log=? WHERE id=?", (f"clé {faux} visible", pid_sale))
ok("le nettoyage retrouve un secret déjà en base", store.nettoyer_secrets() == 1)
ok("et la clé n'est plus lisible",
   faux not in (store.get_project(pid_sale)["log"] or ""),
   store.get_project(pid_sale)["log"])
ok("un second passage ne trouve plus rien", store.nettoyer_secrets() == 0)

# ---------------------------------------------------------------- version en ligne
os.environ["RENDER_GIT_COMMIT"] = "0123456789abcdef"
import importlib                                                 # noqa: E402
importlib.reload(appmod)
c2 = TestClient(appmod.app)
ok("la réponse dit quelle version tourne",
   c2.get("/robots.txt").headers.get("X-Workbook-Version") == "0123456",
   str(dict(c2.get("/robots.txt").headers)))
os.environ.pop("RENDER_GIT_COMMIT")
importlib.reload(appmod)
ok("hors Render, aucun en-tête de version",
   "X-Workbook-Version" not in TestClient(appmod.app).get("/robots.txt").headers)

shutil.rmtree(TMP, ignore_errors=True)
# ---------------------------------------------------------------- accueil et refus
r = client.get("/", headers={"accept": "text/html"})
ok("la racine explique au lieu de renvoyer une erreur",
   r.status_code == 200 and "private link" in r.text, str(r.status_code))
ok("elle ne révèle rien", "admin" not in r.text.lower() and "token" not in r.text.lower())

r = client.get(f"/p/{pid}/manager/", headers={"accept": "text/html"})
ok("un navigateur reçoit une page lisible, pas du JSON",
   r.status_code == 403 and "<h1>" in r.text and "no longer works" in r.text,
   r.text[:80])
r = client.get(f"/p/{pid}/manager/bundle.json", headers={"accept": "application/json"})
ok("un programme reçoit toujours du JSON",
   r.status_code == 403 and r.headers["content-type"].startswith("application/json"),
   r.headers.get("content-type", ""))
ok("le site reste non indexable sur la racine",
   "noindex" in client.get("/").headers.get("X-Robots-Tag", ""))

rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
