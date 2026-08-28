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
    # un livre analysé : c'est de lui qu'un livre généré tire ses mesures
    (ws / "content").mkdir(parents=True, exist_ok=True)
    (ws / "content" / "book_typed.json").write_text(
        json.dumps({"meta": {}, "chapters": []}), encoding="utf-8")
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
ok("le projet est prêt et porte un lien par rôle",
   p["status"] == "ready" and len(p["links"]) == len(store.ROLES)
   and all(l["url"] for l in p["links"]),
   f"{p['status']}, {len(p['links'])} liens pour {len(store.ROLES)} rôles")
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

# ---------------------------------------------------------------- livre généré
ok("les langues disponibles sont annoncées",
   {l["code"] for l in client.get("/admin/projects").json()["langues"]}
   >= {"chinese", "japanese"})

ok("une langue inconnue est refusée",
   client.post("/admin/projects/generer",
               json={"reference": pid, "langue": "klingon"}).status_code == 400)
ok("un projet de référence inconnu est refusé",
   client.post("/admin/projects/generer",
               json={"reference": "zzzz", "langue": "japanese"}).status_code == 404)

planifie = {}


def planifier_doublure(pid_, langue, langue_reference, on_step=None):
    planifie.update(pid=pid_, langue=langue, reference=langue_reference)
    (workspace.workspace(pid_) / "content").mkdir(parents=True, exist_ok=True)
    (workspace.workspace(pid_) / "content" / "plan.json").write_text(
        json.dumps({"totaux": {"lecons": 2}, "lecons": [
            {"n": 1, "titre": "UNE", "exercices": ["mcq"], "vocabulaire": [],
             "quotas": {"caracteres_nouveaux": {"cible": 9},
                        "mots_prose": {"cible": 700}}}]}), encoding="utf-8")
    return True, "ok"


workspace.mesurer_et_planifier = planifier_doublure
r = client.post("/admin/projects/generer",
                json={"reference": pid, "langue": "japanese", "nom": "Japonais"})
ok("un livre à produire est créé", r.status_code == 200, r.text[:90])
gid = r.json()["id"]
g = client.get(f"/admin/projects/{gid}").json()
ok("il porte sa langue, sa référence et sa phase",
   g["kind"] == "generation" and g["langue"] == "japanese"
   and g["reference"] == pid and g["phase"] == "plan",
   f"{g['kind']}/{g['langue']}/{g['phase']}")
ok("la mesure part de la langue du projet de référence",
   planifie.get("reference") == "chinese", str(planifie))
ok("son plan est consultable",
   client.get(f"/admin/projects/{gid}/plan").json()["lecons"][0]["titre"] == "UNE")
ok("un projet sans plan le dit plutôt que de planter",
   client.get(f"/admin/projects/{pid}/plan").status_code == 404)

# --- proposition de la progression (le modèle est remplacé par une doublure)
propose = {}


def proposer_doublure(pid_, langue, projet):
    propose.update(pid=pid_, langue=langue)
    (workspace.workspace(pid_) / "content" / "vocabulaire_propose.json").write_text(
        json.dumps({"langue": langue, "lecons": [
            {"n": 1, "titre": "UNE", "entrees": [
                {"ecriture": "あ", "prononciation": "a", "sens": "a"}]}]}),
        encoding="utf-8")
    return True, "ok"


workspace.proposer_vocabulaire = proposer_doublure
ok("le coût est annoncé avant de lancer",
   "$" in client.get(f"/admin/projects/{gid}").json()["estimations"]["vocabulaire"]["phrase"])
r = client.post(f"/admin/projects/{gid}/vocabulaire")
ok("la proposition part et annonce son coût",
   r.status_code == 200 and r.json()["estimation"]["dollars"] > 0, r.text[:90])
g = client.get(f"/admin/projects/{gid}").json()
ok("la phase avance et les entrées sont comptées",
   g["phase"] == "vocabulaire_propose" and g["vocabulaire"] == 1,
   f"{g['phase']} / {g['vocabulaire']}")
ok("proposer sur un projet sans plan est refusé",
   client.post(f"/admin/projects/{pid}/vocabulaire").status_code == 404)

# --- écriture des leçons, reprenable (le modèle est remplacé par une doublure)
ecrites = []


def generer_doublure(pid_, langue, projet, a_faire, sur_lecon):
    ecrites.append(list(a_faire))
    for n in a_faire:
        sur_lecon(n, "faite", 5000, 16000, "")
    return True


workspace.generer_lecons = generer_doublure
r = client.post(f"/admin/projects/{gid}/generer-lecons")
ok("l'écriture des leçons part et annonce son coût",
   r.status_code == 200 and r.json()["estimation"]["dollars"] > 0, r.text[:90])
g = client.get(f"/admin/projects/{gid}").json()
ok("l'avancement est suivi en base, leçon par leçon",
   g["avancement"]["faites"] == g["avancement"]["total"] == 1, str(g["avancement"]))
ok("le coût réel est cumulé",
   g["avancement"]["sortie"] == 16000, str(g["avancement"]))

store.set_lecon(gid, 1, "echec", erreur="délai dépassé")
client.post(f"/admin/projects/{gid}/generer-lecons")
ok("relancer ne refait que ce qui manque",
   ecrites[-1] == [1] and len(ecrites) == 2, str(ecrites))

store.set_lecon(gid, 1, "faite", 5000, 16000)
client.post(f"/admin/projects/{gid}/generer-lecons")
ok("tout étant fait, plus rien n'est réécrit", ecrites[-1] == [], str(ecrites[-1]))

# --- assemblage
assemble = {}


def assembler_doublure(pid_, langue, projet):
    assemble["pid"] = pid_
    return True, "ok"


workspace.assembler = assembler_doublure
r = client.post(f"/admin/projects/{gid}/assembler")
ok("le livre s'assemble depuis la page", r.status_code == 200, r.text[:90])
ok("et la phase passe à « prêt »",
   client.get(f"/admin/projects/{gid}").json()["phase"] == "pret")
ok("assembler sans aucune leçon écrite est refusé",
   client.post(f"/admin/projects/{pid}/assembler").status_code == 404)

ok("les titres se transposent d'une langue à l'autre",
   workspace.transposer_titres(["HOW CHINESE WORKS", "Chinese at work", "NUMBERS"],
                               "Chinese", "Japanese")
   == ["HOW JAPANESE WORKS", "Japanese at work", "NUMBERS"])

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
   "uploaded" in client.get(f"/admin/projects/{pid}").json()["drive_state"],
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

# ---------------------------------------------------------------- sauvegarde
anonyme = TestClient(appmod.app)
ok("l'état des sauvegardes exige le jeton",
   anonyme.get("/admin/backups").status_code in (401, 403, 404))
ok("le téléchargement d'une sauvegarde exige le jeton",
   anonyme.get("/admin/backups/derniere").status_code in (401, 403, 404))

r = client.post("/admin/backups")
ok("on peut sauvegarder à la demande", r.status_code == 200, r.text[:120])
etat = client.get("/admin/backups").json()
ok("l'archive apparaît dans l'état", len(etat["archives"]) >= 1, str(etat)[:150])
ok("l'archive porte sa date et sa taille",
   etat["archives"][0].get("date") and etat["archives"][0].get("octets", 0) > 0)

copie = client.get("/admin/backups/derniere")
ok("la copie se télécharge", copie.status_code == 200 and len(copie.content) > 0)
ok("la copie est bien une archive gzip", copie.content[:2] == b"\x1f\x8b",
   repr(copie.content[:8]))

import io as _io, tarfile as _tarfile                            # noqa: E402
with _tarfile.open(fileobj=_io.BytesIO(copie.content), mode="r:gz") as t:
    dedans = t.getnames()
ok("la copie contient la base des décisions",
   any(n.endswith("workbooks.db") for n in dedans), str(dedans)[:200])
ok("la copie contient les manuscrits déposés",
   any(n.endswith(".docx") for n in dedans), str(dedans)[:200])

page = client.get(f"/a/{os.environ['WB_ADMIN_TOKEN']}").text
ok("la page propose de télécharger une copie", 'href="backups/derniere"' in page)
ok("la page propose de sauvegarder maintenant", 'id="bk-now"' in page)

shutil.rmtree(TMP, ignore_errors=True)
rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
