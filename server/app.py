#!/usr/bin/env python3
"""Workbook Engine — serveur de relecture.

Pas de comptes : un lien par projet et par rôle. Le jeton arrive dans l'URL
(`/r/<jeton>`), le serveur le range dans un cookie et redirige vers une URL qui
ne le contient plus. Un lien qui traîne dans un historique, une capture d'écran
ou un partage d'écran ne le divulgue donc pas. Le cookie est nommé par projet et
par rôle : un manager peut tenir plusieurs liens ouverts sans les écraser.

Chaque rôle ne reçoit que sa propre file : le lien envoyé à un professeur
externe ne contient pas le reste du manuscrit.
"""
import json, os, shutil, tempfile, time
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse

import couts, drive, planning, store, workspace

REPO = Path(__file__).resolve().parent.parent
CONSOLE = REPO / "webapp" / "console.html"
ACTIONS = {"ok", "fix", "skip", "drop"}      # « drop » : entrée de vocabulaire écartée

app = FastAPI(title="Workbook Engine", docs_url=None, redoc_url=None, openapi_url=None)


@app.on_event("startup")
def _startup():
    store.init()
    corriges = store.nettoyer_secrets()
    if corriges:
        print(f"{corriges} journal(aux) contenaient un secret : masqué.")
    planning.demarrer()


# Quelle version tourne réellement. Sans ça, une construction qui échoue laisse
# l'ancienne image en place et le site répond exactement pareil : impossible de
# savoir si un correctif est déployé autrement qu'en le testant à l'aveugle.
# Render pose RENDER_GIT_COMMIT dans l'environnement ; en local, il n'y a rien.
VERSION = (os.environ.get("RENDER_GIT_COMMIT") or "")[:7]


@app.middleware("http")
async def entetes(request: Request, call_next):
    r = await call_next(request)
    if VERSION:
        r.headers["X-Workbook-Version"] = VERSION
    # Les manuscrits ne sont pas publics : ni indexation, ni fuite par le Referer.
    r.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    r.headers["Referrer-Policy"] = "no-referrer"
    r.headers["X-Content-Type-Options"] = "nosniff"
    return r


MESSAGES = {
    403: ("This link no longer works",
          "It may have been replaced by a new one, or it was never valid. "
          "Ask whoever sent it to you for a fresh link."),
    404: ("Nothing here",
          "This address does not point to anything. Check the link you were sent."),
    409: ("Not ready yet",
          "This step cannot run until the previous one is finished."),
}


@app.exception_handler(HTTPException)
async def refus_lisible(request: Request, exc: HTTPException):
    """Un navigateur reçoit une page, un programme reçoit du JSON.

    Sans ça, un lien révoqué ouvrait une page de JSON brut : illisible pour un
    professeur externe, et impossible à distinguer d'une panne."""
    veut_html = "text/html" in request.headers.get("accept", "")
    if veut_html and exc.status_code in MESSAGES:
        titre, texte = MESSAGES[exc.status_code]
        return page(titre, texte, exc.status_code)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return "User-agent: *\nDisallow: /\n"


ACCUEIL = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>Workbook Engine</title>
<style>
 body{margin:0;min-height:100vh;display:grid;place-items:center;background:#EEF2F0;
   color:#12211E;font-family:"Archivo",system-ui,sans-serif;padding:24px}
 .box{max-width:430px;text-align:center;display:flex;flex-direction:column;gap:12px}
 h1{font-family:"Source Serif 4",Georgia,serif;font-size:27px;font-weight:600;margin:0}
 p{margin:0;color:#5D6A66;font-size:15px;line-height:1.55}
 code{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:13px;color:#1A5E52}
</style></head><body><div class="box">
<h1>%s</h1><p>%s</p></div></body></html>"""


def page(titre, texte, code=200):
    return HTMLResponse(ACCUEIL % (titre, texte), status_code=code)


@app.get("/", response_class=HTMLResponse)
def racine():
    """Une porte fermée doit dire qu'elle est une porte.

    Un 404 nu sur la racine laisse croire que le site est cassé — c'est ce qu'a
    vu la première personne à qui on a donné l'adresse."""
    return page("Workbook Engine",
                "This tool is reached through a private link. "
                "If you were sent one, open that link — it is what grants access. "
                "If you do not have one yet, ask whoever runs the project.")


def cookie_name(pid, role):
    return f"wb_{pid}_{role}"


@app.get("/r/{token}")
def ouvrir(token: str):
    """Échange le jeton contre un cookie, puis sort le jeton de l'URL."""
    lien = store.resolve_token(token)
    if not lien:
        raise HTTPException(404, "unknown or revoked link")
    pid, role = lien
    base = f"/p/{pid}/{role}/"
    r = RedirectResponse(base, status_code=303)
    r.set_cookie(cookie_name(pid, role), token, httponly=True, samesite="lax",
                 path=base, max_age=60 * 60 * 24 * 365,
                 secure=os.environ.get("WB_HTTPS") == "1")
    return r


def autoriser(request: Request, pid: str, role: str):
    """Le cookie doit porter un jeton valable pour ce projet et ce rôle."""
    token = request.cookies.get(cookie_name(pid, role))
    if store.resolve_token(token) != (pid, role):
        raise HTTPException(403, "link missing or revoked — open the link you were sent again")
    projet = store.get_project(pid)
    if not projet:
        raise HTTPException(404)
    return projet


@app.get("/p/{pid}/{role}/", response_class=HTMLResponse)
def console(request: Request, pid: str, role: str):
    autoriser(request, pid, role)
    # Même fichier que la console autonome : le serveur y met `null` à la place
    # du bundle, la page va alors le chercher par l'API.
    return HTMLResponse(CONSOLE.read_text(encoding="utf-8").replace("__BUNDLE__", "null"))


@app.get("/p/{pid}/{role}/bundle.json")
def bundle(request: Request, pid: str, role: str):
    projet = autoriser(request, pid, role)
    chemin = workspace.artifact(pid, "review.json")
    if not chemin:
        return JSONResponse({"status": projet["status"], "step": projet["step"]},
                            status_code=503)
    b = json.loads(chemin.read_text(encoding="utf-8"))
    b["items"] = [i for i in b["items"] if i["queue"] == role]
    b["role"] = role
    b["project_id"] = pid
    b["project"] = projet["name"]
    return b


@app.get("/p/{pid}/{role}/decisions")
def lire_decisions(request: Request, pid: str, role: str):
    autoriser(request, pid, role)
    return {k: {c: v for c, v in d.items() if c != "context"}
            for k, d in store.current(pid).items()}


@app.post("/p/{pid}/{role}/decisions")
async def ecrire_decision(request: Request, pid: str, role: str):
    autoriser(request, pid, role)
    corps = await request.json()
    item_id = str(corps.get("item_id") or "")
    action = str(corps.get("action") or "")
    if action not in ACTIONS:
        raise HTTPException(400, f"unknown action: {action}")

    # Un rôle n'écrit que sur sa propre file : le lien du professeur ne permet
    # pas de trancher les corrigés du manager.
    chemin = workspace.artifact(pid, "review.json")
    if not chemin:
        raise HTTPException(503, "this book has not been built yet")
    b = json.loads(chemin.read_text(encoding="utf-8"))
    item = next((i for i in b["items"] if i["id"] == item_id and i["queue"] == role), None)
    if item is None:
        raise HTTPException(404, "item is not in this queue")

    contexte = {c: item.get(c) for c in ("kind", "lesson", "zh", "pinyin", "target")}
    seq = store.record(pid, item_id, role, action,
                       str(corps.get("value") or "")[:2000],
                       str(corps.get("by") or "")[:80], contexte)
    return {"ok": True, "seq": seq}


@app.get("/p/{pid}/{role}/book.pdf")
def livre(request: Request, pid: str, role: str):
    autoriser(request, pid, role)
    if role != "manager":
        raise HTTPException(403, "the full book is not part of this queue")
    p = workspace.artifact(pid, "book.pdf")
    if not p:
        raise HTTPException(404)
    return FileResponse(p, media_type="application/pdf", filename="book.pdf")


@app.get("/p/{pid}/{role}/reports/{nom}")
def rapport(request: Request, pid: str, role: str, nom: str):
    autoriser(request, pid, role)
    if role != "manager":
        raise HTTPException(403)
    if nom not in workspace.REPORTS:
        raise HTTPException(404)
    p = workspace.artifact(pid, nom)
    if not p:
        raise HTTPException(404)
    return FileResponse(p, media_type="text/plain; charset=utf-8")


# ---------------------------------------------------------------- dépôt (team manager)
ADMIN_COOKIE = "wb_admin"
ADMIN = REPO / "webapp" / "admin.html"
TAILLE_MAX = 40 * 1024 * 1024
ETIQUETTE = {"teacher": "Native teacher", "editor": "Editor",
             "manager": "Team manager", "vocab": "Vocabulary (teacher)"}


@app.get("/a/{token}")
def ouvrir_depot(token: str):
    if token != store.admin_token():
        raise HTTPException(404)
    r = RedirectResponse("/admin/", status_code=303)
    r.set_cookie(ADMIN_COOKIE, token, httponly=True, samesite="lax", path="/admin/",
                 max_age=60 * 60 * 24 * 365, secure=os.environ.get("WB_HTTPS") == "1")
    return r


def admin_requis(request: Request):
    if request.cookies.get(ADMIN_COOKIE) != store.admin_token():
        raise HTTPException(403, "admin link missing — open the link you were sent again")


@app.get("/admin/", response_class=HTMLResponse)
def page_depot(request: Request):
    admin_requis(request)
    return HTMLResponse(ADMIN.read_text(encoding="utf-8"))


def langues_disponibles():
    """Les configs de langue présentes dans le dépôt."""
    out = []
    for f in sorted((REPO / "config").glob("*.json")):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        # nom affiché en anglais : l'application est lue par des relecteurs
        # externes, qui ne sont pas forcément francophones
        out.append({"code": f.stem,
                    "nom": c.get("nom_affiche") or c.get("langue", f.stem),
                    "public": c.get("public_affiche") or c.get("public", "")})
    return out


def estimations(pid):
    """Ce que coûteraient les prochaines étapes, annoncé avant de les lancer."""
    chemin = workspace.workspace(pid) / "content" / "plan.json"
    n = 31
    if chemin.exists():
        n = len(json.loads(chemin.read_text(encoding="utf-8"))["lecons"])
    out = {}
    for quoi, cle in (("vocabulaire", "vocabulaire"), ("lecon", "generation")):
        d, s, phrase = couts.estimer(quoi, n if quoi == "lecon" else 1)
        out[cle] = {"dollars": d, "secondes": s, "phrase": phrase}
    return out


def decrire(projet, base):
    """Un projet tel que la page de dépôt l'affiche."""
    pid = projet["id"]
    liens = {l["role"]: f"{base}/r/{l['token']}" for l in store.links_for(pid)}
    decisions = store.current(pid)
    d = {
        "id": pid, "name": projet["name"], "source": projet["source"],
        "created_at": projet["created_at"], "status": projet["status"],
        "step": projet["step"],
        "links": [{"role": r, "label": ETIQUETTE[r], "url": liens.get(r)}
                  for r in store.ROLES],
        "decisions": len(decisions),
        "reviewers": sorted({d["by"] for d in decisions.values() if d["by"]}),
        "has_pdf": bool(workspace.artifact(pid, "book.pdf")),
        "kind": projet["kind"], "langue": projet["langue"],
        "langue_nom": next((l["nom"] for l in langues_disponibles()
                            if l["code"] == projet["langue"]), projet["langue"]),
        "reference": projet["reference"], "phase": projet["phase"],
        "vocabulaire": workspace.compter_vocabulaire(pid),
        "vocabulaire_impose": workspace.vocabulaire_du_plan(pid),
        "avancement": store.avancement(pid),
        "estimations": estimations(pid) if projet["kind"] == "generation" else {},
        "drive_ready": drive.configure(),
        "drive_folder": projet["drive_folder"],
        "drive_state": projet["drive_state"],
        "reports": [n for n in workspace.REPORTS if workspace.artifact(pid, n)],
    }
    if projet["status"] == "failed":
        # La cause doit être visible là où l'échec est annoncé, pas ailleurs.
        # Le team manager n'est pas développeur : une phrase d'abord, la trace après.
        journal = projet["log"] or ""
        lignes = [l for l in journal.splitlines() if l.strip()]
        d["error"] = lignes[-1].strip() if lignes else "unknown cause"
        d["step"] = next((l for l in reversed(lignes) if len(l) > 3 and l[1] == "/"), None)
        d["log"] = journal[-4000:]
    return d


def archives():
    dossier = store.DATA / "backups"
    return sorted(dossier.glob("workbook-*.tar.gz")) if dossier.exists() else []


@app.get("/admin/backups")
def etat_sauvegardes(request: Request):
    """Ce qui est sauvegardé, et quand. Une archive qu'on ne peut pas voir ne
    rassure personne."""
    admin_requis(request)
    fichiers = archives()
    return {"archives": [{"nom": f.name, "octets": f.stat().st_size,
                          "date": time.strftime("%Y-%m-%d %H:%M",
                                                time.gmtime(f.stat().st_mtime))}
                         for f in reversed(fichiers)][:14],
            "drive": bool(os.environ.get("WB_DRIVE_BACKUP_FOLDER")) and drive.configure()}


@app.post("/admin/backups")
def sauvegarder_maintenant(request: Request):
    admin_requis(request)
    cible = planning.sauvegarder()
    return {"nom": cible.name, "octets": cible.stat().st_size}


@app.get("/admin/backups/derniere")
def telecharger_sauvegarde(request: Request):
    """Sortir la copie du serveur : une archive posée sur le disque qu'elle
    sauvegarde ne protège pas de la perte de ce disque."""
    admin_requis(request)
    fichiers = archives()
    if not fichiers:
        raise HTTPException(404, "no backup yet")
    dernier = fichiers[-1]
    return FileResponse(dernier, media_type="application/gzip", filename=dernier.name)


@app.get("/admin/projects")
def lister(request: Request):
    admin_requis(request)
    base = str(request.base_url).rstrip("/")
    return {"projets": [decrire(p, base) for p in store.list_projects()],
            "langues": langues_disponibles(),
            # Ce qui empêche de générer se dit en haut de la page, avant qu'on
            # lance une étape, pas une heure après l'avoir lancée.
            "empechement": prete_a_generer()}


@app.get("/admin/projects/{pid}")
def etat(request: Request, pid: str):
    admin_requis(request)
    projet = store.get_project(pid)
    if not projet:
        raise HTTPException(404)
    return decrire(projet, str(request.base_url).rstrip("/"))


def compiler(pid, docx, nom):
    """Lance le pipeline et tient l'état à jour pour la barre de progression.

    Les décisions déjà prises sont rejouées après la conversion : c'est ce qui
    fait qu'une correction de professeur se retrouve dans le livre, et qu'elle
    y reste au dépôt suivant."""
    store.set_status(pid, "running", step="1/7  docx → structure")
    try:
        ok, journal = workspace.run(pid, docx, nom,
                                    on_step=lambda l: store.set_status(pid, "running", step=l),
                                    decisions=store.for_replay(pid))
    except Exception as e:                      # le manuscrit peut faire tomber le parseur
        store.set_status(pid, "failed", log=f"{type(e).__name__}: {e}")
        return
    store.set_status(pid, "ready" if ok else "failed", log=journal)
    if ok:
        deposer_sur_drive(pid)


def deposer_sur_drive(pid):
    """Dépose le livre et les rapports dans le dossier Drive du projet.

    Un échec ici ne remet pas en cause la compilation : le livre est déjà
    disponible sur la page. On le dit, on ne le cache pas."""
    projet = store.get_project(pid)
    dossier = (projet or {}).get("drive_folder")
    if not dossier or not drive.configure():
        return
    fichiers = [workspace.artifact(pid, n)
                for n in ("book.pdf",) + workspace.REPORTS]
    fichiers = [f for f in fichiers if f]
    try:
        deposes = drive.deposer(dossier, fichiers)
        store.set_drive(pid, state=f"{len(deposes)} file(s) uploaded on {store.now()}")
    except Exception as e:
        store.set_drive(pid, state=f"Drive upload failed: {type(e).__name__}: {e}"[:300])


@app.post("/admin/projects")
async def deposer(request: Request, background: BackgroundTasks,
                  file: UploadFile = File(...), name: str = Form("")):
    admin_requis(request)

    # Jamais le nom de fichier reçu : il sert d'affichage, pas de chemin.
    origine = Path(file.filename or "manuscrit.docx").name
    if not origine.lower().endswith(".docx"):
        raise HTTPException(400, "a .docx file is required")

    tmp = Path(tempfile.mkdtemp(prefix="wb-upload-")) / "manuscrit.docx"
    taille = 0
    with tmp.open("wb") as f:
        while chunk := await file.read(1 << 20):
            taille += len(chunk)
            if taille > TAILLE_MAX:
                shutil.rmtree(tmp.parent, ignore_errors=True)
                raise HTTPException(413, "manuscript too large (40 MB maximum)")
            f.write(chunk)
    if not workspace.est_docx(tmp):
        shutil.rmtree(tmp.parent, ignore_errors=True)
        raise HTTPException(400, "this file is not a Word document")

    nom = (name or "").strip() or Path(origine).stem.replace("_", " ")
    pid = store.create_project(nom, origine)
    cible = workspace.workspace(pid) / "input"
    cible.mkdir(parents=True, exist_ok=True)
    depot = cible / origine
    shutil.move(str(tmp), depot)
    shutil.rmtree(tmp.parent, ignore_errors=True)

    background.add_task(compiler, pid, str(depot), nom)
    return {"id": pid}


def preparer_livre(pid, reference, langue, langue_reference, nom):
    """Mesure le livre de référence et planifie dans la langue cible.
    Déterministe : aucun appel à un modèle, donc rien à facturer ici."""
    store.set_status(pid, "running", step="preparing")
    try:
        workspace.preparer_generation(pid, reference, langue)
        ok, journal = workspace.mesurer_et_planifier(
            pid, langue, langue_reference,
            on_step=lambda l: store.set_status(pid, "running", step=l))
    except Exception as e:
        store.set_status(pid, "failed", log=f"{type(e).__name__}: {e}")
        return
    store.set_status(pid, "ready" if ok else "failed", log=journal)
    if ok:
        store.set_phase(pid, "plan")


@app.post("/admin/projects/generer")
async def generer(request: Request, background: BackgroundTasks):
    """Crée un livre à produire, à partir d'un projet de référence et d'une langue."""
    admin_requis(request)
    corps = await request.json()
    reference = store.get_project(str(corps.get("reference") or ""))
    if not reference:
        raise HTTPException(404, "unknown reference project")
    if reference["status"] != "ready":
        raise HTTPException(409, "the reference project must be built first")

    langue = str(corps.get("langue") or "")
    if langue not in {l["code"] for l in langues_disponibles()}:
        raise HTTPException(400, f"unknown language: {langue}")
    langue_reference = reference["langue"] or "chinese"

    nom = (corps.get("nom") or "").strip() or f"{langue} book"
    pid = store.create_project(nom, f"config/{langue}.json", kind="generation",
                               langue=langue, reference=reference["id"])
    background.add_task(preparer_livre, pid, reference["id"], langue,
                        langue_reference, nom)
    return {"id": pid}


@app.get("/admin/projects/{pid}/plan")
def voir_plan(request: Request, pid: str):
    admin_requis(request)
    chemin = workspace.workspace(pid) / "content" / "plan.json"
    if not chemin.exists():
        raise HTTPException(404, "no plan yet")
    plan = json.loads(chemin.read_text(encoding="utf-8"))
    return {"totaux": plan["totaux"],
            "lecons": [{"n": l["n"], "titre": l["titre"],
                        "exercices": l["exercices"],
                        "vocabulaire": len(l.get("vocabulaire") or []),
                        "caracteres": l["quotas"]["caracteres_nouveaux"]["cible"],
                        "mots_prose": l["quotas"]["mots_prose"]["cible"]}
                       for l in plan["lecons"]]}


def prete_a_generer():
    """Ce qui doit être vrai avant de lancer une étape payante.

    Sans ce contrôle, une clé absente ou une image incomplète se manifestent une
    fois l'étape lancée, sous la forme d'une carte rouge et d'un traceback — au
    lieu d'une phrase qui dit quoi faire. C'est arrivé pour les deux.
    """
    import importlib.util
    for module in ("anthropic", "httpx"):
        if importlib.util.find_spec(module) is None:
            return (f"this server is missing the {module} library — redeploy so "
                    f"the image is rebuilt, then try again")
    if not (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
        return ("no API key on this server — add ANTHROPIC_API_KEY in Render → "
                "Settings → Environment, then try again")
    return None


def generation_possible():
    empeche = prete_a_generer()
    if empeche:
        raise HTTPException(409, empeche)


def lancer_vocabulaire(pid, langue, nom):
    store.set_status(pid, "running", step="proposing the progression")
    try:
        ok, journal = workspace.proposer_vocabulaire(pid, langue, nom)
    except Exception as e:
        store.set_status(pid, "failed", log=f"{type(e).__name__}: {e}")
        return
    store.set_status(pid, "ready" if ok else "failed", log=journal)
    if ok:
        store.set_phase(pid, "vocabulaire_propose")


@app.post("/admin/projects/{pid}/vocabulaire")
def proposer(request: Request, background: BackgroundTasks, pid: str):
    """Fait proposer la progression de vocabulaire, à faire valider ensuite."""
    admin_requis(request)
    projet = store.get_project(pid)
    if not projet or projet["kind"] != "generation":
        raise HTTPException(404, "unknown book to produce")
    generation_possible()
    if not (workspace.workspace(pid) / "content" / "plan.json").exists():
        raise HTTPException(409, "the plan must be built first")
    store.set_status(pid, "running", step="proposing the progression")
    background.add_task(lancer_vocabulaire, pid, projet["langue"], projet["name"])
    return {"id": pid, "estimation": estimations(pid)["vocabulaire"]}


def lancer_validation(pid, langue, nom):
    store.set_status(pid, "running", step="applying the teacher's decisions")
    try:
        ok, journal = workspace.valider_vocabulaire(pid, langue, nom,
                                                    store.for_replay(pid))
    except Exception as e:
        store.set_status(pid, "failed", log=f"{type(e).__name__}: {e}")
        return
    impose = workspace.vocabulaire_du_plan(pid)
    store.set_status(pid, "ready" if ok else "failed",
                     log=journal + f"\n{impose} entrées imposées au plan")
    if ok:
        store.set_phase(pid, "vocabulaire_valide")


@app.post("/admin/projects/{pid}/vocabulaire/valider")
def valider_vocabulaire(request: Request, background: BackgroundTasks, pid: str):
    """Verse les décisions du professeur dans le plan. Gratuit et instantané."""
    admin_requis(request)
    projet = store.get_project(pid)
    if not projet or projet["kind"] != "generation":
        raise HTTPException(404, "unknown book to produce")
    if not (workspace.workspace(pid) / "content" / "vocabulaire_propose.json").exists():
        raise HTTPException(409, "the progression must be proposed first")
    store.set_status(pid, "running", step="applying the teacher's decisions")
    background.add_task(lancer_validation, pid, projet["langue"], projet["name"])
    return {"id": pid}


def lancer_generation(pid, langue, nom):
    """Génère les leçons restantes. Reprenable : on ne refait que ce qui manque."""
    titres = workspace.titres_du_plan(pid)
    store.declarer_lecons(pid, titres)
    a_faire = [l["n"] for l in store.lecons(pid) if l["etat"] != "faite"]
    store.set_status(pid, "running", step=f"{len(a_faire)} lessons to write")
    store.set_phase(pid, "generation")

    def sur_lecon(n, etat, entree, sortie, erreur):
        store.set_lecon(pid, n, etat, entree, sortie, erreur)
        av = store.avancement(pid)
        store.set_status(pid, "running",
                         step=f"lesson {n} — {av['faites']}/{av['total']} written")

    try:
        arret = workspace.generer_lecons(pid, langue, nom, a_faire, sur_lecon)
    except Exception as e:
        store.set_status(pid, "failed", log=f"{type(e).__name__}: {e}")
        return
    av = store.avancement(pid)
    journal = f"{av['faites']}/{av['total']} lessons written"
    if arret:
        journal += f" — stopped early: {arret}"
    elif av["echecs"]:
        journal += f", {av['echecs']} failure(s) — last: {av['erreur']}"
    # Un livre dont aucune leçon n'est écrite n'est pas « prêt ». Annoncer READY
    # sur trente et un échecs, c'est mentir à celui qui regarde la page.
    store.set_status(pid, "ready" if av["faites"] == av["total"] else "failed",
                     log=journal)


@app.post("/admin/projects/{pid}/generer-lecons")
def ecrire_lecons(request: Request, background: BackgroundTasks, pid: str):
    """Écrit les leçons du livre. Relancer reprend là où ça s'est arrêté."""
    admin_requis(request)
    projet = store.get_project(pid)
    if not projet or projet["kind"] != "generation":
        raise HTTPException(404, "unknown book to produce")
    generation_possible()
    if not workspace.titres_du_plan(pid):
        raise HTTPException(409, "the plan must be built first")
    # Sans vocabulaire imposé, le modèle choisit ce qu'il enseigne — et, quand la
    # référence est dans une autre langue, il n'a aucun ancrage dans la langue
    # cible. Un livre entier de chinois a été écrit ainsi pour un titre japonais.
    if not workspace.vocabulaire_du_plan(pid):
        raise HTTPException(409, "approve the vocabulary progression first — it is "
                                 "what tells the lessons which words to teach")
    store.set_status(pid, "running", step="preparing")
    background.add_task(lancer_generation, pid, projet["langue"], projet["name"])
    return {"id": pid, "estimation": estimations(pid)["generation"]}


def lancer_assemblage(pid, langue, nom):
    store.set_status(pid, "running", step="assembling and building")
    store.set_phase(pid, "assemblage")
    try:
        ok, journal = workspace.assembler(pid, langue, nom)
    except Exception as e:
        store.set_status(pid, "failed", log=f"{type(e).__name__}: {e}")
        return
    store.set_status(pid, "ready" if ok else "failed", log=journal)
    if ok:
        store.set_phase(pid, "pret")
        deposer_sur_drive(pid)


@app.post("/admin/projects/{pid}/assembler")
def assembler_livre(request: Request, background: BackgroundTasks, pid: str):
    """Assemble les leçons écrites en un livre, et refait les files de relecture."""
    admin_requis(request)
    projet = store.get_project(pid)
    if not projet or projet["kind"] != "generation":
        raise HTTPException(404, "unknown book to produce")
    av = store.avancement(pid)
    if not av or not av["faites"]:
        raise HTTPException(409, "no lesson has been written yet")
    store.set_status(pid, "running", step="assembling")
    background.add_task(lancer_assemblage, pid, projet["langue"], projet["name"])
    return {"id": pid, "lecons": av["faites"]}


@app.get("/admin/projects/{pid}/lecons")
def etat_lecons(request: Request, pid: str):
    admin_requis(request)
    return store.lecons(pid)


@app.post("/admin/projects/{pid}/drive")
async def definir_drive(request: Request, pid: str):
    """Le manager colle l'URL du dossier Drive du projet."""
    admin_requis(request)
    if not store.get_project(pid):
        raise HTTPException(404)
    corps = await request.json()
    dossier = drive.dossier_id(corps.get("folder"))
    if corps.get("folder") and not dossier:
        raise HTTPException(400, "this does not look like a Drive folder link")
    store.set_drive(pid, folder=dossier)
    store.set_drive(pid, state="")
    if dossier:
        deposer_sur_drive(pid)
    return {"folder": dossier, "state": store.get_project(pid)["drive_state"]}


@app.post("/admin/projects/{pid}/recompile")
def recompiler(request: Request, background: BackgroundTasks, pid: str):
    """Recompile avec les décisions prises depuis la dernière fois."""
    admin_requis(request)
    projet = store.get_project(pid)
    if not projet:
        raise HTTPException(404)
    entrees = sorted((workspace.workspace(pid) / "input").glob("*.docx"))
    if not entrees:
        raise HTTPException(409, "the original manuscript is gone")
    store.set_status(pid, "running", step="1/7  docx → structure")
    background.add_task(compiler, pid, str(entrees[0]), projet["name"])
    return {"id": pid}


@app.post("/admin/projects/{pid}/rotate/{role}")
def renouveler(request: Request, pid: str, role: str):
    admin_requis(request)
    if role not in store.ROLES:
        raise HTTPException(404)
    jeton = store.rotate(pid, role)
    return {"url": f"{str(request.base_url).rstrip('/')}/r/{jeton}"}


@app.get("/admin/projects/{pid}/book.pdf")
def livre_admin(request: Request, pid: str):
    admin_requis(request)
    p = workspace.artifact(pid, "book.pdf")
    if not p:
        raise HTTPException(404)
    return FileResponse(p, media_type="application/pdf", filename=f"{pid}-book.pdf")


@app.get("/admin/projects/{pid}/reports/{nom}")
def rapport_admin(request: Request, pid: str, nom: str):
    admin_requis(request)
    if nom not in workspace.REPORTS:
        raise HTTPException(404)
    p = workspace.artifact(pid, nom)
    if not p:
        raise HTTPException(404)
    return FileResponse(p, media_type="text/plain; charset=utf-8")
