#!/usr/bin/env python3
"""Sauvegarde quotidienne, dans le processus du serveur.

Pourquoi pas un Cron Job Render : un disque persistant ne se monte que sur un
seul service. Un cron séparé ne verrait pas les données à sauvegarder. Un fil
d'exécution dans le serveur, lui, a le disque sous la main.

Une archive posée sur le même disque protège d'une suppression ou d'une base
corrompue, **pas de la perte du disque**. C'est pourquoi le serveur expose aussi
l'archive au téléchargement, et la dépose dans le Drive quand il est configuré.
"""
import os
import threading
import time
import traceback

HEURE = int(os.environ.get("WB_BACKUP_HEURE", "3"))      # 3 h UTC
JOUR = 24 * 3600


def secondes_avant(heure=HEURE, maintenant=None):
    """Secondes jusqu'au prochain passage à `heure` UTC."""
    t = maintenant if maintenant is not None else time.time()
    jour = int(t // JOUR) * JOUR
    prochain = jour + heure * 3600
    if prochain <= t:
        prochain += JOUR
    return prochain - t


def sauvegarder(journal=print):
    """Une archive, l'élagage, et le dépôt Drive s'il est configuré."""
    import backup
    import drive
    cible = backup.archiver()
    supprimees = backup.elaguer()
    message = f"sauvegarde : {cible.name} ({cible.stat().st_size // 1024} Ko)"
    if supprimees:
        message += f", {supprimees} archive(s) élaguée(s)"
    dossier = os.environ.get("WB_DRIVE_BACKUP_FOLDER", "")
    if dossier and drive.configure():
        try:
            drive.deposer(drive.dossier_id(dossier), [cible])
            message += ", déposée dans le Drive"
        except Exception as e:
            message += f", dépôt Drive en échec : {type(e).__name__}"
    journal(message)
    return cible


def _boucle():
    while True:
        time.sleep(secondes_avant())
        try:
            sauvegarder()
        except Exception:
            # Une sauvegarde ratée ne doit pas tuer le fil : on réessaiera demain.
            traceback.print_exc()


def derniere_archive(dossier):
    archives = sorted(dossier.glob("workbook-*.tar.gz")) if dossier.exists() else []
    return archives[-1] if archives else None


def demarrer():
    """Lance le fil quotidien, et rattrape immédiatement une sauvegarde manquée.

    Un serveur redéployé plusieurs fois dans la journée ne doit pas attendre
    3 h du matin, et une archive vieille de deux jours veut dire que les
    redéploiements ont tué le fil avant son passage.
    """
    import store
    derniere = derniere_archive(store.DATA / "backups")
    age = time.time() - derniere.stat().st_mtime if derniere else None
    if age is None or age > JOUR:
        try:
            sauvegarder()
        except Exception:
            traceback.print_exc()
    threading.Thread(target=_boucle, daemon=True, name="sauvegarde").start()
