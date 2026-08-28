#!/usr/bin/env python3
"""CN10 pipeline — étape 2 : validation automatique du book.json."""
import json, re, unicodedata
from collections import Counter

book = json.load(open("content/book.json"))

from langue import NOM as LANGUE, VERIFICATION

# La vérification automatique de prononciation n'existe que pour les langues
# qui déclarent un vérificateur. Sans lui, ce contrôle ne dit rien — et le dit :
# c'est le professeur natif qui porte alors toute la vérification, ce qui doit
# être visible dans le rapport plutôt que déduit d'un silence.
HAS_PY = False
if VERIFICATION == "pypinyin":
    try:
        from pypinyin import pinyin, Style
        HAS_PY = True
    except ImportError:
        HAS_PY = False

from pairs import RE_PAIR      # motif partagé : voir pipeline/pairs.py

def norm(s):
    s = unicodedata.normalize("NFC", s.lower())
    return re.sub(r"[^a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü]", "", s)

def flat(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = s.replace("u\u0308", "v")  # ü → v AVANT de retirer les diacritiques
    s = re.sub(r"[\u0300-\u036f]", "", s)
    return re.sub(r"[^a-zv]", "", s)

def check_pair(zh, py_given):
    """Vérifie les syllabes (sans tons) avec backtracking sur les hétéronymes + erhua."""
    if re.search(r"[0-9０-９]", zh):
        return True  # chiffres arabes dans le zh — invérifiable syllabe à syllabe
    zh_clean = re.sub(r"[^\u4e00-\u9fff]", "", zh)
    if not zh_clean:
        return True
    opts = []
    for ch in zh_clean:
        readings = pinyin(ch, style=Style.NORMAL, heteronym=True)[0]
        rs = set(flat(r) for r in readings)
        if ch == "儿":
            rs |= {"r", "er", ""}
        if ch == "一":
            rs |= {"yi"}
        if ch == "不":
            rs |= {"bu"}
        opts.append(sorted(rs, key=len, reverse=True))
    # retirer du pinyin les tokens latins présents tels quels dans le zh (noms, Wi-Fi, QR…)
    for tok in re.findall(r"[A-Za-z][A-Za-z\-]*", zh):
        py_given = re.sub(re.escape(tok), "", py_given, count=1, flags=re.I)
    given = flat(py_given)

    from functools import lru_cache
    @lru_cache(maxsize=None)
    def match(i, pos):
        if i == len(opts):
            return pos == len(given)
        for r in opts[i]:
            if given.startswith(r, pos) and match(i + 1, pos + len(r)):
                return True
        return False
    if match(0, 0):
        return True
    # fallback : le zh capturé peut être tronqué en tête (ex. "1988年") —
    # on accepte si le pinyin SE TERMINE par la séquence attendue
    return any(match(0, p) for p in range(1, len(given)))

pairs = []
def walk(blocks, chap):
    for b in blocks:
        t = b["type"]
        if t in ("para", "h2", "h3", "minihead"):
            pairs.extend((chap, z, p) for z, p in RE_PAIR.findall(b["text"]))
        elif t == "dia_line":
            pairs.append((chap, b["zh"], b["pinyin"]))
        elif t == "dialogue":
            for it in b["items"]:
                if it["kind"] == "line":
                    pairs.append((chap, it["zh"], it["pinyin"]))
        elif t == "table":
            for row in b["rows"]:
                for cell in row:
                    pairs.extend((chap, z, p) for z, p in RE_PAIR.findall(cell))
        elif t == "exercise":
            walk(b["blocks"], chap)

for ch in book["chapters"]:
    walk(ch["blocks"], ch["title"][:40])

print(f"paires écriture ↔ prononciation trouvées : {len(pairs)}")
if HAS_PY:
    bad = []
    for chap, zh, py in pairs:
        if not check_pair(zh, py):
            bad.append((chap, zh, py))
    print(f"suspectes : {len(bad)} ({100*len(bad)/max(len(pairs),1):.1f} %)")
    by_chap = Counter(c for c, _, _ in bad)
    with open("validation_report.txt", "w") as f:
        f.write(f"{LANGUE} — rapport de prononciation\n"
                f"{len(pairs)} paires vérifiées, {len(bad)} suspectes\n\n")
        for chap, zh, py in bad:
            f.write(f"[{chap}] {zh}  ↔  [{py}]\n")
    print("top chapitres à relire :", by_chap.most_common(5))
else:
    # Un contrôle absent doit se dire, pas se deviner d'un rapport vide.
    raison = ("aucun vérificateur déclaré pour cette langue"
              if not VERIFICATION else f"{VERIFICATION} n'est pas installé")
    message = (f"{LANGUE} — prononciation non vérifiée automatiquement\n"
               f"{raison}.\n"
               f"{len(pairs)} paires relevées, toutes à la charge du professeur natif.\n")
    print(f"prononciation non vérifiée : {raison}")
    with open("validation_report.txt", "w") as f:
        f.write(message)

# complétude
total_blocks = sum(len(c["blocks"]) for c in book["chapters"])
print(f"blocs totaux : {total_blocks} sur {len(book['chapters'])} chapitres")
