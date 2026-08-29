#!/usr/bin/env python3
"""La chaîne entière, hors ligne, jusqu'au PDF — dans une autre langue.

C'est le test qui manquait. Le premier livre japonais est sorti avec 225 pages
de chinois sur 238 et « LEARN CHINESE » sur la couverture : chaque étape était
testée isolément, aucune ne l'était bout à bout. On rejoue donc tout le parcours
d'un livre en langue nouvelle, sans un seul appel payant :

    mesure → plan → progression proposée → décisions du professeur → curriculum
    validé → replanification → contrôles → leçons → assemblage → PDF

Le modèle est remplacé par des sorties brutes écrites à la main : `generate.py
--toutes --reconvertir` les convertit sans appeler l'API, ce qui exerce le vrai
convertisseur, le vrai contrôle de langue et le vrai assemblage.

    python3 tests/test_bout_en_bout.py
"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PIPELINE = REPO / "pipeline"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_book import BOOK                                    # noqa: E402

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


TMP = Path(tempfile.mkdtemp(prefix="wb-e2e-"))


def atelier():
    """Un espace de travail comme le serveur en fabrique un."""
    for d in ("pipeline", "config", "templates"):
        shutil.copytree(REPO / d, TMP / d,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (TMP / "content").mkdir()
    (TMP / "output").mkdir()
    (TMP / "content" / "book_typed.json").write_text(
        json.dumps(BOOK, ensure_ascii=False), encoding="utf-8")
    if (REPO / "fonts").exists():
        (TMP / "fonts").symlink_to(REPO / "fonts")


def lancer(script, *args, langue="japanese", attendu=0):
    r = subprocess.run([sys.executable, f"pipeline/{script}", *args], cwd=TMP,
                       capture_output=True, text=True,
                       env={**os.environ, "WB_LANGUE": langue,
                            "ANTHROPIC_API_KEY": "sk-hors-ligne"})
    if attendu is not None and r.returncode != attendu:
        raise AssertionError(f"{script} → {r.returncode} (attendu {attendu})\n"
                             f"{r.stdout[-800:]}\n{r.stderr[-800:]}")
    return r


atelier()

# ---------------------------------------------------------------- 1. mesure
lancer("lesson_profile.py", langue="chinese")
lancer("glossary.py", langue="chinese")
lancer("style.py", langue="chinese")
glossaire = json.loads((TMP / "content" / "glossary.json").read_text(encoding="utf-8"))
ok("le glossaire mesuré porte la langue de la référence",
   glossaire["langue"] == "zh-Hans", glossaire.get("langue"))

# Les titres passent dans la langue cible, comme le fait le serveur.
profil = json.loads((TMP / "content" / "profile.json").read_text(encoding="utf-8"))
titres = [l["titre"].replace("CHINESE", "JAPANESE")
          for l in profil["detail"] if l["genre"] == "chapter"]
(TMP / "content" / "titres.txt").write_text("\n".join(titres) + "\n", encoding="utf-8")

# Le livre de référence est mis de côté, comme après la mesure.
(TMP / "content" / "book_typed.json").rename(TMP / "content" / "reference_typed.json")

# ---------------------------------------------------------------- 2. plan sans curriculum
lancer("plan.py", "--config", "config/japanese.json", "--titres", "content/titres.txt")
plan = json.loads((TMP / "content" / "plan.json").read_text(encoding="utf-8"))
impose = sum(len(l.get("vocabulaire") or []) for l in plan["lecons"])
ok("sans curriculum validé, le plan n'impose aucun mot chinois", impose == 0,
   f"{impose} entrées imposées")

r = lancer("check_generation.py", attendu=1)
ok("les contrôles refusent de laisser générer dans cet état",
   "the plan imposes 0 vocabulary entries" in r.stdout, r.stdout[-300:])

# ---------------------------------------------------------------- 3. progression + décisions
# Ce que propose_vocab.py aurait rendu, sans l'appel payant.
(TMP / "content" / "vocabulaire_propose.json").write_text(json.dumps({
    "langue": "ja", "lecons": [
        {"n": i, "titre": t, "entrees": [
            {"ecriture": "みず", "prononciation": "mizu", "sens": "water"},
            {"ecriture": "ひと", "prononciation": "hito", "sens": "person"},
            {"ecriture": "やま", "prononciation": "yama", "sens": "mountain"}]}
        for i, t in enumerate(titres, 1)]}, ensure_ascii=False), encoding="utf-8")

# Le professeur tranche : une corrigée, une écartée, une gardée.
sys.path.insert(0, str(PIPELINE))
os.environ["WB_LANGUE"] = "japanese"
from ids import Numeroteur                                       # noqa: E402
from pairs import tc                                             # noqa: E402
# Les identifiants sont recalculés par la même fonction que le bundle : c'est
# exactement ce qui avait cassé une fois, un titre mis en capitales d'un côté
# et pas de l'autre.
numero = Numeroteur()
ids = {}
ENTREES = [("みず", "mizu", "water"), ("ひと", "hito", "person"),
           ("やま", "yama", "mountain")]
for i, t in enumerate(titres, 1):
    for ecriture, prononciation, sens in ENTREES:
        ids[(i, ecriture)] = numero("vocabulaire", tc(t), ecriture,
                                    f"{prononciation} — {sens}")
(TMP / "content" / "decisions.json").write_text(json.dumps([
    {"item_id": ids[(1, "ひと")], "kind": "vocabulaire", "action": "fix",
     "value": "じん jin", "by": "prof"},
    {"item_id": ids[(1, "やま")], "kind": "vocabulaire", "action": "drop",
     "value": "", "by": "prof"},
], ensure_ascii=False), encoding="utf-8")

lancer("apply_vocab.py")
valide = json.loads((TMP / "content" / "vocabulaire_valide.json").read_text(encoding="utf-8"))
l1 = next(l for l in valide["lecons"] if l["n"] == 1)
formes = {e["ecriture"] for e in l1["entrees"]}
ok("l'entrée écartée par le professeur disparaît du curriculum",
   "やま" not in formes, str(formes))
ok("l'entrée corrigée prend la forme qu'il a écrite", "じん" in formes, str(formes))
ok("l'entrée validée reste", "みず" in formes, str(formes))

# ---------------------------------------------------------------- 4. replanification
lancer("plan.py", "--config", "config/japanese.json", "--titres", "content/titres.txt")
plan = json.loads((TMP / "content" / "plan.json").read_text(encoding="utf-8"))
impose = [m for l in plan["lecons"] for m in (l.get("vocabulaire") or [])]
ok("le plan reprend le curriculum validé", len(impose) > 0, str(len(impose)))
ok("et il est en japonais, pas en chinois",
   all(any("぀" <= c <= "ヿ" for c in m["zh"]) for m in impose),
   str([m["zh"] for m in impose[:5]]))

r = lancer("check_generation.py")
ok("les contrôles passent une fois le curriculum en place",
   "0 vocabulary entries" not in r.stdout, r.stdout[-300:])
ok("et ils confirment que le prompt ne porte que le vocabulaire prévu",
   "the lesson 1 prompt holds only the planned vocabulary" in r.stdout,
   r.stdout[-400:])

# ---------------------------------------------------------------- 5. leçons
# Ce que le modèle aurait rendu. On écrit une leçon chinoise pour la première :
# elle doit être refusée, pas convertie.
genere = TMP / "content" / "generated"
genere.mkdir(parents=True, exist_ok=True)


def brute(mots, prononciations):
    return {"titre": "T", "vocabulaire_nouveau": [
        {"zh": m, "pinyin": p, "en": "x"} for m, p in zip(mots, prononciations)],
        "sections": [{"titre": "S", "paragraphes": ["Prose."],
                      "tableaux": [{"entetes": ["A", "B"], "lignes": [
                          {"zh": m, "pinyin": p, "en": "x"}
                          for m, p in zip(mots, prononciations)]}],
                      "dialogue": [{"locuteur": "A", "zh": mots[0],
                                    "pinyin": prononciations[0], "en": "x"}]}],
        "exercices": [{"titre": "E", "type": "mcq", "consigne": "Choose.",
                       "items": [{"enonce": "Q", "options": ["A", "B"],
                                  "reponse": "A"}]}]}


(genere / "lecon_01_brut.json").write_text(
    json.dumps(brute(["你好", "再见"], ["nǐ hǎo", "zài jiàn"]), ensure_ascii=False),
    encoding="utf-8")
r = lancer("generate.py", "--toutes", "--reconvertir", attendu=1)
ok("une sortie brute en chinois est refusée à la reconversion",
   "not written in Japanese" in r.stdout, r.stdout[-300:])
ok("et rien n'est écrit sur le disque pour elle",
   not (genere / "lecon_01.json").exists())

for i in range(1, len(titres) + 1):
    (genere / f"lecon_{i:02d}_brut.json").write_text(
        json.dumps(brute(["みず", "ひと"], ["mizu", "hito"]), ensure_ascii=False),
        encoding="utf-8")
r = lancer("generate.py", "--toutes", "--reconvertir")
ok("des leçons japonaises se convertissent",
   all((genere / f"lecon_{i:02d}.json").exists() for i in range(1, len(titres) + 1)),
   r.stdout[-200:])

# ---------------------------------------------------------------- 6. assemblage
r = lancer("assemble.py")
livre = json.loads((TMP / "content" / "book.json").read_text(encoding="utf-8"))
ok("le livre assemblé porte le titre de la langue cible",
   livre["meta"]["cover_title"] == "LEARN JAPANESE", str(livre["meta"]))
ok("le chapitre de corrigés de la référence est retiré",
   not any(c["kind"] == "answers" for c in livre["chapters"]))

textes = json.dumps(livre, ensure_ascii=False)
ok("aucun mot de la langue de référence ne subsiste dans les leçons",
   not any("一" <= c <= "鿿" and c not in "" for c in
           json.dumps([c for c in livre["chapters"] if c["kind"] == "chapter"],
                      ensure_ascii=False)),
   "des sinogrammes subsistent")
ok("le japonais est bien présent", "みず" in textes)

# ---------------------------------------------------------------- 7. PDF
lancer("exercises.py")
lancer("validate.py")
lancer("answerkeys.py")
typst = shutil.which("typst") or (str(REPO / ".bin" / "typst")
                                  if (REPO / ".bin" / "typst").exists() else None)
if typst:
    r = subprocess.run([typst, "compile", "--font-path", "fonts", "--root", ".",
                        "templates/book.typ", "output/book.pdf"],
                       cwd=TMP, capture_output=True, text=True)
    ok("le livre japonais compile", r.returncode == 0, r.stderr[-500:])
    pdf = TMP / "output" / "book.pdf"
    ok("et produit un PDF non vide", pdf.exists() and pdf.stat().st_size > 5000,
       str(pdf.stat().st_size if pdf.exists() else 0))
    try:
        from pypdf import PdfReader
        texte = "\n".join((p.extract_text() or "") for p in PdfReader(str(pdf)).pages)
        ok("la couverture n'annonce plus le chinois",
           "LEARN CHINESE" not in texte and "LEARN JAPANESE" in texte,
           texte[:200])
        ok("le PDF contient des kana",
           any("぀" <= c <= "ヿ" for c in texte))
    except ImportError:
        ok("pypdf absent : contenu du PDF non relu", True, "installer pypdf")
else:
    ok("typst absent : compilation non vérifiée", True, "binaire introuvable")

shutil.rmtree(TMP, ignore_errors=True)
rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
