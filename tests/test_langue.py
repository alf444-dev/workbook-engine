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

rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
