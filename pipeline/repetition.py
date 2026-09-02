#!/usr/bin/env python3
"""Répétition d'une leçon à l'autre — la plainte n°1 sur le contenu généré.

Le contrôle de leçon mesurait la répétitivité *à l'intérieur* d'une leçon. Or
« très répétitif », chez les éditeurs, désigne les tournures qui reviennent de
leçon en leçon : « You don't need to… », « Take a look at… ». Un modèle qui
écrit chaque leçon à l'aveugle les reproduit, parce que rien ne lui dit ce qui
a déjà été écrit.

Deux usages, un seul calcul :

- `deja_employees(precedentes)` — ce qu'on donne au modèle **avant** d'écrire,
  pour qu'il l'évite (quelques centaines de jetons, contre 0,45 $ la leçon à
  refaire).
- `part_reprise(lecon, precedentes)` — ce qu'on mesure **après**, dans
  `check_lesson.py`.

Le seuil ne s'invente pas (invariant 4) : mesuré sur le CN10, la prose d'une
leçon humaine reprend au plus 6,0 % de ses suites de 5 mots aux leçons qui la
précèdent (médiane 0,6 %). On prend ce maximum avec 20 % de marge, calculé sur
le livre de référence à l'exécution — jamais codé en dur.

Seule la **prose** compte. Les en-têtes de tableaux (« Useful Phrases in
Chinese / What They Mean ») et les consignes d'exercices reviennent dans toutes
les leçons : c'est la voix maison, on *veut* qu'elle se répète.
"""
from collections import Counter

from lesson_profile import parcours, texte_anglais
from style import jetons_anglais, ngrams

PROSE = ("para", "minihead", "h2", "h3")
MARGE = 1.2


def prose_ngrams(ch):
    """Suites de 5 mots de la prose d'une leçon, hors tableaux et exercices."""
    c = Counter()
    for bloc, dans_exercice in parcours(ch.get("blocks", [])):
        if not dans_exercice and bloc["type"] in PROSE:
            c.update(ngrams(texte_anglais(bloc)))
    return c


def ouvertures(ch, longueur=4, minimum=8):
    """Premiers mots de chaque paragraphe de prose : c'est là que la
    répétition se voit. Les lignes courtes (« Pattern: … », amorces de
    dialogue) ne sont pas des paragraphes : on ne retient que ceux d'au moins
    `minimum` mots, et les marqueurs {zh}{py} sont retirés avant."""
    c = Counter()
    for bloc, dans_exercice in parcours(ch.get("blocks", [])):
        if not dans_exercice and bloc["type"] == "para":
            mots = jetons_anglais(texte_anglais(bloc))
            if len(mots) >= minimum:
                c[" ".join(mots[:longueur])] += 1
    return c


def deja_employees(precedentes, max_tournures=40, max_ouvertures=25):
    """Ce que les leçons précédentes ont déjà dit, pour que la suivante l'évite.

    On ne liste que ce qui revient dans **au moins deux** leçons : une tournure
    employée une fois n'est pas une manie, et la lister ferait gonfler le
    prompt sans rien apprendre au modèle.
    """
    if not precedentes:
        return {"tournures": [], "ouvertures": []}
    par_lecon = [set(prose_ngrams(ch)) for ch in precedentes]
    occ = Counter()
    for s in par_lecon:
        occ.update(s)
    tournures = [g for g, k in occ.most_common() if k >= 2][:max_tournures]

    ouv = Counter()
    for ch in precedentes:
        ouv.update(ouvertures(ch))
    debuts = [o for o, k in ouv.most_common() if k >= 2][:max_ouvertures]
    return {"tournures": tournures, "ouvertures": debuts}


def part_reprise(ch, precedentes):
    """Part des suites de 5 mots de la prose déjà présentes dans une leçon
    antérieure. 0 si la leçon est la première."""
    mienne = set(prose_ngrams(ch))
    if not mienne or not precedentes:
        return 0.0
    avant = set()
    for p in precedentes:
        avant |= set(prose_ngrams(p))
    return len(mienne & avant) / len(mienne)


def seuil_du_livre(lecons):
    """Le pire qu'une leçon humaine se permet, avec marge. `lecons` dans l'ordre
    de lecture."""
    parts = [part_reprise(ch, lecons[:i]) for i, ch in enumerate(lecons)]
    return round((max(parts) if parts else 0.0) * MARGE, 4), (max(parts) if parts else 0.0)


def formuler(deja):
    """Bloc de prompt, ou chaîne vide s'il n'y a rien à éviter."""
    if not deja["tournures"] and not deja["ouvertures"]:
        return ""
    lignes = ["TOURNURES DÉJÀ EMPLOYÉES DANS LES LEÇONS PRÉCÉDENTES — ne les réutilise pas",
              "  Les éditeurs jugent les livres « très répétitifs » quand chaque leçon reprend",
              "  les mêmes formules. Trouve d'autres façons de dire la même chose."]
    if deja["ouvertures"]:
        lignes.append("  Débuts de paragraphe à ne pas reprendre :")
        lignes += [f"    « {o}… »" for o in deja["ouvertures"]]
    if deja["tournures"]:
        lignes.append("  Suites de mots à ne pas reprendre :")
        lignes += [f"    « {t} »" for t in deja["tournures"]]
    return "\n".join(lignes) + "\n"
