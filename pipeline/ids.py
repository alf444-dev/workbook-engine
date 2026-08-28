#!/usr/bin/env python3
"""Dérivation des identifiants d'items — une seule définition.

Les décisions des relecteurs sont stockées sous cette clé. Deux définitions qui
divergeraient feraient atterrir une correction sur une autre entrée que celle
que le professeur avait sous les yeux. Partagé par `bundle.py` (qui fabrique les
files) et `apply_vocab.py` (qui applique ce qui en revient).

Propriété garantie : même contenu ⇒ même id. Un contenu modifié fait
réapparaître l'item comme non traité — c'est le sens sûr de l'erreur.
"""
import hashlib
from collections import Counter

ID_SCHEME = 1


class Numeroteur:
    """Attribue les identifiants d'une exécution, doublons compris.

    Deux items de contenu identique reçoivent `x` puis `x-2`. L'ordre de
    parcours doit donc être le même partout — il l'est : leçons puis entrées.
    """

    def __init__(self):
        self.vus = Counter()

    def __call__(self, kind, lesson, title, detail):
        sig = "\x00".join(str(x) for x in (ID_SCHEME, kind, lesson or "", title, detail))
        base = f"{kind}-{hashlib.sha1(sig.encode()).hexdigest()[:10]}"
        self.vus[base] += 1
        n = self.vus[base]
        return base if n == 1 else f"{base}-{n}"
