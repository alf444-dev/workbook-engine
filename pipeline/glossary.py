#!/usr/bin/env python3
"""Glossaire maître : ce qui a été enseigné, et à partir de quelle leçon.

C'est ce qui rend la difficulté croissante *vérifiable* plutôt que déclarée.
Une leçon générée ne doit employer que du vocabulaire déjà introduit — et une
leçon écrite à la main peut être contrôlée de la même façon.

On enregistre la **première apparition** de chaque caractère et de chaque
entrée de vocabulaire, pas les cumuls : « enseigné à la leçon n » se déduit
ensuite par comparaison, et le fichier reste petit.

    python3 pipeline/glossary.py     → content/glossary.json + glossary_report.txt
"""
import argparse, json, os, re
from collections import Counter

from lesson_profile import parcours, texte_cible
from pairs import RE_PAIR

BOOK = "content/book_typed.json"
OUT = "content/glossary.json"
RAPPORT = "glossary_report.txt"

HANZI = re.compile(r"[一-鿿]")
PONCTUATION = re.compile(r"[，。？！、；：“”‘’（）]")

# Une paire {zh}{py} courte et sans ponctuation est une entrée de vocabulaire ;
# au-delà c'est une phrase d'exemple, qui n'a pas sa place dans un glossaire.
MOTS_MAX_CARACTERES = 4


def est_entree(zh):
    caracteres = HANZI.findall(zh)
    return (1 <= len(caracteres) <= MOTS_MAX_CARACTERES
            and not PONCTUATION.search(zh)
            and len(caracteres) == len(zh.strip()))


def construire(book):
    """Deux relevés distincts, et c'est voulu.

    Les **caractères** sont relevés sur tout le chinois de la leçon, balisé ou
    non : c'est ce qu'un élève a réellement vu, et donc la bonne référence pour
    dire « cette leçon emploie un caractère jamais enseigné ». Les **entrées de
    vocabulaire** ne viennent que des paires balisées {zh}{py}, seul endroit où
    le manuscrit dit explicitement « voici un mot et sa prononciation ».
    """
    caracteres, mots = {}, {}
    lecons, n = [], 0
    for ch in book["chapters"]:
        if ch["kind"] not in ("chapter", "story"):
            continue
        n += 1
        neufs_c, neufs_m = [], []
        for bloc, _ in parcours(ch.get("blocks", [])):
            texte = texte_cible(bloc)
            for c in HANZI.findall(texte):
                if c not in caracteres:
                    caracteres[c] = n
                    neufs_c.append(c)
            for zh, pinyin in RE_PAIR.findall(str(texte)):
                if est_entree(zh) and zh not in mots:
                    mots[zh] = {"pinyin": pinyin.strip(), "lecon": n}
                    neufs_m.append(zh)
        lecons.append({"n": n, "titre": ch["title"], "genre": ch["kind"],
                       "caracteres_nouveaux": neufs_c, "mots_nouveaux": neufs_m})
    return caracteres, mots, lecons


def enseigne_avant(glossaire, n):
    """Les caractères connus d'un élève arrivé à la leçon n incluse."""
    return {c for c, lecon in glossaire["caracteres"].items() if lecon <= n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--livre", default=BOOK)
    ap.add_argument("--sortie", default=OUT)
    a = ap.parse_args()
    book = json.load(open(a.livre))
    caracteres, mots, lecons = construire(book)
    glossaire = {
        "caracteres": caracteres,
        "mots": mots,
        "lecons": lecons,
        "totaux": {"caracteres": len(caracteres), "mots": len(mots),
                   "lecons": len(lecons)},
    }
    os.makedirs("content", exist_ok=True)
    json.dump(glossaire, open(a.sortie, "w"), ensure_ascii=False, indent=1)

    par_lecon = Counter(l["lecon"] for l in mots.values())
    lignes = ["GLOSSAIRE MAÎTRE", "=" * 60,
              f"  {len(caracteres)} caractères, {len(mots)} entrées de vocabulaire, "
              f"{len(lecons)} leçons", "",
              f"  {'leçon':>5}  {'car.':>5}  {'mots':>5}  titre"]
    for l in lecons:
        lignes.append(f"  {l['n']:>5}  {len(l['caracteres_nouveaux']):>5}  "
                      f"{par_lecon.get(l['n'], 0):>5}  {l['titre'][:48]}")
    lignes += ["", "  premières entrées :"]
    for zh, info in list(mots.items())[:12]:
        lignes.append(f"    leçon {info['lecon']:>2}  {zh}  ({info['pinyin']})")
    open(RAPPORT, "w").write("\n".join(lignes) + "\n")
    print(f"glossaire : {len(caracteres)} caractères, {len(mots)} entrées  → {a.sortie}")


if __name__ == "__main__":
    main()
