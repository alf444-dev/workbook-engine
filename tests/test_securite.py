#!/usr/bin/env python3
"""Ce qui protège les manuscrits, vérifié route par route.

Les manuscrits ne sont pas publics et il n'y a pas de comptes : tout repose sur
des liens non devinables et sur le fait que **chaque** point d'entrée vérifie le
lien avant de répondre. Un seul oubli ouvre le dossier entier.

Ce fichier n'écrit donc pas une liste de cas à la main : il **énumère les routes
déclarées par le serveur** et exige que chacune refuse un visiteur sans lien.
Une route ajoutée demain sans garde-fou fera échouer ce test sans que personne
ait à y penser.

    python3 tests/test_securite.py
"""
import io, json, os, shutil, sys, tempfile, zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="wb-sec-"))
os.environ["WB_DATA"] = str(TMP)
os.environ["WB_ADMIN_TOKEN"] = "jeton-du-manager"
sys.path.insert(0, str(REPO / "server"))

from fastapi.testclient import TestClient                        # noqa: E402
import store, workspace, app as appmod                           # noqa: E402

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


store.init()
manager = TestClient(appmod.app)
manager.get("/a/jeton-du-manager")
anonyme = TestClient(appmod.app)


def faux_docx():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w:document/>")
    return buf.getvalue()


# Deux projets : on vérifiera qu'un lien de l'un n'ouvre pas l'autre.
un = store.create_project("Projet un", "un.docx")
deux = store.create_project("Projet deux", "deux.docx")
for pid in (un, deux):
    ws = workspace.workspace(pid)
    (ws / "output").mkdir(parents=True, exist_ok=True)
    (ws / "output" / "review.json").write_text(json.dumps({
        "project": pid, "source": "x.docx", "id_scheme": 1,
        "stats": {"lessons": 0, "blocks": 0, "exercises": 0, "pairs_checked": 0},
        "lessons": [], "items": [
            {"id": f"pinyin-{pid}", "kind": "pinyin", "queue": "teacher",
             "lesson": "L1", "lesson_id": "l1", "title": "你好",
             "detail": "d", "target": None, "zh": "你好", "pinyin": "x"},
            {"id": f"ans-{pid}", "kind": "answers", "queue": "manager",
             "lesson": "L1", "lesson_id": "l1", "title": "T",
             "detail": "d", "target": None}]}), encoding="utf-8")
    (ws / "output" / "book.pdf").write_bytes(b"%PDF-1.7\n")
    (ws / "validation_report.txt").write_text("rapport", encoding="utf-8")

jetons = {p["role"]: p["token"] for p in store.links_for(un)}
jetons_deux = {p["role"]: p["token"] for p in store.links_for(deux)}

# ---------------------------------------------------------------- 1. toutes les routes
def chemin_concret(gabarit, pid, role="teacher"):
    return (gabarit.replace("{pid}", pid).replace("{role}", role)
            .replace("{token}", "inconnu").replace("{nom}", "validation_report.txt")
            .replace("{n}", "1").replace("{path:path}", "console.html"))


admin, relecture, libres = [], [], []
for route in appmod.app.routes:
    chemin = getattr(route, "path", "")
    methodes = getattr(route, "methods", set()) or set()
    for m in sorted(methodes & {"GET", "POST"}):
        if chemin.startswith("/admin"):
            admin.append((m, chemin))
        elif chemin.startswith("/p/"):
            relecture.append((m, chemin))
        else:
            libres.append((m, chemin))

ok("le serveur expose bien des routes d'administration", len(admin) >= 10, str(len(admin)))
ok("et des routes de relecture", len(relecture) >= 4, str(len(relecture)))

ouvertes = []
for m, gabarit in admin:
    url = chemin_concret(gabarit, un)
    r = anonyme.request(m, url)
    if r.status_code not in (401, 403, 404, 405, 422):
        ouvertes.append(f"{m} {url} → {r.status_code}")
ok("aucune route d'administration ne répond sans le lien du manager",
   not ouvertes, "\n      ".join(ouvertes[:6]))

ouvertes = []
for m, gabarit in relecture:
    url = chemin_concret(gabarit, un)
    r = anonyme.request(m, url, json={} if m == "POST" else None)
    if r.status_code not in (401, 403, 404, 405, 422):
        ouvertes.append(f"{m} {url} → {r.status_code}")
ok("aucune file de relecture ne s'ouvre sans lien",
   not ouvertes, "\n      ".join(ouvertes[:6]))

# ---------------------------------------------------------------- 2. cloisonnement
prof = TestClient(appmod.app)
prof.get(f"/r/{jetons['teacher']}", follow_redirects=True)
ok("le professeur ouvre sa file",
   prof.get(f"/p/{un}/teacher/bundle.json").status_code == 200)
ok("il ne voit pas la file du manager",
   prof.get(f"/p/{un}/manager/bundle.json").status_code == 403)
ok("il n'écrit pas dans la file du manager",
   prof.post(f"/p/{un}/manager/decisions",
             json={"item_id": f"ans-{un}", "action": "ok"}).status_code == 403)
ok("il n'atteint pas l'autre projet",
   prof.get(f"/p/{deux}/teacher/bundle.json").status_code == 403)
ok("il n'atteint pas les rapports, réservés au manager",
   prof.get(f"/p/{un}/manager/reports/validation_report.txt").status_code == 403)
ok("il n'atteint pas l'administration",
   prof.get("/admin/projects").status_code == 403)

# Un jeton d'un autre projet ne donne pas accès à celui-ci.
autre = TestClient(appmod.app)
autre.get(f"/r/{jetons_deux['teacher']}", follow_redirects=True)
ok("le lien d'un autre projet n'ouvre pas celui-ci",
   autre.get(f"/p/{un}/teacher/bundle.json").status_code == 403)

# ---------------------------------------------------------------- 3. révocation
ancien = jetons["teacher"]
manager.post(f"/admin/projects/{un}/rotate/teacher")
perime = TestClient(appmod.app)
ok("un lien révoqué ne s'échange plus contre un accès",
   perime.get(f"/r/{ancien}", follow_redirects=True).status_code in (403, 404))
ok("et le cookie déjà obtenu ne survit pas à la révocation",
   prof.get(f"/p/{un}/teacher/bundle.json").status_code == 403)

# ---------------------------------------------------------------- 4. entrées hostiles
r = manager.post("/admin/projects", files={"file": ("a.txt", b"pas un docx")})
ok("un fichier qui n'est pas un .docx est refusé", r.status_code == 400, r.text[:120])
r = manager.post("/admin/projects", files={"file": ("vide.docx", b"")})
ok("un .docx vide est refusé", r.status_code == 400, r.text[:120])
r = manager.post("/admin/projects", files={"file": ("faux.docx", b"PK\x03\x04rien")})
ok("un zip qui n'est pas un document Word est refusé", r.status_code == 400,
   r.text[:120])

r = manager.post("/admin/projects",
                 files={"file": ("../../evade.docx", faux_docx())},
                 data={"name": "traversée"})
ok("un nom de fichier qui remonte est accepté sans écrire hors de l'espace",
   r.status_code == 200, r.text[:120])
if r.status_code == 200:
    pid3 = r.json()["id"]
    depots = list((workspace.workspace(pid3) / "input").glob("*"))
    ok("le fichier atterrit bien dans l'espace du projet",
       depots and all(workspace.workspace(pid3) in d.parents for d in depots),
       str(depots))
    ok("et rien n'a été écrit à côté", not (TMP / "evade.docx").exists())

# décisions mal formées
prof2 = TestClient(appmod.app)
prof2.get(f"/r/{store.links_for(un)[0]['token']}", follow_redirects=True)
jeton_prof = next(l["token"] for l in store.links_for(un) if l["role"] == "teacher")
prof2 = TestClient(appmod.app)
prof2.get(f"/r/{jeton_prof}", follow_redirects=True)
ok("une action inconnue est refusée",
   prof2.post(f"/p/{un}/teacher/decisions",
              json={"item_id": f"pinyin-{un}", "action": "supprimer"}).status_code == 400)
ok("un item qui n'est pas dans la file est refusé",
   prof2.post(f"/p/{un}/teacher/decisions",
              json={"item_id": "inexistant", "action": "ok"}).status_code == 404)
ok("un item de la file d'un autre rôle est refusé",
   prof2.post(f"/p/{un}/teacher/decisions",
              json={"item_id": f"ans-{un}", "action": "ok"}).status_code == 404)
r = prof2.post(f"/p/{un}/teacher/decisions",
               json={"item_id": f"pinyin-{un}", "action": "fix", "value": "z" * 9000,
                     "by": "b" * 500})
ok("une valeur démesurée est acceptée mais tronquée", r.status_code == 200, r.text[:120])
enregistre = prof2.get(f"/p/{un}/teacher/decisions").json().get(f"pinyin-{un}", {})
ok("la valeur est bornée en base", len(enregistre.get("value", "")) <= 2000,
   str(len(enregistre.get("value", ""))))
ok("le nom du relecteur aussi", len(enregistre.get("by", "")) <= 80,
   str(len(enregistre.get("by", ""))))

# ---------------------------------------------------------------- 5. discrétion
r = anonyme.get("/")
ok("la racine ne révèle aucun projet",
   un not in r.text and "Projet un" not in r.text, r.text[:200])
ok("le site demande à ne pas être indexé",
   "noindex" in r.headers.get("X-Robots-Tag", ""), str(dict(r.headers)))
ok("et ne fuit pas par le Referer",
   r.headers.get("Referrer-Policy") == "no-referrer")
ok("robots.txt interdit tout", "Disallow: /" in anonyme.get("/robots.txt").text)

r = anonyme.get(f"/p/{un}/teacher/bundle.json")
ok("un refus ne dit pas si le projet existe",
   "Projet un" not in r.text and un not in r.text, r.text[:200])
r = anonyme.get("/r/jeton-inventé", follow_redirects=True)
ok("un lien inventé ne révèle rien",
   r.status_code in (403, 404) and "Projet" not in r.text, r.text[:200])

shutil.rmtree(TMP, ignore_errors=True)
# ---------------------------------------------------------------- en-têtes et bombes
r = anonyme.get("/robots.txt")
ok("les pages refusent d'être encadrées ailleurs",
   r.headers.get("X-Frame-Options") == "DENY"
   and "frame-ancestors 'none'" in r.headers.get("Content-Security-Policy", ""))
ok("la politique de contenu n'autorise que les polices de Google à l'extérieur",
   "fonts.gstatic.com" in r.headers.get("Content-Security-Policy", "")
   and "connect-src 'self'" in r.headers.get("Content-Security-Policy", ""))

import io, zipfile, tempfile
with tempfile.TemporaryDirectory() as tmp:
    # la taille reçue ne protège pas, seule la taille dépliée compte
    chemin = Path(tmp) / "bombe.docx"
    with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", b"<w:document/>")
        z.writestr("word/media/x.bin", b"\0" * (4 * 1024 * 1024))
    import workspace as ws
    borne = ws.DECOMPRESSE_MAX
    ws.DECOMPRESSE_MAX = 1024          # la même règle, avec une borne minuscule
    try:
        ok("un .docx dont la taille dépliée dépasse la borne est refusé", not ws.est_docx(chemin))
    finally:
        ws.DECOMPRESSE_MAX = borne
    ok("la borne réelle laisse passer un manuscrit avec ses images", ws.est_docx(chemin))
    sain = Path(tmp) / "sain.docx"
    with zipfile.ZipFile(sain, "w") as z:
        z.writestr("word/document.xml", b"<w:document/>")
    ok("un .docx ordinaire passe", ws.est_docx(sain))

rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
