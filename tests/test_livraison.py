#!/usr/bin/env python3
"""Dépôt dans le Drive de l'équipe, et sauvegarde de data/.

L'API Drive est remplacée par une doublure : ces tests vérifient ce qu'on lui
demande, pas Google. Le dépôt réel demande un compte de service et un dossier
partagé avec lui — voir docs/DEPLOIEMENT.md.

    python3 tests/test_livraison.py
"""
import json, os, sys, tarfile, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="wb-livraison-"))
os.environ["WB_DATA"] = str(TMP)
sys.path.insert(0, str(REPO / "server"))

import backup, drive, store        # noqa: E402

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


# ---------------------------------------------------------------- doublure Drive
class Appel:
    def __init__(self, journal, quoi, kw, resultat):
        journal.append((quoi, kw))
        self.resultat = resultat

    def execute(self):
        return self.resultat


class FauxFichiers:
    def __init__(self, journal, existants):
        self.journal, self.existants = journal, existants

    def list(self, **kw):
        nom = kw["q"].split("'")[1]
        trouve = [{"id": self.existants[nom]}] if nom in self.existants else []
        return Appel(self.journal, "list", kw, {"files": trouve})

    def create(self, **kw):
        return Appel(self.journal, "create", kw, {"id": "neuf"})

    def update(self, **kw):
        return Appel(self.journal, "update", kw, {"id": kw["fileId"]})


def doublure(existants=None):
    journal = []
    fichiers = FauxFichiers(journal, existants or {})
    drive._service = lambda: type("S", (), {"files": lambda self: fichiers})()
    return journal


def fichier(nom, contenu=b"x"):
    p = TMP / nom
    p.write_bytes(contenu)
    return p


# ---------------------------------------------------------------- non configuré
os.environ.pop("WB_DRIVE_CREDENTIALS", None)
os.environ.pop("WB_DRIVE_CREDENTIALS_FILE", None)
ok("sans identifiants, le dépôt Drive est inactif", not drive.configure())
journal = doublure()
ok("et il ne fait rien plutôt que d'échouer",
   drive.deposer("dossier123456", [fichier("book.pdf")]) == [] and journal == [])

os.environ["WB_DRIVE_CREDENTIALS"] = json.dumps({"type": "service_account"})
ok("avec identifiants, il s'active", drive.configure())

# ---------------------------------------------------------------- lecture du lien collé
ok("un lien de dossier collé est compris",
   drive.dossier_id("https://drive.google.com/drive/folders/1AbC_dEfGhIjKlMnOpQr?usp=sharing")
   == "1AbC_dEfGhIjKlMnOpQr")
ok("un lien qui n'est pas un dossier Drive est rejeté",
   drive.dossier_id("https://exemple.fr/projets") == "")
ok("un dossier vide n'est pas confondu avec un identifiant", drive.dossier_id("") == "")

# ---------------------------------------------------------------- premier dépôt
journal = doublure()
deposes = drive.deposer("DOSSIER", [fichier("book.pdf"), fichier("validation_report.txt")])
crees = [kw for quoi, kw in journal if quoi == "create"]
ok("chaque fichier est créé dans le dossier du projet",
   deposes == ["book.pdf", "validation_report.txt"] and len(crees) == 2
   and all(kw["body"]["parents"] == ["DOSSIER"] for kw in crees),
   str(deposes))
ok("les Drive partagés sont pris en charge",
   all(kw.get("supportsAllDrives") for quoi, kw in journal if quoi != "list")
   and all(kw.get("includeItemsFromAllDrives") for quoi, kw in journal if quoi == "list"))

# ---------------------------------------------------------------- deuxième dépôt
journal = doublure({"book.pdf": "ancien"})
drive.deposer("DOSSIER", [fichier("book.pdf")])
quois = [quoi for quoi, _ in journal]
ok("un livre déjà présent est remplacé, pas dupliqué",
   "update" in quois and "create" not in quois, str(quois))
ok("c'est bien l'ancien fichier qui est mis à jour",
   [kw["fileId"] for quoi, kw in journal if quoi == "update"] == ["ancien"])

# ---------------------------------------------------------------- sauvegarde
store.init()
pid = store.create_project("Essai", "essai.docx")
entree = TMP / "projects" / pid / "input"
entree.mkdir(parents=True, exist_ok=True)
(entree / "essai.docx").write_bytes(b"PK\x03\x04 manuscrit")
store.record(pid, "pinyin-a", "teacher", "fix", "nǐ hǎo", "Wei", {"kind": "pinyin"})

archive = backup.archiver("2026-01-01")
with tarfile.open(archive) as t:
    noms = t.getnames()
ok("l'archive contient la base et les manuscrits",
   "workbooks.db" in noms and f"projects/{pid}/input/essai.docx" in noms, str(noms))
ok("elle ne contient pas les sorties, qui se régénèrent",
   not any("output" in n for n in noms))

with tarfile.open(archive) as t, tempfile.TemporaryDirectory() as tmp:
    t.extract("workbooks.db", tmp)
    import sqlite3
    cx = sqlite3.connect(Path(tmp) / "workbooks.db")
    n_proj = cx.execute("SELECT count(*) FROM projects").fetchone()[0]
    n_dec = cx.execute("SELECT count(*) FROM decisions").fetchone()[0]
ok("la base restaurée porte les projets et les décisions",
   n_proj == 1 and n_dec == 1, f"{n_proj} projets, {n_dec} décisions")

for jour in range(2, 8):
    backup.archiver(f"2026-01-0{jour}")
supprimees = backup.elaguer(garder=3)
restantes = sorted(p.name for p in (TMP / "backups").glob("*.tar.gz"))
ok("l'élagage ne garde que les archives récentes",
   supprimees == 4 and len(restantes) == 3
   and restantes[-1] == "workbook-2026-01-07.tar.gz", str(restantes))

import shutil                                        # noqa: E402
shutil.rmtree(TMP, ignore_errors=True)
rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
