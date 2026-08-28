#!/usr/bin/env python3
"""Profil pédagogique d'un livre existant, mesuré et non deviné.

La config d'une langue doit décrire ce que sont réellement les livres validés,
pas ce qu'on imagine qu'ils sont. Ce script lit un manuscrit déjà passé par les
éditeurs et le professeur, et en sort les quotas leçon par leçon : volume,
structure, exercices, vocabulaire nouveau.

C'est cette mesure qui devient le cahier des charges de la génération. Elle sert
aussi de garde-fou : une leçon générée hors de ces bornes est signalée avant
d'arriver à un humain.

    python3 pipeline/lesson_profile.py     → content/profile.json + profile_report.txt
"""
import json, os, re, statistics
from collections import Counter

from pairs import RE_PAIR, plain

BOOK = "content/book_typed.json"
OUT = "content/profile.json"
RAPPORT = "profile_report.txt"

from langue import SCRIPT as HANZI   # plage déclarée dans config/<langue>.json


RE_ZH = re.compile(r"\{zh:[^}]*\}")
RE_PY = re.compile(r"\{py:[^}]*\}")


def mots(texte):
    """Compte les mots **anglais**.

    Le pinyin s'écrit en caractères latins : le compter comme de l'anglais
    double le volume mesuré et fausserait tous les quotas de génération.
    """
    t = RE_PY.sub(" ", RE_ZH.sub(" ", str(texte)))
    t = HANZI.sub(" ", t).replace("{br}", " ")
    return len(re.findall(r"[A-Za-z][A-Za-z'’-]*", t))


def hanzi_de(texte):
    """Les suites de caractères chinois d'un texte — le vocabulaire vu."""
    return HANZI.findall(str(texte))


def parcours(blocs):
    """Rend chaque bloc, exercices dépliés, avec sa profondeur d'exercice."""
    for b in blocs:
        yield b, False
        if b["type"] == "exercise":
            for interne in b.get("blocks", []):
                yield interne, True


def texte_anglais(b):
    """Ce qui compte comme volume rédactionnel : la langue d'explication."""
    if b["type"] in ("para", "h2", "h3", "minihead"):
        return b.get("text", "")
    if b["type"] == "dia_line":
        return str(b.get("en", ""))
    if b["type"] == "dialogue":
        return " ".join(str(it.get("en", "") or it.get("text", "")) for it in b["items"])
    if b["type"] == "table":
        return " ".join(c for row in b["rows"] for c in row)
    return ""


def texte_cible(b):
    """Ce qui porte la langue enseignée : hanzi et prononciations."""
    if b["type"] in ("para", "h2", "h3", "minihead"):
        return b.get("text", "")
    if b["type"] == "dia_line":
        return " ".join(str(b.get(k, "")) for k in ("zh", "pinyin"))
    if b["type"] == "dialogue":
        return " ".join(str(it.get(k, "")) for it in b["items"] for k in ("zh", "pinyin"))
    if b["type"] == "table":
        return " ".join(c for row in b["rows"] for c in row)
    return ""


def profiler(book):
    lecons, vus = [], set()
    for ch in book["chapters"]:
        if ch["kind"] not in ("chapter", "story"):
            continue
        compte = Counter()
        types = Counter()
        nouveaux = set()
        for b, dans_exercice in parcours(ch.get("blocks", [])):
            t = b["type"]
            compte["mots"] += mots(texte_anglais(b))
            if not dans_exercice and t in ("para", "h2", "h3", "minihead"):
                compte["mots_prose"] += mots(texte_anglais(b))
            texte = texte_cible(b)
            if t in ("h2", "h3"):
                compte["sections"] += 1
            elif t == "minihead":
                compte["minititres"] += 1
            elif t == "table" and not dans_exercice:
                compte["tableaux"] += 1
            elif t in ("dialogue", "dia_line") and not dans_exercice:
                compte["dialogues"] += 1 if t == "dialogue" else 0
                compte["repliques"] += len(b["items"]) if t == "dialogue" else 1
            elif t == "exercise":
                compte["exercices"] += 1
                types[b.get("ex_type") or "?"] += 1
            for caractere in hanzi_de(texte):
                if caractere not in vus:
                    nouveaux.add(caractere)
            compte["paires"] += len(RE_PAIR.findall(str(texte)))
        vus |= nouveaux
        lecons.append({
            "titre": ch["title"], "genre": ch["kind"],
            "mots": compte["mots"], "mots_prose": compte["mots_prose"],
            "sections": compte["sections"],
            "minititres": compte["minititres"], "tableaux": compte["tableaux"],
            "dialogues": compte["dialogues"], "repliques": compte["repliques"],
            "exercices": compte["exercices"], "paires": compte["paires"],
            "caracteres_nouveaux": len(nouveaux),
            "types_exercices": dict(types),
        })
    return lecons


def bornes(valeurs):
    valeurs = sorted(valeurs)
    if not valeurs:
        return {}
    return {"min": valeurs[0], "median": int(statistics.median(valeurs)),
            "max": valeurs[-1], "moyenne": round(statistics.mean(valeurs), 1)}


CHAMPS = ["mots", "mots_prose", "sections", "minititres", "tableaux", "dialogues", "repliques",
          "exercices", "paires", "caracteres_nouveaux"]


def main():
    book = json.load(open(BOOK))
    lecons = profiler(book)
    lecons_seules = [l for l in lecons if l["genre"] == "chapter"]
    histoires = [l for l in lecons if l["genre"] == "story"]

    types = Counter()
    for l in lecons:
        types.update(l["types_exercices"])

    tiers = max(1, len(lecons_seules) // 3)
    profil = {
        "lecons": len(lecons_seules),
        "courbe": {
            "caracteres_nouveaux_premier_tiers":
                sum(l["caracteres_nouveaux"] for l in lecons_seules[:tiers]),
            "caracteres_nouveaux_dernier_tiers":
                sum(l["caracteres_nouveaux"] for l in lecons_seules[-tiers:]),
        },
        "histoires": len(histoires),
        "quotas": {c: bornes([l[c] for l in lecons_seules]) for c in CHAMPS},
        "quotas_histoires": {c: bornes([l[c] for l in histoires]) for c in CHAMPS},
        "types_exercices": dict(types.most_common()),
        "caracteres_distincts": sum(l["caracteres_nouveaux"] for l in lecons),
        "detail": lecons,
    }
    os.makedirs("content", exist_ok=True)
    json.dump(profil, open(OUT, "w"), ensure_ascii=False, indent=1)

    lignes = ["PROFIL PÉDAGOGIQUE MESURÉ SUR LE MANUSCRIT", "=" * 64,
              f"  {len(lecons_seules)} leçons, {len(histoires)} histoires, "
              f"{profil['caracteres_distincts']} caractères distincts", ""]
    lignes.append(f"  {'':<20} {'min':>6} {'médiane':>8} {'max':>6} {'moyenne':>8}")
    for c in CHAMPS:
        b = profil["quotas"][c]
        lignes.append(f"  {c:<20} {b['min']:>6} {b['median']:>8} {b['max']:>6} {b['moyenne']:>8}")
    lignes += ["", "  types d'exercices :"]
    for t, n in types.most_common():
        lignes.append(f"    {t:<20} {n:>3}")
    lignes += ["", "  leçons hors norme (volume) :"]
    med = profil["quotas"]["mots"]["median"]
    for l in lecons_seules:
        if l["mots"] < med * 0.6 or l["mots"] > med * 1.6:
            lignes.append(f"    {l['mots']:>5} mots  {l['titre'][:52]}")
    open(RAPPORT, "w").write("\n".join(lignes) + "\n")
    print(f"profil : {len(lecons_seules)} leçons mesurées  → {OUT} + {RAPPORT}")


if __name__ == "__main__":
    main()
