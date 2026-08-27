#!/usr/bin/env python3
"""Vérifie la mesure du profil pédagogique.

Ces quotas deviennent le cahier des charges de la génération : une mesure
fausse contraindrait la production avec des chiffres inventés. Le piège
principal est que le pinyin s'écrit en caractères latins — le compter comme de
l'anglais double le volume mesuré.

    python3 tests/test_profil.py
"""
import copy, json, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_book import BOOK                                  # noqa: E402

PROFILEUR = REPO / "pipeline" / "lesson_profile.py"


def profiler(book):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "content").mkdir()
        (tmp / "content" / "book_typed.json").write_text(
            json.dumps(book, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, str(PROFILEUR)], cwd=tmp,
                           capture_output=True, text=True)
        if r.returncode:
            raise AssertionError(f"lesson_profile.py a échoué :\n{r.stderr}")
        return json.loads((tmp / "content" / "profile.json").read_text(encoding="utf-8"))


checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


base = profiler(BOOK)
lecon = base["detail"][0]

# ---------------------------------------------------------------- le pinyin n'est pas de l'anglais
allonge = copy.deepcopy(BOOK)
allonge["chapters"][1]["blocks"][0]["text"] = "Say {zh:你好} {py:nǐ hǎo zài jiàn xiè xie duō} to greet."
apres = profiler(allonge)["detail"][0]
ok("rallonger le pinyin ne change pas le volume rédactionnel",
   apres["mots"] == lecon["mots"], f"{lecon['mots']} → {apres['mots']}")

allonge = copy.deepcopy(BOOK)
allonge["chapters"][1]["blocks"][2]["items"][0]["pinyin"] = "xiè xie hěn duō de huà"
ok("le pinyin d'une réplique ne compte pas non plus",
   profiler(allonge)["detail"][0]["mots"] == lecon["mots"])

anglais = copy.deepcopy(BOOK)
anglais["chapters"][1]["blocks"][0]["text"] = "Say {zh:你好} {py:nǐ hǎo} to greet a friend today."
ok("mais l'anglais ajouté, si",
   profiler(anglais)["detail"][0]["mots"] == lecon["mots"] + 3,
   f"{lecon['mots']} → {profiler(anglais)['detail'][0]['mots']}")

# ---------------------------------------------------------------- prose et exercices
dans_ex = copy.deepcopy(BOOK)
dans_ex["chapters"][1]["blocks"][4]["blocks"][0]["text"] = \
    "Wrong: {zh:你的老师呢？} {py:Nǐ ne?} here and there and elsewhere too."
apres = profiler(dans_ex)["detail"][0]
ok("le texte d'un exercice compte dans le volume total",
   apres["mots"] > lecon["mots"])
ok("mais pas dans la prose de la leçon",
   apres["mots_prose"] == lecon["mots_prose"],
   f"{lecon['mots_prose']} → {apres['mots_prose']}")

# ---------------------------------------------------------------- vocabulaire vu une fois
repete = copy.deepcopy(BOOK)
repete["chapters"].append({"kind": "chapter", "num": 2, "title": "REVISION", "blocks": [
    {"type": "para", "text": "Again {zh:你好} {py:nǐ hǎo} and {zh:谢谢} {py:xièxie}."}]})
p = profiler(repete)
ok("un caractère déjà enseigné n'est pas recompté comme nouveau",
   p["detail"][-1]["caracteres_nouveaux"] == 0,
   str(p["detail"][-1]["caracteres_nouveaux"]))

neuf = copy.deepcopy(BOOK)
neuf["chapters"].append({"kind": "chapter", "num": 2, "title": "SUITE", "blocks": [
    {"type": "para", "text": "New {zh:机场} {py:jīchǎng} here."}]})
ok("un caractère inédit, si",
   profiler(neuf)["detail"][-1]["caracteres_nouveaux"] == 2)

# ---------------------------------------------------------------- structure
ok("les exercices sont comptés, y compris ceux sans réponses",
   lecon["exercices"] == 2, str(lecon["exercices"]))
ok("les types d'exercices sont relevés",
   base["types_exercices"].get("translation") == 2, str(base["types_exercices"]))
ok("un tableau à l'intérieur d'un exercice ne gonfle pas le compte de tableaux",
   lecon["tableaux"] == 1, str(lecon["tableaux"]))
ok("les histoires sont séparées des leçons",
   base["lecons"] == 1 and base["histoires"] == 1,
   f"{base['lecons']} leçons, {base['histoires']} histoires")
ok("la courbe du vocabulaire est exposée pour la config",
   "caracteres_nouveaux_premier_tiers" in base["courbe"])

rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
