#!/usr/bin/env python3
"""Crée un projet depuis un manuscrit et imprime les liens de relecture.

En attendant le dépôt web (étape suivante), c'est ainsi qu'on met un projet en
ligne :

    python3 server/seed.py input/742_CN10_FINAL_Manuscript.docx --nom "Learn Chinese — CN10"
"""
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store, workspace

ETIQUETTE = {"teacher": "Professeur natif", "editor": "Éditeur",
             "manager": "Team manager", "vocab": "Vocabulaire (professeur)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("--nom", default=None, help="nom affiché du projet")
    ap.add_argument("--base", default="http://127.0.0.1:8000", help="URL publique du serveur")
    a = ap.parse_args()

    docx = Path(a.docx).resolve()
    if not docx.exists():
        sys.exit(f"manuscrit introuvable : {docx}")

    store.init()
    nom = a.nom or docx.stem.replace("_", " ")
    pid = store.create_project(nom, docx.name)
    print(f"projet {pid} — {nom}")

    store.set_status(pid, "running")
    ok, journal = workspace.run(pid, docx, nom,
                                on_step=lambda l: print("   ", l))
    store.set_status(pid, "ready" if ok else "failed", log=journal)
    if not ok:
        print(journal[-2000:])
        sys.exit("échec du pipeline")

    print("\nliens à distribuer :")
    for lien in sorted(store.links_for(pid), key=lambda l: l["role"]):
        print(f"  {ETIQUETTE[lien['role']]:<16} {a.base}/r/{lien['token']}")


if __name__ == "__main__":
    main()
