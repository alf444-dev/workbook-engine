#!/usr/bin/env python3
"""Vérifie le rejeu des décisions sur content/book.json.

Ce que ces tests protègent : une correction de professeur doit atterrir
exactement là où il l'a vue, survivre à une recompilation, et ne jamais
s'appliquer au petit bonheur quand le manuscrit a bougé sous elle.

    python3 tests/test_decisions.py
"""
import copy, json, re, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_book import BOOK, FAUTIF                       # noqa: E402

APPLIQUEUR = REPO / "pipeline" / "decisions.py"

# Adresses des paires du manuscrit d'essai.
T_PARA     = {"path": ["chapters", 1, "blocks", 1], "field": "text", "occurrence": 0}
T_DIALOGUE = {"path": ["chapters", 1, "blocks", 2, "items", 0], "field": "pinyin", "occurrence": 0}
T_TABLE    = {"path": ["chapters", 1, "blocks", 3, "rows", 0], "field": 0, "occurrence": 0}
T_EX_LIGNE = {"path": ["chapters", 1, "blocks", 4, "blocks", 1], "field": "pinyin", "occurrence": 0}
T_FAUX     = {"path": ["chapters", 1, "blocks", 99], "field": "text", "occurrence": 0}


def decision(**kw):
    base = {"item_id": "x", "action": "fix", "by": "Wei", "kind": "pinyin",
            "lesson": "Leçon", "value": ""}
    base.update(kw)
    return base


def appliquer(decisions, book=None):
    """Lance decisions.py dans un espace neuf. Rend (livre, rapport)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "content").mkdir()
        livre = copy.deepcopy(BOOK if book is None else book)
        (tmp / "content" / "book.json").write_text(
            json.dumps(livre, ensure_ascii=False), encoding="utf-8")
        if decisions is not None:
            (tmp / "content" / "decisions.json").write_text(
                json.dumps(decisions, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, str(APPLIQUEUR)], cwd=tmp,
                           capture_output=True, text=True)
        if r.returncode:
            raise AssertionError(f"decisions.py a échoué :\n{r.stderr}")
        rapport = (tmp / "decisions_report.txt")
        return (json.loads((tmp / "content" / "book.json").read_text(encoding="utf-8")),
                rapport.read_text(encoding="utf-8") if rapport.exists() else "")


checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


# ---------------------------------------------------------------- sans décisions
livre, rapport = appliquer(None)
ok("sans decisions.json, le livre n'est pas touché", livre == BOOK)
ok("sans decisions.json, aucun rapport n'est écrit", rapport == "")

# ---------------------------------------------------------------- ligne de dialogue
livre, _ = appliquer([decision(item_id="a", zh="谢谢", pinyin="xièxie",
                               value="xiè xie", target=T_DIALOGUE)])
ok("une correction sur une ligne de dialogue atteint le bon champ",
   livre["chapters"][1]["blocks"][2]["items"][0]["pinyin"] == "xiè xie",
   livre["chapters"][1]["blocks"][2]["items"][0]["pinyin"])
ok("elle ne touche pas la ligne voisine",
   livre["chapters"][1]["blocks"][2]["items"][2]["pinyin"] == "bú kèqi")

# ---------------------------------------------------------------- cellule de tableau
livre, _ = appliquer([decision(item_id="b", zh="老师", pinyin="lǎoshī",
                               value="lǎo shī", target=T_TABLE)])
ok("une correction dans un tableau ne réécrit que sa cellule",
   livre["chapters"][1]["blocks"][3]["rows"][0][0] == "{zh:老师} {py:lǎo shī}"
   and livre["chapters"][1]["blocks"][3]["rows"][1][0] == "{zh:学生} {py:xuésheng}",
   livre["chapters"][1]["blocks"][3]["rows"][0][0])

# ---------------------------------------------------------------- paragraphe et exercice imbriqué
livre, _ = appliquer([decision(item_id="c", zh="再见", pinyin="zai",
                               value="zài jiàn", target=T_EX_LIGNE)])
ok("une correction dans un exercice imbriqué aboutit",
   livre["chapters"][1]["blocks"][4]["blocks"][1]["pinyin"] == "zài jiàn")

# ---------------------------------------------------------------- adresse périmée
sans_doublon = copy.deepcopy(BOOK)
sans_doublon["chapters"][1]["blocks"][4]["blocks"].pop(0)      # retire le doublon
decale = copy.deepcopy(sans_doublon)
decale["chapters"].insert(1, {"kind": "section", "num": 9, "title": "INSÉRÉE", "blocks": []})
livre, rapport = appliquer(
    [decision(item_id="d", zh="你的老师呢？", pinyin="Nǐ ne?",
              value="nǐ de lǎoshī ne", target=T_PARA)], book=decale)
ok("un bloc qui a bougé est retrouvé par son contenu",
   "{py:nǐ de lǎoshī ne}" in livre["chapters"][2]["blocks"][1]["text"]
   and "relocalisée" in rapport,
   livre["chapters"][2]["blocks"][1]["text"])

# ---------------------------------------------------------------- ambiguïté
livre, rapport = appliquer(
    [decision(item_id="e", zh="你的老师呢？", pinyin="Nǐ ne?",
              value="nǐ de lǎoshī ne", target=T_FAUX)])
ok("deux emplacements possibles : rien n'est appliqué",
   livre == BOOK and "ambiguë" in rapport, rapport[-200:])

# ---------------------------------------------------------------- contenu disparu
livre, rapport = appliquer(
    [decision(item_id="f", zh="不存在", pinyin="bù cúnzài",
              value="x", target=T_FAUX)])
ok("une paire absente du manuscrit ne s'applique nulle part",
   livre == BOOK and "sans objet" in rapport)

# ---------------------------------------------------------------- hors portée
livre, rapport = appliquer(
    [decision(item_id="g", kind="exercise", value="peu importe", target=T_PARA)])
ok("une décision d'exercice ne réécrit pas le livre",
   livre == BOOK and "non appliquée" in rapport)
ok("le corrigé reste dérivé, jamais recopié",
   "hors portée" in rapport)

# ---------------------------------------------------------------- triage
livre, _ = appliquer([decision(item_id="h", action="ok", zh="谢谢",
                               pinyin="xièxie", target=T_DIALOGUE)])
ok("valider un item ne change rien au livre", livre == BOOK)

# ---------------------------------------------------------------- idempotence
d = [decision(item_id="i", zh="谢谢", pinyin="xièxie",
              value="xiè xie", target=T_DIALOGUE)]
une, _ = appliquer(d)
deux, rapport = appliquer(d, book=une)

def compte(rapport, libelle):
    m = re.search(rf"(\d+) {libelle}", rapport)
    return int(m.group(1)) if m else 0

ok("rejouer sur un livre déjà corrigé ne dérive pas", deux == une)
ok("et la correction est reconnue comme déjà en place",
   compte(rapport, "déjà en place") == 1 and compte(rapport, "corrections appliquées") == 0,
   rapport.split("\n\n")[0])

rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
