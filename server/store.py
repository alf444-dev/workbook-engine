#!/usr/bin/env python3
"""Workbook Engine — stockage : projets, liens de relecture, décisions.

SQLite sur le disque persistant. Une seule instance de serveur, donc pas de
concurrence distribuée à gérer : WAL suffit pour six personnes en parallèle.

Les décisions sont un journal *append-only* : on n'écrase jamais une ligne.
L'état courant d'un item est sa dernière décision. C'est ce qui donne
l'historique (« qui a tranché quoi, quand ») sans travail supplémentaire, et ce
qui permettra de rejouer les décisions après chaque conversion du manuscrit.
"""
import json, os, re, secrets, sqlite3, time
from pathlib import Path

ROLES = ("teacher", "editor", "manager", "vocab")

DATA = Path(os.environ.get("WB_DATA") or Path(__file__).resolve().parent.parent / "data")
DB = DATA / "workbooks.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id         TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  source     TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status     TEXT NOT NULL,          -- pending | running | ready | failed
  step       TEXT,                   -- dernière étape annoncée par run.sh
  log        TEXT,
  drive_folder TEXT NOT NULL DEFAULT '',   -- dossier Drive du projet
  drive_state  TEXT NOT NULL DEFAULT '',   -- résultat du dernier dépôt
  kind       TEXT NOT NULL DEFAULT 'depot',   -- depot | generation
  langue     TEXT NOT NULL DEFAULT '',        -- config de langue, pour un livre généré
  reference  TEXT NOT NULL DEFAULT '',        -- projet dont on reprend les mesures
  phase      TEXT NOT NULL DEFAULT ''         -- où en est un livre généré
);
CREATE TABLE IF NOT EXISTS links (
  token      TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  role       TEXT NOT NULL,
  created_at TEXT NOT NULL,
  revoked_at TEXT
);
CREATE TABLE IF NOT EXISTS decisions (
  seq        INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL,
  item_id    TEXT NOT NULL,
  role       TEXT NOT NULL,
  action     TEXT NOT NULL,          -- ok | fix | skip
  value      TEXT NOT NULL DEFAULT '',
  reviewer   TEXT NOT NULL DEFAULT '',
  at         TEXT NOT NULL,
  context    TEXT NOT NULL DEFAULT '{}'   -- l'item tel qu'il était quand on a tranché
);
CREATE INDEX IF NOT EXISTS decisions_project ON decisions(project_id, item_id);
CREATE TABLE IF NOT EXISTS lecons (
  project_id TEXT NOT NULL,
  n          INTEGER NOT NULL,
  titre      TEXT NOT NULL DEFAULT '',
  etat       TEXT NOT NULL DEFAULT 'attente',  -- attente | en_cours | faite | echec
  entree     INTEGER NOT NULL DEFAULT 0,
  sortie     INTEGER NOT NULL DEFAULT 0,
  erreur     TEXT NOT NULL DEFAULT '',
  at         TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (project_id, n)
);
CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(DB, timeout=10)
    cx.row_factory = sqlite3.Row
    cx.execute("PRAGMA journal_mode=WAL")
    cx.execute("PRAGMA busy_timeout=5000")
    return cx


def init():
    with connect() as cx:
        cx.executescript(SCHEMA)
        # Bases créées avant l'ajout du contexte : on complète sans rien perdre.
        colonnes = {r["name"] for r in cx.execute("PRAGMA table_info(decisions)")}
        if "context" not in colonnes:
            cx.execute("ALTER TABLE decisions ADD COLUMN context TEXT NOT NULL DEFAULT '{}'")
        colonnes = {r["name"] for r in cx.execute("PRAGMA table_info(projects)")}
        for nom, defaut in (("kind", "depot"), ("langue", ""),
                            ("reference", ""), ("phase", "")):
            if nom not in colonnes:
                cx.execute(f"ALTER TABLE projects ADD COLUMN {nom} "
                           f"TEXT NOT NULL DEFAULT '{defaut}'")
        colonnes = {r["name"] for r in cx.execute("PRAGMA table_info(projects)")}
        for nom in ("drive_folder", "drive_state"):
            if nom not in colonnes:
                cx.execute(f"ALTER TABLE projects ADD COLUMN {nom} TEXT NOT NULL DEFAULT ''")
    admin_token()          # créé au premier démarrage


def setting(key, defaut=None):
    with connect() as cx:
        r = cx.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else defaut


def admin_token():
    """Le lien de dépôt. Fixé par WB_ADMIN_TOKEN au déploiement, sinon tiré au
    premier démarrage et conservé en base — il n'y a personne pour le gérer."""
    fixe = os.environ.get("WB_ADMIN_TOKEN")
    if fixe:
        return fixe
    jeton = setting("admin_token")
    if not jeton:
        jeton = secrets.token_urlsafe(16)
        with connect() as cx:
            cx.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_token', ?)",
                       (jeton,))
    return jeton


# ---------------------------------------------------------------- projets
def create_project(name, source, kind="depot", langue="", reference=""):
    pid = secrets.token_hex(4)
    with connect() as cx:
        cx.execute("INSERT INTO projects (id, name, source, created_at, status,"
                   " kind, langue, reference) VALUES (?,?,?,?,'pending',?,?,?)",
                   (pid, name, source, now(), kind, langue, reference))
        for role in ROLES:
            cx.execute("INSERT INTO links (token, project_id, role, created_at)"
                       " VALUES (?,?,?,?)",
                       (secrets.token_urlsafe(16), pid, role, now()))
    return pid


def get_project(pid):
    with connect() as cx:
        r = cx.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    return dict(r) if r else None


def list_projects():
    with connect() as cx:
        return [dict(r) for r in cx.execute(
            "SELECT * FROM projects ORDER BY created_at DESC")]


# Un traceback d'une bibliothèque HTTP recopie l'en-tête fautif, clé d'API
# comprise. Ce journal est affiché sur la page et conservé sur le disque : les
# secrets en sont retirés avant écriture, pas à l'affichage.
SECRETS = re.compile(r"sk-[A-Za-z0-9_\-]{12,}")


def masquer_secrets(texte):
    if not texte:
        return texte
    return SECRETS.sub(lambda m: m.group(0)[:10] + "…[masqué]", texte)


def nettoyer_secrets():
    """Masque les secrets déjà écrits. Le masquage à l'écriture est arrivé après
    qu'une clé se soit retrouvée dans un journal : elle est alors dans la base et
    dans les archives, et s'affiche sur la page tant qu'on ne la retire pas.
    Renvoie le nombre de journaux corrigés."""
    corriges = 0
    with connect() as cx:
        for pid, journal in cx.execute(
                "SELECT id, log FROM projects WHERE log IS NOT NULL").fetchall():
            propre = masquer_secrets(journal)
            if propre != journal:
                cx.execute("UPDATE projects SET log=? WHERE id=?", (propre, pid))
                corriges += 1
    return corriges


def set_status(pid, status, step=None, log=None):
    log = masquer_secrets(log)
    with connect() as cx:
        cx.execute("UPDATE projects SET status=?,"
                   " step=COALESCE(?, step), log=COALESCE(?, log) WHERE id=?",
                   (status, step, log, pid))


# Les phases d'un livre généré. Une seule avance à la fois, et la troisième
# attend un humain : le professeur natif peut mettre des jours à vider sa file.
PHASES = ("mesure", "plan", "vocabulaire_propose", "vocabulaire_valide",
          "generation", "assemblage", "pret")


def set_phase(pid, phase):
    with connect() as cx:
        cx.execute("UPDATE projects SET phase=? WHERE id=?", (phase, pid))


# ---------------------------------------------------------------- leçons générées
def declarer_lecons(pid, titres):
    """Inscrit les leçons à produire. Ne touche pas à celles déjà faites :
    c'est ce qui rend la génération reprenable après un redéploiement."""
    with connect() as cx:
        for i, titre in enumerate(titres, 1):
            cx.execute("INSERT OR IGNORE INTO lecons (project_id, n, titre, at)"
                       " VALUES (?,?,?,?)", (pid, i, titre, now()))


def set_lecon(pid, n, etat, entree=0, sortie=0, erreur=""):
    with connect() as cx:
        cx.execute("UPDATE lecons SET etat=?, entree=?, sortie=?, erreur=?, at=?"
                   " WHERE project_id=? AND n=?",
                   (etat, entree, sortie, erreur[:400], now(), pid, n))


def lecons(pid):
    with connect() as cx:
        return [dict(r) for r in cx.execute(
            "SELECT * FROM lecons WHERE project_id=? ORDER BY n", (pid,))]


def avancement(pid):
    """Où en est la génération, et ce qu'elle a coûté jusqu'ici."""
    rangs = lecons(pid)
    if not rangs:
        return None
    faites = [l for l in rangs if l["etat"] == "faite"]
    return {"total": len(rangs), "faites": len(faites),
            "echecs": sum(1 for l in rangs if l["etat"] == "echec"),
            "en_cours": [l["n"] for l in rangs if l["etat"] == "en_cours"],
            "entree": sum(l["entree"] for l in rangs),
            "sortie": sum(l["sortie"] for l in rangs)}


def set_drive(pid, folder="", state=None):
    with connect() as cx:
        if state is None:
            cx.execute("UPDATE projects SET drive_folder=? WHERE id=?", (folder, pid))
        else:
            cx.execute("UPDATE projects SET drive_state=? WHERE id=?", (state, pid))


# ---------------------------------------------------------------- liens
def links_for(pid):
    with connect() as cx:
        return [dict(r) for r in cx.execute(
            "SELECT * FROM links WHERE project_id=? AND revoked_at IS NULL", (pid,))]


def resolve_token(token):
    """Rend (project_id, role) si le jeton est valable, sinon None."""
    if not token:
        return None
    with connect() as cx:
        r = cx.execute("SELECT project_id, role FROM links"
                       " WHERE token=? AND revoked_at IS NULL", (token,)).fetchone()
    return (r["project_id"], r["role"]) if r else None


def revoke(token):
    with connect() as cx:
        cx.execute("UPDATE links SET revoked_at=? WHERE token=?", (now(), token))


def rotate(pid, role):
    """Révoque le lien d'un rôle et en émet un neuf — pour la fin d'une langue,
    quand le professeur externe change."""
    jeton = secrets.token_urlsafe(16)
    with connect() as cx:
        cx.execute("UPDATE links SET revoked_at=? WHERE project_id=? AND role=?"
                   " AND revoked_at IS NULL", (now(), pid, role))
        cx.execute("INSERT INTO links (token, project_id, role, created_at)"
                   " VALUES (?,?,?,?)", (jeton, pid, role, now()))
    return jeton


# ---------------------------------------------------------------- décisions
def record(pid, item_id, role, action, value, reviewer, context=None):
    """`context` fige l'item au moment de la décision : sa nature, la paire
    visée, son adresse dans le livre. Indispensable — une fois la correction
    appliquée, l'item sort de la file de relecture ; s'il fallait l'y relire
    pour rejouer la décision, la correction s'annulerait d'elle-même à la
    compilation suivante."""
    with connect() as cx:
        cur = cx.execute(
            "INSERT INTO decisions (project_id, item_id, role, action, value, reviewer, at, context)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (pid, item_id, role, action, value or "", reviewer or "", now(),
             json.dumps(context or {}, ensure_ascii=False)))
        return cur.lastrowid


def current(pid):
    """Dernière décision par item — l'état que voit la console."""
    with connect() as cx:
        rows = cx.execute("""
            SELECT d.item_id, d.action, d.value, d.reviewer, d.at, d.seq, d.context
            FROM decisions d
            JOIN (SELECT item_id, MAX(seq) AS m FROM decisions
                  WHERE project_id=? GROUP BY item_id) last
              ON d.item_id = last.item_id AND d.seq = last.m
            WHERE d.project_id=?""", (pid, pid)).fetchall()
    return {r["item_id"]: {"action": r["action"], "value": r["value"],
                           "by": r["reviewer"], "at": r["at"], "seq": r["seq"],
                           "context": r["context"]}
            for r in rows}


def for_replay(pid):
    """Les décisions telles que pipeline/decisions.py les attend."""
    sorties = []
    for item_id, d in current(pid).items():
        ctx = json.loads(d.get("context") or "{}")
        sorties.append({"item_id": item_id, "action": d["action"], "value": d["value"],
                        "by": d["by"], "at": d["at"], **ctx})
    return sorties


def history(pid, item_id):
    with connect() as cx:
        return [dict(r) for r in cx.execute(
            "SELECT * FROM decisions WHERE project_id=? AND item_id=? ORDER BY seq",
            (pid, item_id))]
