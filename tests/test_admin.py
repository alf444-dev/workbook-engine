#!/usr/bin/env python3
"""Vérifie le dépôt de manuscrit : ce qui est accepté, ce qui est refusé.

Le pipeline est remplacé par une doublure : ce test porte sur le dépôt et sur
les droits, pas sur la compilation (couverte par tests/check_cn10_ids.py).

    python3 tests/test_admin.py
"""
import io, json, os, shutil, sys, tempfile, zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="wb-admin-"))
os.environ["WB_DATA"] = str(TMP)
os.environ["WB_ADMIN_TOKEN"] = "jeton-de-test"
sys.path.insert(0, str(REPO / "server"))

from fastapi.testclient import TestClient      # noqa: E402
import drive, store, workspace, app as appmod  # noqa: E402

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


def faux_docx():
    """Un .docx minimal mais authentique : un zip qui porte word/document.xml."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w:document/>")
    return buf.getvalue()


# Doublure du pipeline : on écrit ce que run.sh aurait produit, sans le lancer.
recu = {}

def run_doublure(pid, docx, nom, on_step=None, decisions=None):
    recu["decisions"] = decisions
    ws = workspace.workspace(pid)
    (ws / "output").mkdir(parents=True, exist_ok=True)
    (ws / "output" / "review.json").write_text(json.dumps({
        "project": nom, "source": Path(docx).name, "id_scheme": 1,
        "stats": {"lessons": 0, "blocks": 0, "exercises": 0, "pairs_checked": 0},
        "lessons": [], "items": []}), encoding="utf-8")
    (ws / "output" / "book.pdf").write_bytes(b"%PDF-1.7\n")
    (ws / "validation_report.txt").write_text("rien à signaler\n", encoding="utf-8")
    for etape in ("1/5  a", "5/5  b"):
        if on_step:
            on_step(etape)
    return True, "ok"


workspace.run = run_doublure
store.init()
client = TestClient(appmod.app)

# ---------------------------------------------------------------- accès au dépôt
ok("sans lien, la page de dépôt est refusée", client.get("/admin/").status_code == 403)
ok("un jeton de dépôt inventé est refusé", client.get("/a/faux").status_code == 404)
r = client.get("/a/jeton-de-test", follow_redirects=False)
ok("le lien de dépôt redirige sans son jeton",
   r.status_code == 303 and "jeton-de-test" not in r.headers["location"])
client.get("/a/jeton-de-test")
ok("avec le lien, la page s'ouvre", client.get("/admin/").status_code == 200)

# ---------------------------------------------------------------- ce qui est refusé
r = client.post("/admin/projects", files={"file": ("notes.pdf", b"%PDF", "application/pdf")})
ok("un PDF est refusé", r.status_code == 400, r.text[:90])

r = client.post("/admin/projects",
                files={"file": ("piege.docx", b"ceci n'est pas un zip", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
ok("un fichier renommé .docx est refusé", r.status_code == 400, r.text[:90])

buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("autre.xml", "x")
r = client.post("/admin/projects", files={"file": ("vide.docx", buf.getvalue())})
ok("un zip sans word/document.xml est refusé", r.status_code == 400, r.text[:90])

vrai = faux_docx()
appmod.TAILLE_MAX = 10
r = client.post("/admin/projects", files={"file": ("gros.docx", vrai)})
ok("un manuscrit trop lourd est refusé", r.status_code == 413, r.text[:90])
appmod.TAILLE_MAX = 40 * 1024 * 1024

# ---------------------------------------------------------------- dépôt réussi
r = client.post("/admin/projects", files={"file": ("../../evasion.docx", vrai)},
                data={"name": "Essai"})
ok("le dépôt aboutit", r.status_code == 200, r.text[:90])
pid = r.json()["id"]
ok("le nom de fichier reçu ne sert pas de chemin",
   (workspace.workspace(pid) / "input" / "evasion.docx").exists()
   and not (TMP / "evasion.docx").exists())

p = client.get(f"/admin/projects/{pid}").json()
ok("le projet est prêt et porte ses trois liens",
   p["status"] == "ready" and len(p["links"]) == 3 and all(l["url"] for l in p["links"]),
   p["status"])
ok("le livre et les rapports sont proposés",
   p["has_pdf"] and "validation_report.txt" in p["reports"], str(p["reports"]))
ok("le livre est téléchargeable depuis le dépôt",
   client.get(f"/admin/projects/{pid}/book.pdf").status_code == 200)
ok("les décisions sont transmises au pipeline, même vides",
   recu.get("decisions") == [], repr(recu.get("decisions")))
ok("un rapport inconnu n'est pas servi",
   client.get(f"/admin/projects/{pid}/reports/../../workbooks.db").status_code in (404, 400))

# ---------------------------------------------------------------- recompilation
store.record(pid, "pinyin-aaa", "teacher", "fix", "nǐ hǎo", "Wei",
             {"kind": "pinyin", "zh": "你好", "pinyin": "ni hao", "target": None})
r = client.post(f"/admin/projects/{pid}/recompile")
ok("la recompilation repart du manuscrit déposé", r.status_code == 200, r.text[:90])
ok("elle rejoue les décisions déjà prises",
   len(recu.get("decisions") or []) == 1
   and recu["decisions"][0]["value"] == "nǐ hǎo"
   and recu["decisions"][0]["zh"] == "你好",
   repr(recu.get("decisions")))

# ---------------------------------------------------------------- dossier Drive
ok("sans identifiants, la page annonce le dépôt Drive indisponible",
   client.get(f"/admin/projects/{pid}").json()["drive_ready"] is False)

os.environ["WB_DRIVE_CREDENTIALS"] = json.dumps({"type": "service_account"})
envoyes = []
drive._service = lambda: type("S", (), {"files": lambda self: type("F", (), {
    "list": lambda self, **kw: type("A", (), {"execute": lambda self: {"files": []}})(),
    "create": lambda self, **kw: (envoyes.append(kw["body"]["name"]),
                                  type("A", (), {"execute": lambda self: {"id": "x"}})())[1],
})()})()

r = client.post(f"/admin/projects/{pid}/drive",
                json={"folder": "https://drive.google.com/drive/folders/1AbC_dEfGhIjKlMnOpQr"})
ok("le lien du dossier Drive collé est retenu",
   r.status_code == 200 and r.json()["folder"] == "1AbC_dEfGhIjKlMnOpQr", r.text[:90])
ok("le livre et les rapports y sont déposés",
   "book.pdf" in envoyes and "validation_report.txt" in envoyes, str(envoyes))
ok("le dépôt est rapporté sur la fiche du projet",
   "déposé" in client.get(f"/admin/projects/{pid}").json()["drive_state"],
   client.get(f"/admin/projects/{pid}").json()["drive_state"])

r = client.post(f"/admin/projects/{pid}/drive", json={"folder": "https://exemple.fr/ailleurs"})
ok("un lien qui n'est pas un dossier Drive est refusé", r.status_code == 400, r.text[:90])
os.environ.pop("WB_DRIVE_CREDENTIALS")

# ---------------------------------------------------------------- renouvellement d'un lien
avant = [l["url"] for l in p["links"] if l["role"] == "teacher"][0]
jeton_avant = avant.rsplit("/", 1)[1]
neuf = client.post(f"/admin/projects/{pid}/rotate/teacher").json()["url"]
ok("le lien renouvelé est différent", neuf != avant)
ok("l'ancien lien du professeur ne marche plus",
   store.resolve_token(jeton_avant) is None)
ok("le nouveau lien marche",
   store.resolve_token(neuf.rsplit("/", 1)[1]) == (pid, "teacher"))

shutil.rmtree(TMP, ignore_errors=True)
rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
