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
import json, os, shutil, tempfile
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse

import couts, drive, store, workspace

REPO = Path(__file__).resolve().parent.parent
CONSOLE = REPO / "webapp" / "console.html"
ACTIONS = {"ok", "fix", "skip", "drop"}      # « drop » : entrée de vocabulaire écartée

app = FastAPI(title="Workbook Engine", docs_url=None, redoc_url=None, openapi_url=None)


@app.on_event("startup")
def _startup():
    store.init()


@app.middleware("http")
async def entetes(request: Request, call_next):
    r = await call_next(request)
    # Les manuscrits ne sont pas publics : ni indexation, ni fuite par le Referer.
    r.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    r.headers["Referrer-Policy"] = "no-referrer"
    r.headers["X-Content-Type-Options"] = "nosniff"
    return r


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return "User-agent: *\nDisallow: /\n"


@app.get("/")
def racine():
    raise HTTPException(404)


def cookie_name(pid, role):
    return f"wb_{pid}_{role}"


@app.get("/r/{token}")
def ouvrir(token: str):
    """Échange le jeton contre un cookie, puis sort le jeton de l'URL."""
    lien = store.resolve_token(token)
    if not lien:
        raise HTTPException(404, "lien inconnu ou révoqué")
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
        raise HTTPException(403, "lien absent ou révoqué — rouvrez le lien reçu")
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
        raise HTTPException(400, f"action inconnue : {action}")

    # Un rôle n'écrit que sur sa propre file : le lien du professeur ne permet
    # pas de trancher les corrigés du manager.
    chemin = workspace.artifact(pid, "review.json")
    if not chemin:
        raise HTTPException(503, "projet pas encore compilé")
    b = json.loads(chemin.read_text(encoding="utf-8"))
    item = next((i for i in b["items"] if i["id"] == item_id and i["queue"] == role), None)
    if item is None:
        raise HTTPException(404, "item absent de cette file")

    contexte = {c: item.get(c) for c in ("kind", "lesson", "zh", "pinyin", "target")}
    seq = store.record(pid, item_id, role, action,
                       str(corps.get("value") or "")[:2000],
                       str(corps.get("by") or "")[:80], contexte)
    return {"ok": True, "seq": seq}


@app.get("/p/{pid}/{role}/book.pdf")
def livre(request: Request, pid: str, role: str):
    autoriser(request, pid, role)
    if role != "manager":
        raise HTTPException(403, "le livre complet n'est pas dans cette file")
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
ETIQUETTE = {"teacher": "Professeur natif", "editor": "Éditeur",
             "manager": "Team manager", "vocab": "Vocabulaire (professeur)"}


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
        raise HTTPException(403, "lien de dépôt absent — rouvrez le lien reçu")


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
        out.append({"code": f.stem, "nom": c.get("langue", f.stem),
                    "public": c.get("public", "")})
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
        "reference": projet["reference"], "phase": projet["phase"],
        "vocabulaire": workspace.compter_vocabulaire(pid),
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
        d["error"] = lignes[-1].strip() if lignes else "cause inconnue"
        d["step"] = next((l for l in reversed(lignes) if len(l) > 3 and l[1] == "/"), None)
        d["log"] = journal[-4000:]
    return d


@app.get("/admin/projects")
def lister(request: Request):
    admin_requis(request)
    base = str(request.base_url).rstrip("/")
    return {"projets": [decrire(p, base) for p in store.list_projects()],
            "langues": langues_disponibles()}


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
        store.set_drive(pid, state=f"{len(deposes)} fichier(s) déposé(s) le {store.now()}")
    except Exception as e:
        store.set_drive(pid, state=f"échec du dépôt Drive : {type(e).__name__}: {e}"[:300])


@app.post("/admin/projects")
async def deposer(request: Request, background: BackgroundTasks,
                  file: UploadFile = File(...), name: str = Form("")):
    admin_requis(request)

    # Jamais le nom de fichier reçu : il sert d'affichage, pas de chemin.
    origine = Path(file.filename or "manuscrit.docx").name
    if not origine.lower().endswith(".docx"):
        raise HTTPException(400, "il faut un fichier .docx")

    tmp = Path(tempfile.mkdtemp(prefix="wb-upload-")) / "manuscrit.docx"
    taille = 0
    with tmp.open("wb") as f:
        while chunk := await file.read(1 << 20):
            taille += len(chunk)
            if taille > TAILLE_MAX:
                shutil.rmtree(tmp.parent, ignore_errors=True)
                raise HTTPException(413, "manuscrit trop lourd (40 Mo maximum)")
            f.write(chunk)
    if not workspace.est_docx(tmp):
        shutil.rmtree(tmp.parent, ignore_errors=True)
        raise HTTPException(400, "ce fichier n'est pas un document Word")

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
    store.set_status(pid, "running", step="préparation")
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
        raise HTTPException(404, "projet de référence inconnu")
    if reference["status"] != "ready":
        raise HTTPException(409, "le projet de référence doit être compilé d'abord")

    langue = str(corps.get("langue") or "")
    if langue not in {l["code"] for l in langues_disponibles()}:
        raise HTTPException(400, f"langue inconnue : {langue}")
    langue_reference = reference["langue"] or "chinese"

    nom = (corps.get("nom") or "").strip() or f"Livre {langue}"
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
        raise HTTPException(404, "pas encore de plan")
    plan = json.loads(chemin.read_text(encoding="utf-8"))
    return {"totaux": plan["totaux"],
            "lecons": [{"n": l["n"], "titre": l["titre"],
                        "exercices": l["exercices"],
                        "vocabulaire": len(l.get("vocabulaire") or []),
                        "caracteres": l["quotas"]["caracteres_nouveaux"]["cible"],
                        "mots_prose": l["quotas"]["mots_prose"]["cible"]}
                       for l in plan["lecons"]]}


def lancer_vocabulaire(pid, langue, nom):
    store.set_status(pid, "running", step="proposition de la progression")
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
        raise HTTPException(404, "livre à produire inconnu")
    if not (workspace.workspace(pid) / "content" / "plan.json").exists():
        raise HTTPException(409, "le plan doit être établi d'abord")
    store.set_status(pid, "running", step="proposition de la progression")
    background.add_task(lancer_vocabulaire, pid, projet["langue"], projet["name"])
    return {"id": pid, "estimation": estimations(pid)["vocabulaire"]}


def lancer_generation(pid, langue, nom):
    """Génère les leçons restantes. Reprenable : on ne refait que ce qui manque."""
    titres = workspace.titres_du_plan(pid)
    store.declarer_lecons(pid, titres)
    a_faire = [l["n"] for l in store.lecons(pid) if l["etat"] != "faite"]
    store.set_status(pid, "running", step=f"{len(a_faire)} leçons à écrire")
    store.set_phase(pid, "generation")

    def sur_lecon(n, etat, entree, sortie, erreur):
        store.set_lecon(pid, n, etat, entree, sortie, erreur)
        av = store.avancement(pid)
        store.set_status(pid, "running",
                         step=f"leçon {n} — {av['faites']}/{av['total']} écrites")

    try:
        workspace.generer_lecons(pid, langue, nom, a_faire, sur_lecon)
    except Exception as e:
        store.set_status(pid, "failed", log=f"{type(e).__name__}: {e}")
        return
    av = store.avancement(pid)
    store.set_status(pid, "ready",
                     log=f"{av['faites']}/{av['total']} leçons écrites, "
                         f"{av['echecs']} échec(s)")


@app.post("/admin/projects/{pid}/generer-lecons")
def ecrire_lecons(request: Request, background: BackgroundTasks, pid: str):
    """Écrit les leçons du livre. Relancer reprend là où ça s'est arrêté."""
    admin_requis(request)
    projet = store.get_project(pid)
    if not projet or projet["kind"] != "generation":
        raise HTTPException(404, "livre à produire inconnu")
    if not workspace.titres_du_plan(pid):
        raise HTTPException(409, "le plan doit être établi d'abord")
    store.set_status(pid, "running", step="préparation")
    background.add_task(lancer_generation, pid, projet["langue"], projet["name"])
    return {"id": pid, "estimation": estimations(pid)["generation"]}


def lancer_assemblage(pid, langue, nom):
    store.set_status(pid, "running", step="assemblage et compilation")
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
        raise HTTPException(404, "livre à produire inconnu")
    av = store.avancement(pid)
    if not av or not av["faites"]:
        raise HTTPException(409, "aucune leçon écrite")
    store.set_status(pid, "running", step="assemblage")
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
        raise HTTPException(400, "ce lien ne ressemble pas à un dossier Drive")
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
        raise HTTPException(409, "le manuscrit d'origine n'est plus là")
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
