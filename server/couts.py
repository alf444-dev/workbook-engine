#!/usr/bin/env python3
"""Ce qu'une action va coûter, annoncé avant de la lancer.

Un bouton qui dépense sans le dire n'est pas acceptable dans un outil que
d'autres utiliseront. Les tarifs et les consommations viennent de mesures
réelles, pas d'estimations : elles sont datées, et à revoir quand le modèle ou
la tarification changent.
"""

# Tarif Claude Opus 5 au 24 juin 2026, en dollars par million de jetons.
# À vérifier sur la page tarifs d'Anthropic avant de s'y fier pour un budget.
PRIX_ENTREE = 5.0
PRIX_SORTIE = 25.0

# Consommations mesurées sur le CN10, août 2026.
MESURES = {
    # une proposition de progression complète, tous les niveaux en un appel
    "vocabulaire": {"entree": 2_300, "sortie": 28_500, "par_lecon": False,
                    "duree_s": 200},
    # une leçon générée, avec son glossaire et ses exemples de style en contexte
    "lecon": {"entree": 5_800, "sortie": 16_500, "par_lecon": True,
              "duree_s": 200},
}


def estimer(quoi, n_lecons=1, parallele=2):
    """Rend (dollars, secondes, phrase) pour une action à venir."""
    m = MESURES[quoi]
    facteur = n_lecons if m["par_lecon"] else 1
    entree = m["entree"] * facteur
    sortie = m["sortie"] * facteur
    dollars = entree / 1e6 * PRIX_ENTREE + sortie / 1e6 * PRIX_SORTIE
    secondes = m["duree_s"] * (facteur / max(1, parallele) if m["par_lecon"] else 1)
    return round(dollars, 2), int(secondes), phrase(dollars, secondes)


def phrase(dollars, secondes):
    """En anglais : l'application est lue par des relecteurs non francophones."""
    minutes = max(1, round(secondes / 60))
    duree = (f"{minutes} min" if minutes < 60
             else f"{minutes // 60} h {minutes % 60:02d}")
    return f"about ${dollars:.2f} and {duree}"
