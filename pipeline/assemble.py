#!/usr/bin/env python3
"""Assemble un livre à partir des leçons générées.

Reprend la charpente du livre de référence — introduction, sections, histoires,
conclusion — et y substitue les leçons produites par la génération. Ce qui n'est
pas encore généré (histoires, textes de section) reste celui de la référence :
c'est explicite, pas caché.

Le chapitre de corrigés du manuscrit est **retiré** : le corrigé se dérive des
exercices (invariant 2), et celui de la référence ne correspond plus à rien.

    python3 pipeline/assemble.py            → content/book.json
    python3 pipeline/assemble.py --rendre   → et lance le reste du pipeline
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

# Le livre de référence a été mis de côté après avoir livré ses mesures, pour ne
# pas polluer les files de relecture : livre.py sait sous quel nom le trouver.
import langue
import livre

reference = livre.chemin
GENERE = Path("content/generated")
SORTIE = "content/book.json"

SUITE = [
    ("typage des exercices", ["pipeline/exercises.py"]),
    ("validation linguistique", ["pipeline/validate.py"]),
    ("contrôle des exercices", ["pipeline/check_exercises.py"]),
    ("corrigés dérivés", ["pipeline/answerkeys.py"]),
]


def en_langue_etrangere(ch):
    """Ce chapitre repris porte-t-il l'écriture de la langue de référence ?

    Les histoires, l'introduction et la conclusion ne sont pas générées : elles
    viennent du livre de référence. Dans la même langue c'est un brouillon
    lisible ; dans une autre, ce sont cinq récits chinois au milieu d'un livre
    japonais. Le livre du 2 septembre 2026 les contenait — 87 à 151 sinogrammes
    chacun — et rien ne le signalait, parce que le contrôle ne portait que sur
    les leçons manquantes.
    """
    if not reference_etrangere():
        return False
    # Surtout pas `langue.SCRIPT` : pour le japonais elle inclut le bloc des
    # sinogrammes, donc un récit chinois y passerait — c'est exactement le
    # piège qui avait laissé 225 pages de chinois dans un livre japonais.
    # `langue_plausible` s'appuie sur la signature, qui distingue vraiment.
    ECRITURES = re.compile(r"[一-鿿぀-ゟ゠-ヿ가-힣]")
    morceaux = []

    def ramasser(x):
        if isinstance(x, str):
            if ECRITURES.search(x):
                morceaux.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                ramasser(v)
        elif isinstance(x, list):
            for v in x:
                ramasser(v)

    ramasser(ch)
    if not morceaux:
        return False
    bon, _ = langue.langue_plausible(morceaux)
    return not bon


def assembler(garder_reference=False):
    book = json.load(open(reference()))
    chapitres, rang, manquantes, reprises, ecartes = [], 0, [], 0, []
    for ch in book["chapters"]:
        if ch["kind"] == "answers":
            continue                       # le corrigé sera dérivé des exercices
        if ch["kind"] != "chapter":
            if not garder_reference and en_langue_etrangere(ch):
                ecartes.append(ch.get("title") or ch["kind"])
                continue
            chapitres.append(ch)
            if ch["kind"] in ("story", "intro", "conclusion"):
                reprises += 1
            continue
        rang += 1
        fichier = GENERE / f"lecon_{rang:02d}.json"
        if fichier.exists():
            lecon = json.loads(fichier.read_text(encoding="utf-8"))
            lecon["num"] = ch.get("num", rang)
            chapitres.append(lecon)
        else:
            manquantes.append(rang)
            chapitres.append(ch)
    book["chapters"] = chapitres
    # La charpente vient du livre de référence, ses titres aussi : sans cette
    # ligne, un livre de japonais garde « LEARN CHINESE » en couverture.
    book["meta"] = {**book.get("meta", {}), **langue.titres_du_livre()}
    return book, rang, manquantes, reprises, ecartes


def reference_etrangere():
    """Le livre de référence est-il dans une autre langue que la cible ?"""
    chemin = Path("content/glossary.json")
    if not chemin.exists():
        return False
    return json.loads(chemin.read_text(encoding="utf-8")).get("langue") not in (None, langue.CODE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--garder-reference", action="store_true",
                    help="garder les chapitres repris même s'ils sont dans la "
                         "langue de la référence — un brouillon, pas un livre")
    ap.add_argument("--rendre", action="store_true",
                    help="enchaîne le reste du pipeline jusqu'au PDF")
    a = ap.parse_args()

    book, total, manquantes, reprises, ecartes = assembler(a.garder_reference)
    # Reprendre un chapitre de la référence est acceptable dans la même langue :
    # c'est un brouillon lisible. Dans une autre langue, c'est un livre qui a
    # l'air fini et enseigne la mauvaise — celui du 29 août 2026 avait
    # « LEARN CHINESE » sur 238 pages. On refuse plutôt que de le produire.
    if manquantes and reference_etrangere():
        sys.exit(f"assembly refused: {len(manquantes)} lessons are missing "
                 f"({', '.join(map(str, manquantes[:8]))}"
                 f"{'…' if len(manquantes) > 8 else ''}) and the reference book is "
                 f"not in {langue.ANGLAIS}. Reusing its chapters would produce a "
                 f"book in the wrong language. Write those lessons first.")
    json.dump(book, open(SORTIE, "w"), ensure_ascii=False, indent=1)
    print(f"livre assemblé : {total - len(manquantes)}/{total} leçons générées, "
          f"{reprises} chapitres repris de la référence (introduction, histoires, "
          f"conclusion) → {SORTIE}")
    if manquantes:
        print(f"  leçons manquantes, reprises de la référence : {manquantes}")
    if ecartes:
        print(f"  {len(ecartes)} chapitres écartés, encore dans la langue de la "
              f"référence : {', '.join(str(e)[:34] for e in ecartes)}")
        print("    (ils ne sont pas générés ; --garder-reference les réintègre)")

    if not a.rendre:
        return 0
    for libelle, commande in SUITE:
        print(f"  {libelle}…")
        r = subprocess.run([sys.executable] + commande, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"échec sur {commande[0]} :\n{r.stderr[-1500:]}")
    print("  compilation du livre…")
    r = subprocess.run(["typst", "compile", "--font-path", "fonts", "--root", ".",
                        "templates/book.typ", "output/book.pdf"],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"échec de Typst :\n{r.stderr[-1500:]}")
    subprocess.run([sys.executable, "pipeline/bundle.py"])
    print("→ output/book.pdf")
    return 0


if __name__ == "__main__":
    sys.exit(main())
