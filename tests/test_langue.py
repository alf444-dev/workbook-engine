#!/usr/bin/env python3
"""Vérifie qu'ajouter une langue ne demande pas de toucher au code.

Tout ce qui dépend de la langue — plage d'écriture, signes de romanisation,
vérification de prononciation — est déclaré dans config/<langue>.json. Ce test
le prouve en pilotant le moteur avec une autre langue que le chinois.

    python3 tests/test_langue.py
"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PIPELINE = REPO / "pipeline"

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


def sous_langue(langue, code):
    """Exécute un bout de code avec la langue demandée."""
    env = {**os.environ, "WB_LANGUE": langue, "PYTHONPATH": str(PIPELINE)}
    r = subprocess.run([sys.executable, "-c", code], cwd=REPO, env=env,
                       capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(f"échec sous {langue} :\n{r.stderr[-800:]}")
    return r.stdout.strip()


DETECTE = ("import langue, sys; "
           "print(','.join(str(bool(langue.SCRIPT.search(t))) "
           "for t in ['你好', 'ひらがな', 'カタカナ', '漢字', 'hello']))")

ok("le chinois reconnaît les hanzi et pas l'anglais",
   sous_langue("chinese", DETECTE).split(",")[0] == "True"
   and sous_langue("chinese", DETECTE).split(",")[-1] == "False")

ja = sous_langue("japanese", DETECTE).split(",")
ok("le japonais reconnaît hiragana, katakana et kanji",
   ja[1] == "True" and ja[2] == "True" and ja[3] == "True", str(ja))
ok("et ne prend pas l'anglais pour de l'écriture cible", ja[-1] == "False")

ok("le chinois déclare son vérificateur de prononciation",
   sous_langue("chinese", "import langue; print(langue.VERIFICATION)") == "pypinyin")
ok("le japonais n'en déclare aucun",
   sous_langue("japanese", "import langue; print(langue.VERIFICATION)") == "None")

ok("les signes de romanisation sont propres à la langue",
   sous_langue("chinese", "import langue; print('ǎ' in langue.DIACRITIQUES)") == "True"
   and sous_langue("japanese", "import langue; print('ǎ' in langue.DIACRITIQUES)") == "False")
ok("le japonais connaît ses macrons",
   sous_langue("japanese", "import langue; print('ō' in langue.DIACRITIQUES)") == "True")

ok("une langue inconnue échoue avec un message utile",
   "introuvable" in subprocess.run(
       [sys.executable, "-c", "import langue"], cwd=REPO,
       env={**os.environ, "WB_LANGUE": "klingon", "PYTHONPATH": str(PIPELINE)},
       capture_output=True, text=True).stderr)

# ------------------------------------------------- la config reprise d'un gabarit
# check_config lit content/profile.json : sur un dépôt fraîchement cloné il
# n'existe pas et les deux vérifications échouaient sans dire pourquoi. On le
# produit ici si le livre est là, sinon on le dit.
if not (REPO / "content" / "profile.json").exists() and (REPO / "content" / "book_typed.json").exists():
    subprocess.run([sys.executable, "pipeline/lesson_profile.py"], cwd=REPO,
                   capture_output=True, text=True)
if not (REPO / "content" / "profile.json").exists():
    print("  (content/profile.json absent : lancer ./run.sh puis pipeline/lesson_profile.py)")
r = subprocess.run([sys.executable, "pipeline/check_config.py", "config/japanese.json"],
                   cwd=REPO, capture_output=True, text=True)
ok("une config reprise d'un gabarit ne se présente pas comme mesurée",
   r.returncode == 0 and "gabarit" in r.stdout and "correspondent au livre" not in r.stdout,
   r.stdout.strip()[:120])

r = subprocess.run([sys.executable, "pipeline/check_config.py", "config/chinese.json"],
                   cwd=REPO, capture_output=True, text=True)
ok("la config chinoise, elle, reste confrontée au livre",
   r.returncode == 0 and "correspondent au livre" in r.stdout, r.stdout.strip()[:120])

# ------------------------------------------------- prononciation non vérifiable
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    (tmp / "content").mkdir()
    (tmp / "content" / "book.json").write_text(json.dumps({"meta": {}, "chapters": [
        {"kind": "chapter", "num": 1, "title": "T", "blocks": [
            {"type": "para", "text": "Say {zh:你好} {py:nǐ hǎo}."}]}]}), encoding="utf-8")
    r = subprocess.run([sys.executable, str(PIPELINE / "validate.py")], cwd=tmp,
                       env={**os.environ, "WB_LANGUE": "japanese"},
                       capture_output=True, text=True)
    rapport = (tmp / "validation_report.txt").read_text(encoding="utf-8")
ok("sans vérificateur, le rapport le dit au lieu de rester vide",
   "non vérifiée" in rapport and "professeur natif" in rapport, rapport[:150])

# ------------------------------------------------- distinguer les langues à écriture voisine
import importlib                                                 # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
os.environ["WB_LANGUE"] = "japanese"
import langue                                                    # noqa: E402
ja = importlib.reload(langue)

JAPONAIS = ["私は学生です", "水を飲みます", "こんにちは", "駅はどこですか"]
CHINOIS = ["你好", "我喜欢红茶", "今天比昨天热", "地铁比公交车快"]

bon, _ = ja.langue_plausible(JAPONAIS)
ok("du japonais passe le contrôle de langue", bon)
refus, motif = ja.langue_plausible(CHINOIS)
ok("du chinois est refusé dans un livre de japonais", not refus)
ok("et le refus explique ce qui manque", "signature" in motif, motif)
ok("les kanji seuls ne suffisent pas à faire du japonais",
   not ja.langue_plausible(["人", "水", "山", "火"])[0])
ok("le titre du livre suit la langue",
   ja.titres_du_livre()["cover_title"] == "LEARN JAPANESE",
   str(ja.titres_du_livre()))

os.environ["WB_LANGUE"] = "chinese"
zh = importlib.reload(langue)
ok("du chinois passe dans un livre de chinois", zh.langue_plausible(CHINOIS)[0])
ok("des kana sont refusés dans un livre de chinois",
   not zh.langue_plausible(JAPONAIS)[0])
ok("le titre chinois reste celui du livre publié",
   zh.titres_du_livre()["cover_title"] == "LEARN CHINESE")

rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
