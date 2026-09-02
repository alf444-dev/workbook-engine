#!/usr/bin/env python3
"""L'outil de comparaison de modèles, sans appeler aucun modèle.

Ce qu'il produit sert à décider si on remplace Opus par un modèle deux fois et
demie moins cher sur un livre entier. Une erreur de notation ferait prendre la
mauvaise décision — sans que rien ne le signale.

    python3 tests/test_comparer.py
"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "server"))
sys.path.insert(0, str(REPO / "pipeline"))

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


import couts                                                     # noqa: E402
import tarifs                                                    # noqa: E402

# ---------------------------------------------------------------- tarifs
ok("le tarif d'Opus 5 est celui de la page officielle",
   couts.prix("claude-opus-5") == {"entree": 5.0, "sortie": 25.0})
ok("celui de Sonnet 5 aussi",
   couts.prix("claude-sonnet-5") == {"entree": 2.0, "sortie": 10.0})
ok("un modèle inconnu retombe sur le tarif par défaut, pas sur zéro",
   couts.prix("modele-imaginaire") == couts.prix(couts.MODELE_DEFAUT))
# La table vit dans le pipeline : un espace de travail ne reçoit pas server/.
ok("la table des tarifs est dans le pipeline, pas dans le serveur",
   (REPO / "pipeline" / "tarifs.py").exists()
   and "from tarifs import" in (REPO / "server" / "couts.py").read_text(encoding="utf-8"))
ok("aucun script du pipeline n'importe le serveur",
   not [f.name for f in (REPO / "pipeline").glob("*.py")
        if "server" in f.read_text(encoding="utf-8")
        and "sys.path" in f.read_text(encoding="utf-8")],
   "un script du moteur cassera dans un espace de travail")

opus = couts.cout(5_800, 16_500, "claude-opus-5")
sonnet = couts.cout(5_800, 16_500, "claude-sonnet-5")
ok("une leçon Opus coûte bien 0,44 $", abs(opus - 0.4415) < 0.001, f"{opus:.4f}")
ok("une leçon Sonnet coûte bien 0,18 $", abs(sonnet - 0.1766) < 0.001, f"{sonnet:.4f}")
ok("Sonnet est exactement 2,5 fois moins cher sur ce mélange",
   abs(opus / sonnet - 2.5) < 0.01, f"{opus / sonnet:.3f}")
ok("la remise Batch divise par deux",
   abs(couts.cout(5_800, 16_500, "claude-opus-5", batch=True) - opus / 2) < 1e-9)
ok("l'estimation affichée sur le site n'a pas bougé",
   couts.estimer("lecon", 31)[0] == 13.69, str(couts.estimer("lecon", 31)))

# ---------------------------------------------------------------- notation
TMP = Path(tempfile.mkdtemp(prefix="wb-comp-"))
for d in ("pipeline", "config"):
    shutil.copytree(REPO / d, TMP / d, ignore=shutil.ignore_patterns("__pycache__"))
(TMP / "content").mkdir()
sys.path.insert(0, str(REPO / "tests"))
from fixture_book import BOOK                                    # noqa: E402
(TMP / "content" / "book_typed.json").write_text(
    json.dumps(BOOK, ensure_ascii=False), encoding="utf-8")
(TMP / "content" / "plan.json").write_text(json.dumps({
    "totaux": {"lecons": 1}, "lecons": [
        {"n": 1, "titre": "GREETINGS", "exercices": ["translation"],
         "vocabulaire": [{"zh": "你好", "pinyin": "nǐ hǎo"},
                         {"zh": "再见", "pinyin": "zài jiàn"}],
         "quotas": {k: {"cible": 3, "min": 1, "max": 99} for k in
                    ("mots_prose", "sections", "tableaux", "paires", "dialogues",
                     "repliques", "caracteres_nouveaux")}}]}, ensure_ascii=False),
    encoding="utf-8")

# Une « leçon produite » qui n'enseigne qu'un mot sur les deux imposés.
lecon = {"kind": "chapter", "num": 1, "title": "GREETINGS", "blocks": [
    {"type": "para", "text": "Say {zh:你好} {py:nǐ hǎo} to greet."},
    {"type": "table", "ncols": 2,
     "rows": [["Phrase", "Meaning"], ["{zh:你好} {py:nǐ hǎo}", "hello"]]}]}
dossier = TMP / "content" / "comparaison" / "essai-1"
dossier.mkdir(parents=True)
(dossier / "lecon.json").write_text(json.dumps(lecon, ensure_ascii=False),
                                    encoding="utf-8")
(dossier / "lecon_recu.json").write_text(json.dumps({"entree": 5800, "sortie": 16500}),
                                         encoding="utf-8")

r = subprocess.run([sys.executable, "pipeline/comparer.py", "--lecon", "1",
                    "--simuler", "--modeles", "claude-essai"],
                   cwd=TMP, capture_output=True, text=True,
                   env={**os.environ, "WB_LANGUE": "chinese"})
ok("l'outil tourne sans appeler aucun modèle", r.returncode == 0,
   r.stderr[-400:] or r.stdout[-400:])
ok("il compte le vocabulaire imposé réellement enseigné", " 1/2" in r.stdout,
   r.stdout[-400:])
ok("il chiffre le coût à partir des jetons mesurés", "0.442$" in r.stdout,
   r.stdout[-400:])

# ---------------------------------------------------------------- à l'aveugle
aveugle = TMP / "content" / "comparaison"
ok("une page anonyme est produite", (aveugle / "A.html").exists())
page = (aveugle / "A.html").read_text(encoding="utf-8")
ok("elle ne nomme aucun modèle",
   "opus" not in page.lower() and "sonnet" not in page.lower()
   and "claude" not in page.lower(), page[:200])
ok("elle montre bien le texte de la leçon", "to greet" in page, page[:200])
ok("et les marqueurs de paires n'y apparaissent pas", "{zh:" not in page)
ok("la correspondance est dans un fichier à part",
   json.loads((aveugle / "cle.json").read_text(encoding="utf-8")) == {"A": "essai-1"},
   (aveugle / "cle.json").read_text(encoding="utf-8"))
ok("la page n'est pas indexable", "noindex" in page)

shutil.rmtree(TMP, ignore_errors=True)
rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
