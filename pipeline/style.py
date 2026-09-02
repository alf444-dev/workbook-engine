#!/usr/bin/env python3
"""Exemples de style : la voix maison, extraite du livre déjà validé.

Le CN10 est passé par les éditeurs *et* par le professeur natif. Ce travail de
réécriture est aujourd'hui jeté à chaque titre ; ici il devient l'entrée du
modèle : consignes d'exercices, paragraphes d'explication types, tournures
récurrentes.

Le fichier sert aussi de **base de comparaison pour la répétitivité**. Un livre
humain répète : on mesure combien, pour ne pas signaler comme robotique une
leçon qui répète moins qu'un éditeur.

    python3 pipeline/style.py     → content/style.json + style_report.txt
"""
import json, os, re, statistics
from collections import Counter, defaultdict

from lesson_profile import mots, parcours, texte_anglais

BOOK = "content/book_typed.json"
OUT = "content/style.json"
RAPPORT = "style_report.txt"

TAILLE_NGRAM = 5
PARAGRAPHES_GARDES = 10

RE_MOT = re.compile(r"[A-Za-z][A-Za-z'’-]*")
from langue import DIACRITIQUES, PLAGE

RE_BALISE = re.compile(r"\{(?:zh|py):[^}]*\}|\{br\}|[" + PLAGE + "]")

# La romanisation qui traîne hors des balises {py:} porte ses diacritiques.
# Sans ce filtre, « jīntiān hěn hǎo » se découpe en « j nti n h n » et vient
# polluer la mesure de répétition : la tournure la plus « réutilisée » du livre
# était du pinyin. Les signes dépendent de la langue, d'où la config.
TONS = DIACRITIQUES
RE_JETON = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", re.UNICODE)


def anglais(texte):
    return RE_BALISE.sub(" ", str(texte))


def jetons_anglais(texte):
    return [j.lower() for j in RE_JETON.findall(anglais(texte))
            if not (TONS & set(j.lower()))]


def ngrams(texte, taille=TAILLE_NGRAM):
    jetons = jetons_anglais(texte)
    return [" ".join(jetons[i:i + taille]) for i in range(len(jetons) - taille + 1)]


def extraire(book):
    consignes = defaultdict(list)
    tailles = defaultdict(list)
    paragraphes = []
    titres = []
    compteur = Counter()

    for ch in book["chapters"]:
        if ch["kind"] not in ("chapter", "story"):
            continue
        for bloc, dans_exercice in parcours(ch.get("blocks", [])):
            t = bloc["type"]
            if t == "exercise":
                consigne = next((anglais(b.get("text", "")).strip()
                                 for b in bloc.get("blocks", [])
                                 if b["type"] == "para" and b.get("text", "").strip()), "")
                genre = bloc.get("ex_type") or "?"
                consignes[genre].append(
                    {"titre": bloc.get("title", "").strip(), "consigne": consigne[:200]})
                # Combien de questions par exercice. Le CN10 fait 5 appariements
                # à chaque fois, sans exception ; le générateur en produisait
                # 6 à 10, ce que rien ne lui disait. C'est une mesure, pas une
                # préférence : elle appartient au brief comme les quotas.
                d = bloc.get("data") or {}
                n = len(d.get("col_a") or d.get("items") or [])
                if n:
                    tailles[genre].append(n)
            elif t in ("h2", "h3") and not dans_exercice:
                titres.append(anglais(bloc.get("text", "")).strip())
            elif t == "para" and not dans_exercice:
                texte = anglais(bloc.get("text", "")).strip()
                if mots(bloc.get("text", "")) >= 25:
                    paragraphes.append({"lecon": ch["title"], "texte": texte})
            compteur.update(ngrams(texte_anglais(bloc)))

    return consignes, tailles, paragraphes, titres, compteur


def main():
    book = json.load(open(BOOK))
    consignes, tailles, paragraphes, titres, compteur = extraire(book)

    # Paragraphes représentatifs : ceux dont la longueur est la plus proche de
    # la médiane. Un exemple de style doit être typique, pas remarquable.
    longueurs = [len(RE_MOT.findall(p["texte"])) for p in paragraphes]
    mediane = statistics.median(longueurs) if longueurs else 0
    representatifs = sorted(paragraphes,
                            key=lambda p: abs(len(RE_MOT.findall(p["texte"])) - mediane)
                            )[:PARAGRAPHES_GARDES]

    repetes = {g: n for g, n in compteur.items() if n >= 3}
    occurrences = sorted(repetes.values(), reverse=True)

    style = {
        "consignes": {k: v for k, v in sorted(consignes.items())},
        "paragraphes_types": representatifs,
        "titres_de_section": titres[:60],
        "questions_par_exercice": {
            genre: {"median": int(statistics.median(n)), "min": min(n), "max": max(n),
                    "exercices": len(n)}
            for genre, n in sorted(tailles.items())},
        "repetition_humaine": {
            "_lecture": "Ce que se permet un livre écrit par des éditeurs et relu par "
                        "un professeur. Toute règle anti-répétitivité doit se comparer "
                        "à ces chiffres avant de signaler quoi que ce soit.",
            "taille_ngram": TAILLE_NGRAM,
            "ngrams_distincts": len(compteur),
            "ngrams_repetes": len(repetes),
            "part_repetee": round(len(repetes) / max(1, len(compteur)), 3),
            "max_occurrences": occurrences[0] if occurrences else 0,
            "mediane_des_repetes": int(statistics.median(occurrences)) if occurrences else 0,
            "les_plus_frequents": Counter(repetes).most_common(15),
        },
    }
    os.makedirs("content", exist_ok=True)
    json.dump(style, open(OUT, "w"), ensure_ascii=False, indent=1)

    r = style["repetition_humaine"]
    lignes = ["VOIX MAISON — EXEMPLES DE STYLE", "=" * 66,
              f"  {sum(len(v) for v in consignes.values())} consignes d'exercices, "
              f"{len(representatifs)} paragraphes types, {len(titres)} titres de section", "",
              "  répétition dans le livre humain :",
              f"    suites de {TAILLE_NGRAM} mots distinctes   {r['ngrams_distincts']}",
              f"    dont répétées 3 fois ou plus     {r['ngrams_repetes']}  "
              f"({r['part_repetee']:.1%})",
              f"    répétition maximale              {r['max_occurrences']} fois", "",
              "  tournures les plus réutilisées :"]
    for g, n in r["les_plus_frequents"][:8]:
        lignes.append(f"    {n:>3}×  « {g} »")
    lignes += ["", "  consignes par type d'exercice :"]
    for typ, liste in sorted(consignes.items()):
        lignes.append(f"    {typ} ({len(liste)}) :")
        for c in liste[:2]:
            lignes.append(f"       {c['titre']} — {c['consigne'][:90]}")
    open(RAPPORT, "w").write("\n".join(lignes) + "\n")
    print(f"style : {sum(len(v) for v in consignes.values())} consignes, "
          f"{r['ngrams_repetes']} tournures répétées  → {OUT}")


if __name__ == "__main__":
    main()
