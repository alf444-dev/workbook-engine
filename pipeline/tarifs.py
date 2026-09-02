#!/usr/bin/env python3
"""Ce que coûtent les modèles. Une seule table, lue par le moteur et le serveur.

Elle vit dans `pipeline/` et non dans `server/` parce qu'un espace de travail de
projet ne reçoit que le pipeline (`workspace.CODE`) : un script du moteur qui
importerait le serveur marcherait sur un poste de développement et tomberait en
production. `server/couts.py` lit cette table, jamais l'inverse.

Relevé le 2 septembre 2026 sur platform.claude.com/docs/en/about-claude/pricing.
À revérifier avant d'en tirer un budget : c'est une page qui bouge.
"""

# Dollars par million de jetons.
TARIFS = {
    "claude-opus-5":   {"entree": 5.0, "sortie": 25.0},
    "claude-sonnet-5": {"entree": 2.0, "sortie": 10.0},
    "claude-haiku-4-5-20251001": {"entree": 1.0, "sortie": 5.0},
}
MODELE_DEFAUT = "claude-opus-5"

# L'API Batch coûte moitié prix sur les deux dimensions, en asynchrone. Écrire
# un livre prend déjà 52 minutes et n'a rien d'urgent : c'est le seul levier qui
# divise la facture par deux sans toucher à ce qui est écrit. Pas encore
# branché — le chiffre est ici pour rester sous les yeux.
REMISE_BATCH = 0.5


def prix(modele=MODELE_DEFAUT):
    """Tarif d'un modèle, ou celui du modèle par défaut s'il est inconnu.

    Retomber sur le défaut plutôt que sur zéro : un tarif manquant doit faire
    surestimer la dépense, jamais annoncer qu'elle est gratuite.
    """
    return TARIFS.get(modele, TARIFS[MODELE_DEFAUT])


def cout(entree, sortie, modele=MODELE_DEFAUT, batch=False):
    """Dollars pour un nombre de jetons mesuré."""
    t = prix(modele)
    d = entree / 1e6 * t["entree"] + sortie / 1e6 * t["sortie"]
    return d * (REMISE_BATCH if batch else 1.0)
