#!/usr/bin/env python3
"""Sauvegarde de data/ — les manuscrits et les décisions.

Tout le reste se régénère : le livre, les rapports, les files de relecture sont
des sorties du pipeline. Ce qui ne se retrouve pas, c'est le manuscrit déposé et
le travail des relecteurs. C'est donc cela qu'on sauvegarde.

La base est copiée par l'API de sauvegarde de SQLite, pas par `cp` : en mode WAL,
copier le fichier pendant qu'un relecteur enregistre une décision donnerait une
archive incohérente.

    python3 server/backup.py                 # une archive dans data/backups/
    python3 server/backup.py --drive <id>    # et un dépôt dans un dossier Drive

À mettre en cron (par exemple 0 3 * * *).
"""
import argparse, os, sqlite3, sys, tarfile, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402

GARDER = 14          # deux semaines d'archives quotidiennes


def copier_base(vers):
    """Copie cohérente, même si le serveur écrit pendant ce temps."""
    src = sqlite3.connect(store.DB)
    dst = sqlite3.connect(vers)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()


def archiver(horodatage=None):
    horodatage = horodatage or time.strftime("%Y-%m-%d", time.gmtime())
    dossier = store.DATA / "backups"
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / f"workbook-{horodatage}.tar.gz"

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "workbooks.db"
        copier_base(base)
        with tarfile.open(cible, "w:gz") as tar:
            tar.add(base, arcname="workbooks.db")
            projets = store.DATA / "projects"
            for entree in sorted(projets.glob("*/input/*.docx")) if projets.exists() else []:
                tar.add(entree, arcname=str(entree.relative_to(store.DATA)))
    return cible


def elaguer(garder=GARDER):
    dossier = store.DATA / "backups"
    archives = sorted(dossier.glob("workbook-*.tar.gz"))
    perimees = archives[:-garder] if garder else []
    for a in perimees:
        a.unlink()
    return len(perimees)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive", default=os.environ.get("WB_DRIVE_BACKUP_FOLDER", ""),
                    help="dossier Drive où déposer l'archive")
    ap.add_argument("--garder", type=int, default=GARDER)
    a = ap.parse_args()

    cible = archiver()
    taille = cible.stat().st_size / 1024 / 1024
    print(f"archive : {cible}  ({taille:.1f} Mo)")
    supprimees = elaguer(a.garder)
    if supprimees:
        print(f"élagage : {supprimees} archive(s) plus ancienne(s) supprimée(s)")

    if a.drive:
        import drive as drv
        if not drv.configure():
            print("dépôt Drive demandé mais WB_DRIVE_CREDENTIALS est absent", file=sys.stderr)
            return
        drv.deposer(drv.dossier_id(a.drive), [cible])
        print(f"déposée dans le Drive ({a.drive})")


if __name__ == "__main__":
    main()
