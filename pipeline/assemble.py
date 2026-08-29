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
import argparse, json, subprocess, sys
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


def assembler():
    book = json.load(open(reference()))
    chapitres, rang, manquantes, reprises = [], 0, [], 0
    for ch in book["chapters"]:
        if ch["kind"] == "answers":
            continue                       # le corrigé sera dérivé des exercices
        if ch["kind"] != "chapter":
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
    return book, rang, manquantes, reprises


def reference_etrangere():
    """Le livre de référence est-il dans une autre langue que la cible ?"""
    chemin = Path("content/glossary.json")
    if not chemin.exists():
        return False
    return json.loads(chemin.read_text(encoding="utf-8")).get("langue") not in (None, langue.CODE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rendre", action="store_true",
                    help="enchaîne le reste du pipeline jusqu'au PDF")
    a = ap.parse_args()

    book, total, manquantes, reprises = assembler()
    # Reprendre un chapitre de la référence est acceptable dans la même langue :
    # c'est un brouillon lisible. Dans une autre langue, c'est un livre qui a
    # l'air fini et enseigne la mauvaise — celui du 29 août 2026 avait
    # « LEARN CHINESE » sur 238 pages. On refuse plutôt que de le produire.
    if manquantes and reference_etrangere():
        sys.exit(f"assemblage refusé : {len(manquantes)} leçons manquent "
                 f"({', '.join(map(str, manquantes[:8]))}"
                 f"{'…' if len(manquantes) > 8 else ''}) et le livre de référence "
                 f"n'est pas en {langue.NOM}. Les reprendre donnerait un livre "
                 f"dans la mauvaise langue. Écrire ces leçons d'abord.")
    json.dump(book, open(SORTIE, "w"), ensure_ascii=False, indent=1)
    print(f"livre assemblé : {total - len(manquantes)}/{total} leçons générées, "
          f"{reprises} chapitres repris de la référence (introduction, histoires, "
          f"conclusion) → {SORTIE}")
    if manquantes:
        print(f"  leçons manquantes, reprises de la référence : {manquantes}")

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
