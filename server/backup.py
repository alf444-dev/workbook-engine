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


def membres_surs(tar, vers):
    """Les entrées d'archive qui restent bien à l'intérieur du dossier visé.

    Une archive est un fichier qu'on reçoit : un chemin absolu ou un « .. » y
    écrirait n'importe où sur le disque. `tarfile` ne s'en protège pas seul
    avant Python 3.12, et la restauration doit marcher partout.
    """
    racine = vers.resolve()
    for membre in tar.getmembers():
        if not (membre.isfile() or membre.isdir()):
            continue                      # ni lien symbolique ni périphérique
        cible = (racine / membre.name).resolve()
        if cible == racine or racine in cible.parents:
            yield membre


def restaurer(archive, vers=None, ecraser=False):
    """Remet une archive en place. Rend la liste des fichiers restaurés.

    Refuse par défaut d'écraser une base existante : on restaure sur un disque
    vide ou après avoir mis l'ancienne de côté, jamais par-dessus des décisions
    qu'on n'a pas relues.
    """
    vers = Path(vers) if vers else store.DATA
    base = vers / "workbooks.db"
    if base.exists() and not ecraser:
        raise FileExistsError(
            f"{base} existe déjà : déplacer la base actuelle, ou passer ecraser=True")
    vers.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        membres = list(membres_surs(tar, vers))
        tar.extractall(vers, members=membres)
    return sorted(m.name for m in membres if m.isfile())


def elaguer(garder=GARDER):
    dossier = store.DATA / "backups"
    archives = sorted(dossier.glob("workbook-*.tar.gz"))
    perimees = archives[:-garder] if garder else []
    for a in perimees:
        a.unlink()
    return len(perimees)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--restaurer", metavar="ARCHIVE",
                    help="remet une archive en place dans WB_DATA")
    ap.add_argument("--ecraser", action="store_true",
                    help="autorise l'écrasement d'une base existante")
    ap.add_argument("--drive", default=os.environ.get("WB_DRIVE_BACKUP_FOLDER", ""),
                    help="dossier Drive où déposer l'archive")
    ap.add_argument("--garder", type=int, default=GARDER)
    a = ap.parse_args()

    if a.restaurer:
        fichiers = restaurer(a.restaurer, ecraser=a.ecraser)
        print(f"{len(fichiers)} fichiers restaurés dans {store.DATA}")
        for f in fichiers[:10]:
            print(f"  {f}")
        return 0

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
