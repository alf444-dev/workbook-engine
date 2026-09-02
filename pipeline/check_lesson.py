#!/usr/bin/env python3
"""Contrôle de conformité d'une leçon : quotas, vocabulaire, répétitivité.

Ce qui est vérifiable par code ne doit pas être confié à un modèle (invariant 3).
Une leçon — générée ou écrite à la main — est confrontée ici à son plan, au
glossaire maître et à la voix maison.

Chaque règle est mesurée sur les 31 leçons du CN10 avant d'être retenue : un
contrôle qui recale des leçons écrites par des éditeurs et validées par un
professeur natif crie au loup, et ne sera plus lu (invariant 4).

    python3 pipeline/check_lesson.py             # tout le livre de référence
    python3 pipeline/check_lesson.py --lecon 5
"""
import argparse, json, re, sys
from collections import Counter

from lesson_profile import mots, parcours, texte_anglais, texte_cible
from pairs import RE_PAIR
from style import ngrams
import repetition

BOOK = "content/book_typed.json"
PLAN = "content/plan.json"
GLOSSAIRE = "content/glossary.json"
STYLE = "content/style.json"

from langue import SCRIPT as HANZI   # plage déclarée dans config/<langue>.json

CHAMPS = ("mots_prose", "tableaux", "dialogues", "repliques", "exercices",
          "caracteres_nouveaux", "sections")


def mesurer(ch):
    """Les mêmes grandeurs que lesson_profile, pour une leçon isolée."""
    c = Counter()
    for bloc, dans_exercice in parcours(ch.get("blocks", [])):
        t = bloc["type"]
        c["mots"] += mots(texte_anglais(bloc))
        if not dans_exercice and t in ("para", "h2", "h3", "minihead"):
            c["mots_prose"] += mots(texte_anglais(bloc))
        if t in ("h2", "h3"):
            c["sections"] += 1
        elif t == "table" and not dans_exercice:
            c["tableaux"] += 1
        elif t == "dialogue" and not dans_exercice:
            c["dialogues"] += 1
            c["repliques"] += len(bloc["items"])
        elif t == "dia_line" and not dans_exercice:
            c["repliques"] += 1
        elif t == "exercise":
            c["exercices"] += 1
    return c


def enseigne_dans(ch):
    """Caractères que **cette leçon** enseigne elle-même.

    Un exercice a le droit d'employer le vocabulaire que sa propre leçon vient
    de présenter — c'est même le but. Sans cette règle, une leçon générée qui
    respecte son quota de vocabulaire neuf serait signalée pour l'avoir employé.
    """
    vus = set()
    for bloc, _ in parcours(ch.get("blocks", [])):
        texte = str(texte_cible(bloc))
        source = "".join(z for z, _ in RE_PAIR.findall(texte))
        if bloc["type"] in ("table", "dia_line", "dialogue"):
            source += texte
        vus |= set(HANZI.findall(source))
    return vus


def enseignement(book):
    """Première **position dans le livre** où chaque caractère est enseigné.

    Attention : le livre a deux numérotations. Les leçons seules (1–31, celles
    que décrit le plan) et les leçons plus les histoires (1–36, l'ordre réel de
    lecture). Le vocabulaire s'acquiert dans l'ordre de lecture, les quotas se
    comparent au plan : confondre les deux fait passer tout le vocabulaire de
    fin de livre pour non enseigné. On indexe donc ici par position de lecture.

    Explicitement = dans une paire {zh}{py}, un tableau ou une réplique de
    dialogue — les endroits où le manuscrit présente un mot avec sa
    prononciation. Un caractère qui n'apparaît que dans un paragraphe de
    consigne n'a pas été enseigné : c'est ce qu'on cherche à repérer.

    Le contenu **interne aux exercices** compte comme enseignement : banques de
    mots et textes de compréhension présentent réellement le vocabulaire. Mesuré
    sur le CN10 : l'exclure ferait passer le taux de signalement de 6 % à 29 %
    des leçons d'un livre validé — la règle crierait au loup (invariant 4).
    """
    premiere = {}
    n = 0
    for ch in book["chapters"]:
        if ch["kind"] not in ("chapter", "story"):
            continue
        n += 1
        for bloc, _ in parcours(ch.get("blocks", [])):
            texte = str(texte_cible(bloc))
            source = "".join(z for z, _ in RE_PAIR.findall(texte))
            if bloc["type"] == "table":
                source += texte
            if bloc["type"] in ("dia_line", "dialogue"):
                source += texte
            for c in HANZI.findall(source):
                premiere.setdefault(c, n)
    return premiere


def controler(ch, n, lu, plan, premiere, seuil_repetition, catalogue, apparition,
              serre=None, precedentes=None, seuil_reprise=None):
    """`n` est le rang dans le plan, `lu` la position dans l'ordre de lecture."""
    """Rend la liste des remarques sur une leçon."""
    remarques = []
    enseignes_ici = enseigne_dans(ch)
    mesures = mesurer(ch)

    # Caractères que cette leçon introduit : ceux que le **livre de référence**
    # n'avait pas encore montrés à ce stade. Les compter sur le livre où l'on
    # vient d'insérer une leçon générée serait circulaire — son propre
    # vocabulaire passerait pour acquis et le contrôle ne dirait plus rien.
    vus = set()
    for bloc, _ in parcours(ch.get("blocks", [])):
        vus |= set(HANZI.findall(str(texte_cible(bloc))))
    mesures["caracteres_nouveaux"] = sum(
        1 for c in vus if apparition.get(c, 10 ** 6) >= lu)
    quotas = plan["lecons"][n - 1]["quotas"] if n <= len(plan["lecons"]) else {}

    for champ in CHAMPS:
        if champ not in quotas:
            continue
        valeur = mesures.get(champ, 0)
        q = quotas[champ]
        if serre:
            # Deux usages, deux bandes. Sur du contenu humain la bande est
            # l'étendue du livre : assez large pour ne pas recaler ses auteurs.
            # Sur du contenu généré on veut savoir s'il vise la cible : une
            # leçon à 5 tableaux pour 11 attendus passe la bande large sans
            # être acceptable.
            bas = max(q["min"], int(q["cible"] * (1 - serre)))
            haut = min(q["max"], max(1, round(q["cible"] * (1 + serre))))
        else:
            bas, haut = q["min"], q["max"]
        if not (bas <= valeur <= haut):
            remarques.append(("quota", f"{champ} : {valeur} hors de {bas}–{haut}"))

    # vocabulaire employé dans les exercices sans avoir été enseigné avant
    for bloc, dans_exercice in parcours(ch.get("blocks", [])):
        if dans_exercice or bloc["type"] != "exercise":
            continue
        vus = set()
        for interne, _ in parcours(bloc.get("blocks", [])):
            vus |= set(HANZI.findall(str(texte_cible(interne))))
        for a in bloc.get("answers") or []:
            vus |= set(HANZI.findall(str(a.get("text", ""))))
        jamais = sorted(c for c in vus
                        if premiere.get(c, 10 ** 6) > lu and c not in enseignes_ici)
        if jamais:
            remarques.append(("vocabulaire",
                              f"{bloc.get('title', 'exercice')} emploie "
                              f"{len(jamais)} caractère(s) non enseignés : {''.join(jamais[:8])}"))

    # répétitivité interne, comparée à ce que se permet le livre humain
    interne = Counter()
    for bloc, _ in parcours(ch.get("blocks", [])):
        interne.update(ngrams(texte_anglais(bloc)))
    repetes = sum(1 for g, k in interne.items() if k >= 3)
    part = repetes / max(1, len(interne))
    if part > seuil_repetition:
        remarques.append(("repetition",
                          f"{part:.1%} des suites de 5 mots répétées 3 fois ou plus "
                          f"(seuil {seuil_repetition:.1%})"))

    # répétition d'une leçon à l'autre : la plainte n°1 sur le contenu généré.
    # Mesurée sur la prose seule, contre les leçons qui précèdent dans l'ordre
    # de lecture, avec pour seuil le pire du livre humain (voir repetition.py).
    if precedentes is not None and seuil_reprise is not None:
        part = repetition.part_reprise(ch, precedentes)
        if part > seuil_reprise:
            remarques.append(("reprise",
                              f"{part:.1%} de la prose reprend des tournures des leçons "
                              f"précédentes (seuil {seuil_reprise:.1%})"))

    # exercices : type conforme au plan, et réponses présentes
    # On vérifie que le type existe au catalogue, pas qu'il corresponde à la
    # case du plan : le plan répartit les types sur le livre, il ne prétend pas
    # dire lequel va dans quelle leçon.
    reels = {b.get("ex_type") for b, d in parcours(ch.get("blocks", []))
             if b["type"] == "exercise" and not d}
    inconnus = sorted(t for t in reels if t and t not in catalogue)
    if inconnus:
        remarques.append(("exercices", f"types hors catalogue : {inconnus}"))
    for bloc, d in parcours(ch.get("blocks", [])):
        if bloc["type"] == "exercise" and not d and bloc.get("ex_type") != "open_ended" \
                and not bloc.get("answers"):
            remarques.append(("reponses", f"{bloc.get('title', 'exercice')} sans réponses"))

    return remarques


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lecon", type=int, default=None)
    ap.add_argument("--serre", nargs="?", const=0.35, type=float, default=None,
                    help="bande resserrée autour de la cible (défaut 0.35) : "
                         "pour du contenu généré, qui doit viser la cible et pas "
                         "seulement rester dans l'étendue humaine")
    ap.add_argument("--glossaire", default=GLOSSAIRE,
                    help="glossaire de référence ; celui du livre généré permet "
                         "de mesurer sa cohérence interne")
    ap.add_argument("--livre", default=BOOK,
                    help="livre à contrôler ; par défaut celui du manuscrit")
    ap.add_argument("--seuil-repetition", type=float, default=None,
                    help="part maximale de suites répétées ; par défaut, le pire "
                         "que se permet le livre de référence")
    a = ap.parse_args()

    book = json.load(open(a.livre))
    plan = json.load(open(PLAN))
    style = json.load(open(STYLE))
    # Le vocabulaire disponible vient du livre de référence, sauf si l'on
    # fournit explicitement le glossaire du livre contrôlé : dans ce cas on
    # mesure sa cohérence avec lui-même.
    autonome = a.glossaire != GLOSSAIRE
    premiere = enseignement(book if (a.livre == BOOK or autonome) else json.load(open(BOOK)))
    # Première apparition de chaque caractère dans le livre de référence.
    apparition = json.load(open(a.glossaire))["caracteres"]
    catalogue = set(json.load(open("config/chinese.json"))["types_exercices"]["actifs"])

    # Le plan ne décrit que les leçons. Les histoires ont une tout autre forme
    # (peu de prose, pas de tableaux) : les confronter aux quotas d'une leçon
    # produisait un décalage d'index et des dizaines de fausses alertes.
    lecons = [ch for ch in book["chapters"] if ch["kind"] == "chapter"]

    # Seuil de répétition : on ne l'invente pas, on prend le maximum observé
    # dans le livre validé, avec une marge. Sinon la règle recalerait ses auteurs.
    if a.seuil_repetition is None:
        parts = []
        for ch in lecons:
            interne = Counter()
            for bloc, _ in parcours(ch.get("blocks", [])):
                interne.update(ngrams(texte_anglais(bloc)))
            parts.append(sum(1 for g, k in interne.items() if k >= 3) / max(1, len(interne)))
        seuil = round(max(parts) * 1.2, 4)
        print(f"seuil de répétition déduit du livre : {seuil:.1%} "
              f"(pire leçon humaine {max(parts):.1%}, marge 20 %)\n")
    else:
        seuil = a.seuil_repetition

    # Seuil de reprise inter-leçons : déduit du livre de référence, jamais du
    # livre contrôlé (sinon un livre généré répétitif se donnerait son propre
    # seuil). Sur le livre de référence lui-même, aucune leçon ne le dépasse.
    reference = book if a.livre == BOOK else json.load(open(BOOK))
    lecture_ref = [c for c in reference["chapters"] if c["kind"] in ("chapter", "story")]
    seuil_reprise, pire = repetition.seuil_du_livre(lecture_ref)
    print(f"seuil de reprise inter-leçons déduit du livre : {seuil_reprise:.1%} "
          f"(pire leçon humaine {pire:.1%}, marge 20 %)\n")
    lecture = [c for c in book["chapters"] if c["kind"] in ("chapter", "story")]

    # rang dans le plan (leçons seules) → position de lecture (avec histoires)
    position = {}
    rang = 0
    for i, ch in enumerate(c for c in book["chapters"] if c["kind"] in ("chapter", "story")):
        if ch["kind"] == "chapter":
            rang += 1
            position[rang] = i + 1

    cibles = [a.lecon] if a.lecon else range(1, len(lecons) + 1)
    total = Counter()
    signalees = 0
    for n in cibles:
        ch = lecons[n - 1]
        remarques = controler(ch, n, position[n], plan, premiere, seuil, catalogue,
                              apparition, a.serre,
                              precedentes=lecture[:position[n] - 1],
                              seuil_reprise=seuil_reprise)
        total.update(r[0] for r in remarques)
        if remarques:
            signalees += 1
            print(f"  leçon {n} — {ch['title'][:50]}")
            for genre, message in remarques:
                print(f"      [{genre}] {message}")

    n_lecons = len(list(cibles))
    print(f"\n  {signalees}/{n_lecons} leçons du livre validé sont signalées "
          f"({signalees / max(1, n_lecons):.0%})")
    for genre, n in total.most_common():
        print(f"    {genre:<14} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
