#!/usr/bin/env python3
"""Dépôt du livre et des rapports dans le dossier Drive du projet.

On ne remplace pas le Drive de l'équipe, on s'y ajoute : après chaque
compilation réussie, le PDF et les rapports sont déposés dans le dossier du
projet, là où les fichiers sont déjà rangés.

Facultatif. Sans identifiants (`WB_DRIVE_CREDENTIALS`), tout ici ne fait rien
et le serveur fonctionne comme avant.

Mise en place côté Google : créer un compte de service, puis **partager le
dossier du projet avec son adresse e-mail** en accès éditeur. Aucun compte
utilisateur n'est demandé à qui que ce soit, et la portée est `drive.file` :
l'outil ne voit que les fichiers qu'il a lui-même déposés.
"""
import json, os, re

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

TYPES = {".pdf": "application/pdf", ".txt": "text/plain"}

# Un dossier Drive collé depuis la barre d'adresse, sous ses formes courantes.
RE_DOSSIER = re.compile(r"(?:folders/|[?&]id=)([A-Za-z0-9_-]{10,})")


def identifiants():
    """Le JSON du compte de service, depuis l'environnement ou un fichier."""
    brut = os.environ.get("WB_DRIVE_CREDENTIALS")
    if brut:
        return json.loads(brut)
    chemin = os.environ.get("WB_DRIVE_CREDENTIALS_FILE")
    if chemin and os.path.exists(chemin):
        return json.load(open(chemin))
    return None


def configure():
    return identifiants() is not None


def dossier_id(colle):
    """Rend l'identifiant d'un dossier à partir d'une URL collée, ou de l'id nu."""
    colle = (colle or "").strip()
    if not colle:
        return ""
    m = RE_DOSSIER.search(colle)
    if m:
        return m.group(1)
    return colle if re.fullmatch(r"[A-Za-z0-9_-]{10,}", colle) else ""


def _service():
    """Construit le client Drive. Remplacé par une doublure dans les tests."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_info(
        identifiants(), scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _media(chemin):
    from googleapiclient.http import MediaFileUpload
    suffixe = os.path.splitext(str(chemin))[1].lower()
    return MediaFileUpload(str(chemin), mimetype=TYPES.get(suffixe, "application/octet-stream"),
                           resumable=False)


def deposer(folder_id, fichiers):
    """Dépose (ou met à jour) chaque fichier dans le dossier. Rend la liste des noms.

    Un fichier du même nom déjà présent est **remplacé**, pas dupliqué : sans
    cela le dossier du projet se remplirait d'un book.pdf par compilation, et
    plus personne ne saurait lequel est le bon.
    """
    if not folder_id or not configure():
        return []
    service = _service()
    fichiers_api = service.files()
    deposes = []
    for chemin in fichiers:
        nom = os.path.basename(str(chemin))
        echappe = nom.replace("'", "\\'")
        existants = fichiers_api.list(
            q=f"name = '{echappe}' and '{folder_id}' in parents and trashed = false",
            fields="files(id)", pageSize=1,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute().get("files", [])
        if existants:
            fichiers_api.update(fileId=existants[0]["id"], media_body=_media(chemin),
                                supportsAllDrives=True).execute()
        else:
            fichiers_api.create(body={"name": nom, "parents": [folder_id]},
                                media_body=_media(chemin), fields="id",
                                supportsAllDrives=True).execute()
        deposes.append(nom)
    return deposes
