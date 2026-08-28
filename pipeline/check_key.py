#!/usr/bin/env python3
"""Vérifie que la clé de génération fonctionne, sans jamais l'afficher.

Interroge la liste des modèles : cet appel authentifie sans consommer de jetons,
donc il ne coûte rien. Aucun secret n'est imprimé — seulement s'il marche, et
les quatre derniers caractères pour distinguer deux clés si besoin.

    export ANTHROPIC_API_KEY=sk-ant-...
    python3 pipeline/check_key.py
"""
import os, sys


def main():
    try:
        import anthropic
    except ImportError:
        sys.exit("dépendance manquante : pip install anthropic")

    from env import charger
    charger()          # lit .env s'il existe ; l'environnement l'emporte toujours

    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        sys.exit("ANTHROPIC_API_KEY n'est pas dans l'environnement.\n"
                 "  Clé à créer sur https://platform.claude.com/settings/keys, puis,\n"
                 "  à la racine du dépôt, un fichier .env (ignoré par git) :\n"
                 "      ANTHROPIC_API_KEY=sk-ant-...")

    client = anthropic.Anthropic()          # lit l'environnement, rien n'est codé en dur
    try:
        modeles = list(client.models.list(limit=20))
    except anthropic.AuthenticationError:
        sys.exit("clé refusée (401). Vérifier qu'elle n'a pas expiré : l'expiration "
                 "est fixée à la création et ne se modifie pas.")
    except anthropic.PermissionDeniedError as e:
        sys.exit(f"clé valable mais accès refusé : {e}")
    except anthropic.APIConnectionError as e:
        sys.exit(f"impossible de joindre l'API : {e}")

    empreinte = (os.environ.get("ANTHROPIC_API_KEY") or "")[-4:]
    print(f"clé fonctionnelle (…{empreinte}) — {len(modeles)} modèles accessibles")
    for m in modeles[:6]:
        print(f"    {m.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
