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
# La génération est doublée : aucune requête ne part. La clé sert seulement
# à passer le contrôle qui refuse de lancer une étape payante sans elle.
os.environ["ANTHROPIC_API_KEY"] = "sk-doublure"
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

# --- la validation du professeur est obligatoire avant d'écrire
r = client.post(f"/admin/projects/{gid}/generer-lecons")
ok("écrire sans progression validée est refusé", r.status_code == 409, r.text[:120])
ok("et le refus dit quoi faire", "approve" in r.text.lower(), r.text[:120])


def valider_doublure(pid_, langue, projet, decisions):
    """apply_vocab + plan.py : ce que la vraie fonction produit, en substance."""
    valide.update(decisions=decisions, langue=langue)
    chemin = workspace.workspace(pid_) / "content" / "plan.json"
    plan = json.loads(chemin.read_text(encoding="utf-8"))
    plan["lecons"][0]["vocabulaire"] = [{"zh": "あ", "pinyin": "a"}]
    chemin.write_text(json.dumps(plan), encoding="utf-8")
    return True, "curriculum validé"


valide = {}
workspace.valider_vocabulaire = valider_doublure
r = client.post(f"/admin/projects/{gid}/vocabulaire/valider")
ok("les décisions du professeur peuvent être versées au plan",
   r.status_code == 200, r.text[:120])
g = client.get(f"/admin/projects/{gid}").json()
ok("la phase passe à « progression validée »",
   g["phase"] == "vocabulaire_valide", g["phase"])
ok("le plan impose désormais du vocabulaire", g["vocabulaire_impose"] == 1,
   str(g.get("vocabulaire_impose")))
ok("les décisions enregistrées lui sont bien passées", "decisions" in valide)

# --- une leçon d'essai avant de payer le livre entier
essais = []


def essai_doublure(pid_, langue, projet, a_faire, sur_lecon):
    essais.append(list(a_faire))
    for n in a_faire:
        sur_lecon(n, "faite", 100, 200, "")
        ws = workspace.workspace(pid_) / "content" / "generated"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / f"lecon_{n:02d}.json").write_text(json.dumps({
            "kind": "chapter", "num": n, "title": "UNE", "blocks": [
                {"type": "para", "text": "Bonjour."},
                {"type": "table", "ncols": 2,
                 "rows": [["Japanese", "English"], ["{zh:みず} {py:mizu}", "water"]]}]}),
            encoding="utf-8")
    return ""


vrai_gen = workspace.generer_lecons
workspace.generer_lecons = essai_doublure
r = client.post(f"/admin/projects/{gid}/generer-lecons?une=1")
ok("on peut n'écrire qu'une leçon", r.status_code == 200, r.text[:120])
ok("une seule est demandée au pipeline", essais and essais[-1] == [1], str(essais))
ok("et son coût annoncé est celui d'une leçon, pas du livre",
   r.json()["estimation"]["dollars"] < 2, str(r.json()["estimation"]))
g = client.get(f"/admin/projects/{gid}").json()
ok("un essai réussi n'est pas annoncé comme un échec", g["status"] == "ready",
   f"{g['status']} — {g.get('log')}")

page = client.get(f"/admin/projects/{gid}/lecons/1")
ok("la leçon écrite se lit seule, sans assembler le livre",
   page.status_code == 200 and "mizu" in page.text, str(page.status_code))
ok("et les marqueurs de paires n'apparaissent pas au lecteur",
   "{zh:" not in page.text, page.text[:200])
ok("une leçon non écrite renvoie une erreur claire",
   client.get(f"/admin/projects/{gid}/lecons/9").status_code == 404)
ok("la lecture d'une leçon exige le jeton",
   TestClient(appmod.app).get(f"/admin/projects/{gid}/lecons/1").status_code == 403)
workspace.generer_lecons = vrai_gen
for n in (1,):
    store.set_lecon(gid, n, "a_faire")

# --- écriture des leçons, reprenable (le modèle est remplacé par une doublure)
ecrites = []


def generer_doublure(pid_, langue, projet, a_faire, sur_lecon):
    ecrites.append(list(a_faire))
    for n in a_faire:
        sur_lecon(n, "faite", 5000, 16000, "")
    return True


# La vraie fonction est gardée sous la main : la doublure ci-dessus reste posée
# jusqu'à la fin du fichier, et la boucle réelle est testée plus bas.
GENERER_REEL = workspace.generer_lecons
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

# ---------------------------------------------------------------- issue d'une génération
gid = store.create_project("issue", "ref.docx", kind="generation", langue="japanese")
store.declarer_lecons(gid, ["A", "B"])
store.set_lecon(gid, 1, "echec", erreur="RuntimeError: schéma refusé")
store.set_lecon(gid, 2, "echec", erreur="RuntimeError: schéma refusé")
av = store.avancement(gid)
ok("un échec porte son motif jusqu'à la page", av["erreur"] == "RuntimeError: schéma refusé",
   str(av))

# On appelle la vraie fonction, avec la génération doublée : c'est la conclusion
# qu'elle tire de l'état des leçons qu'on vérifie, pas une règle recopiée ici.
vrai_titres, vraie_generation = workspace.titres_du_plan, workspace.generer_lecons
workspace.titres_du_plan = lambda pid: ["A", "B"]
workspace.generer_lecons = lambda *a, **k: None

appmod.lancer_generation(gid, "japanese", "issue")
ok("aucune leçon écrite ne donne pas un projet prêt",
   store.get_project(gid)["status"] == "failed", store.get_project(gid)["status"])
ok("et le journal dit pourquoi",
   "schéma refusé" in (store.get_project(gid)["log"] or ""),
   store.get_project(gid)["log"])

store.set_lecon(gid, 1, "faite", entree=10, sortie=20)
store.set_lecon(gid, 2, "faite", entree=10, sortie=20)
appmod.lancer_generation(gid, "japanese", "issue")
ok("toutes les leçons écrites donnent un projet prêt",
   store.get_project(gid)["status"] == "ready", store.get_project(gid)["status"])
workspace.titres_du_plan, workspace.generer_lecons = vrai_titres, vraie_generation
av = store.avancement(gid)
ok("sans échec, aucun motif à afficher", av["erreur"] == "", str(av["erreur"]))

store.set_lecon(gid, 2, "echec", erreur="clé sk-ant-" + "B" * 30 + " refusée")
ok("un motif ne peut pas republier un secret",
   "sk-ant-BBBB" not in store.avancement(gid)["erreur"],
   store.avancement(gid)["erreur"])

page_fiche = client.get(f"/a/{os.environ['WB_ADMIN_TOKEN']}").text
ok("la page sait afficher un motif d'échec", 'class="motif"' in page_fiche)

# ---------------------------------------------------------------- arrêt anticipé
ok("une erreur de compte est reconnue comme fatale",
   workspace.cause_fatale("anthropic.BadRequestError: Your credit balance is too "
                          "low to access the Anthropic API."))
ok("une erreur de leçon ne l'est pas",
   workspace.cause_fatale("RuntimeError: réponse tronquée à max_tokens") is None)

vrai_lancer = workspace.lancer
tentees = []

def lancer_qui_echoue(pid, args, langue=None, projet=None):
    tentees.append(args[-1])
    return False, "anthropic.BadRequestError: Your credit balance is too low."

workspace.lancer = lancer_qui_echoue
vues = []
arret = GENERER_REEL(gid, "japanese", "issue", [1, 2, 3],
                                 lambda n, etat, e, s_, err: vues.append((n, etat)))
ok("la série s'arrête au premier échec de compte", len(tentees) == 1, str(tentees))
ok("et la raison de l'arrêt remonte", "credit balance" in arret, arret)
ok("les leçons non tentées restent à faire, donc Resume les reprendra",
   [n for n, e in vues if e == "echec"] == [1], str(vues))

tentees.clear()
workspace.lancer = lambda pid, args, langue=None, projet=None: (
    tentees.append(args[-1]) or (False, "RuntimeError: réponse tronquée"))
arret = GENERER_REEL(gid, "japanese", "issue", [1, 2, 3, 4, 5],
                                 lambda *a: None)
ok("trois échecs d'affilée arrêtent aussi la série", len(tentees) == 3, str(tentees))
ok("et disent que le problème n'est plus la leçon",
   "in a row" in arret, arret)
workspace.lancer = vrai_lancer

# ---------------------------------------------------------------- avant de payer
cle = os.environ.pop("ANTHROPIC_API_KEY", None)
message = appmod.prete_a_generer()
ok("sans clé, on refuse de lancer une étape payante", message is not None)
ok("et on dit où la mettre",
   message and "ANTHROPIC_API_KEY" in message and "Environment" in message, message)

os.environ["ANTHROPIC_API_KEY"] = "sk-essai"
ok("avec la clé et les bibliothèques, rien n'empêche",
   appmod.prete_a_generer() is None, str(appmod.prete_a_generer()))

import importlib.util as _iu                                     # noqa: E402
vrai_find_spec = _iu.find_spec
_iu.find_spec = lambda nom, *a, **k: None if nom == "httpx" else vrai_find_spec(nom, *a, **k)
manque = appmod.prete_a_generer()
_iu.find_spec = vrai_find_spec
ok("une image sans httpx est signalée comme telle, pas par un traceback",
   manque and "httpx" in manque and "redeploy" in manque, str(manque))
if cle is None:
    os.environ.pop("ANTHROPIC_API_KEY", None)
else:
    os.environ["ANTHROPIC_API_KEY"] = cle

d = client.get("/admin/projects").json()
ok("la liste dit ce qui empêche de générer, ou rien", "empechement" in d)
ok("avec la clé, elle n'annonce aucun empêchement", d["empechement"] is None,
   str(d["empechement"]))
page_admin = client.get(f"/a/{os.environ['WB_ADMIN_TOKEN']}").text
ok("la page a la bande qui l'affiche", 'id="empechement"' in page_admin)

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
