#!/usr/bin/env python3
"""Glossaire maître, voix maison, contrôle de conformité d'une leçon.

Ces trois briques précèdent toute génération : ce qui est vérifiable par code
ne doit pas être confié à un modèle. Le contrôle de conformité est le plus
délicat — s'il recale des leçons écrites par des humains et validées par un
professeur, il ne sera plus lu.

    python3 tests/test_generation.py
"""
import copy, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_book import BOOK                                    # noqa: E402

PIPELINE = REPO / "pipeline"

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


def atelier(book):
    """Un espace de travail avec le livre donné et le code du dépôt."""
    tmp = Path(tempfile.mkdtemp(prefix="wb-gen-"))
    (tmp / "content").mkdir()
    (tmp / "config").mkdir()
    shutil.copy2(REPO / "config" / "chinese.json", tmp / "config" / "chinese.json")
    (tmp / "content" / "book_typed.json").write_text(
        json.dumps(book, ensure_ascii=False), encoding="utf-8")
    return tmp


def lancer(tmp, script, *args):
    r = subprocess.run([sys.executable, str(PIPELINE / script), *args],
                       cwd=tmp, capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(f"{script} a échoué :\n{r.stderr}")
    return r.stdout


def charger(tmp, nom):
    return json.loads((tmp / "content" / nom).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- glossaire
tmp = atelier(BOOK)
lancer(tmp, "glossary.py")
g = charger(tmp, "glossary.json")

ok("un caractère est daté de sa première apparition",
   g["caracteres"]["好"] == 1 and g["caracteres"]["再"] == 1, str(g["caracteres"].get("好")))

tardif = copy.deepcopy(BOOK)
tardif["chapters"].append({"kind": "chapter", "num": 2, "title": "PLUS TARD", "blocks": [
    {"type": "para", "text": "Later {zh:机场} {py:jīchǎng} appears."}]})
t2 = atelier(tardif)
lancer(t2, "glossary.py")
g2 = charger(t2, "glossary.json")
ok("un caractère introduit plus loin porte une position ultérieure",
   g2["caracteres"]["机"] > g2["caracteres"]["好"],
   f"机 en {g2['caracteres'].get('机')}, 好 en {g2['caracteres'].get('好')}")

ok("une paire courte est une entrée de vocabulaire", "你好" in g["mots"])
ok("une phrase d'exemple n'en est pas une",
   not any(len(m) > 4 for m in g["mots"]), str([m for m in g["mots"] if len(m) > 4]))
ok("la prononciation accompagne l'entrée", g["mots"]["你好"]["pinyin"] == "nǐ hǎo")

# les caractères sont relevés partout, pas seulement dans les paires balisées
brut = copy.deepcopy(BOOK)
brut["chapters"][1]["blocks"].append({"type": "para", "text": "Note : 山 is a mountain."})
t3 = atelier(brut)
lancer(t3, "glossary.py")
ok("un caractère hors balise compte quand même comme vu",
   "山" in charger(t3, "glossary.json")["caracteres"])

# ---------------------------------------------------------------- style
lancer(tmp, "style.py")
st = charger(tmp, "style.json")
ok("les consignes sont groupées par type d'exercice",
   "translation" in st["consignes"], str(list(st["consignes"])))
ok("le pinyin à tons ne pollue pas les tournures",
   not any(any(c in g for c in "āǎěǐǒūǔ") for g in
           dict(st["repetition_humaine"]["les_plus_frequents"])),
   str(st["repetition_humaine"]["les_plus_frequents"][:3]))
ok("la base de répétition humaine est chiffrée",
   st["repetition_humaine"]["ngrams_distincts"] > 0
   and "part_repetee" in st["repetition_humaine"])

# ---------------------------------------------------------------- conformité
# La fixture porte un exercice sans réponses — le contrôle a raison de le
# signaler, mais ce n'est pas ce qu'on teste ici : on le complète.
LIVRE = copy.deepcopy(BOOK)
LIVRE["chapters"][1]["blocks"][4]["answers"] = [{"n": 1, "text": "bye"}]

PLAN = {"langue": "zh-Hans", "reference": "essai", "totaux": {},
        "lecons": [{"n": 1, "titre": "GREETINGS", "exercices": ["translation"],
                    "quotas": {"mots_prose": {"cible": 5, "min": 1, "max": 50},
                               "tableaux": {"cible": 1, "min": 1, "max": 3},
                               "dialogues": {"cible": 1, "min": 0, "max": 3},
                               "repliques": {"cible": 3, "min": 1, "max": 9},
                               "exercices": {"cible": 2, "min": 1, "max": 4},
                               "sections": {"cible": 0, "min": 0, "max": 3}}}]}


def controler(book, plan=None, serre=False):
    t = atelier(book)
    (t / "content" / "plan.json").write_text(
        json.dumps(plan or PLAN, ensure_ascii=False), encoding="utf-8")
    lancer(t, "glossary.py")
    lancer(t, "style.py")
    return lancer(t, "check_lesson.py", *(["--serre"] if serre else []))


sortie = controler(LIVRE)
ok("une leçon conforme ne déclenche rien",
   "0/1 leçons du livre validé sont signalées" in sortie, sortie.strip()[-200:])

etroit = copy.deepcopy(PLAN)
etroit["lecons"][0]["quotas"]["tableaux"] = {"cible": 9, "min": 8, "max": 12}
ok("un quota hors bande est signalé",
   "[quota] tableaux" in controler(LIVRE, etroit), "")

# un exercice qui emploie un caractère jamais enseigné
# Employé dans un énoncé, jamais présenté avec sa prononciation : non enseigné.
# (Une réplique de dialogue ou un tableau, eux, enseignent — mesuré sur le CN10.)
inconnu = copy.deepcopy(LIVRE)
inconnu["chapters"][1]["blocks"][4]["blocks"].append(
    {"type": "para", "text": "Complete the sentence with 蛋糕 or another word."})
sortie = controler(inconnu)
ok("un exercice employant du vocabulaire non enseigné est signalé",
   "[vocabulaire]" in sortie and "蛋" in sortie, sortie.strip()[-220:])

# deux bandes pour deux usages : large sur l'humain, serrée sur le généré
large = copy.deepcopy(PLAN)
large["lecons"][0]["quotas"]["tableaux"] = {"cible": 4, "min": 1, "max": 5}
ok("dans l'étendue humaine, un écart à la cible passe",
   "[quota] tableaux" not in controler(LIVRE, large))
ok("...mais la bande serrée le signale",
   "[quota] tableaux" in controler(LIVRE, large, serre=True))

# une leçon a le droit d'exercer ce qu'elle vient elle-même d'enseigner
enseigne_ici = copy.deepcopy(inconnu)
enseigne_ici["chapters"][1]["blocks"].append(
    {"type": "table", "ncols": 2,
     "rows": [["Chinese", "What it means"], ["{zh:蛋糕} {py:dàngāo}", "cake"]]})
sortie = controler(enseigne_ici)
ok("le vocabulaire présenté dans un tableau de la leçon est exerçable",
   "[vocabulaire]" not in sortie, sortie.strip()[-200:])

# le même caractère, enseigné avant dans la prose, ne doit plus rien déclencher
enseigne = copy.deepcopy(inconnu)
enseigne["chapters"][1]["blocks"].insert(
    0, {"type": "para", "text": "Try {zh:蛋糕}*{py:dàngāo}* — cake."})
sortie = controler(enseigne)
ok("enseigné d'abord dans la prose, il ne l'est plus",
   "[vocabulaire]" not in sortie, sortie.strip()[-220:])
ok("...y compris quand la mise en gras sépare les deux balises",
   "0/1 leçons" in sortie, sortie.strip()[-160:])

for t in (tmp, t2, t3):
    shutil.rmtree(t, ignore_errors=True)

# ---------------------------------------------------------------- file vocabulaire
PROPOSE = {"langue": "ja", "lecons": [
    {"n": 1, "titre": "PREMIERS MOTS", "entrees": [
        {"ecriture": "わたし", "prononciation": "watashi", "sens": "I, me"},
        {"ecriture": "あなた", "prononciation": "anata", "sens": "you"}]},
    {"n": 2, "titre": "SALUER", "entrees": [
        {"ecriture": "こんにちは", "prononciation": "konnichiwa", "sens": "hello"}]}]}


def bundle_vocabulaire(avec_livre):
    t = Path(tempfile.mkdtemp(prefix="wb-vocab-"))
    (t / "content").mkdir()
    if avec_livre:
        (t / "content" / "book_typed.json").write_text(
            json.dumps(LIVRE, ensure_ascii=False), encoding="utf-8")
    (t / "content" / "vocabulaire_propose.json").write_text(
        json.dumps(PROPOSE, ensure_ascii=False), encoding="utf-8")
    subprocess.run([sys.executable, str(PIPELINE / "bundle.py")], cwd=t,
                   capture_output=True, text=True, check=True)
    b = json.loads((t / "output" / "review.json").read_text(encoding="utf-8"))
    shutil.rmtree(t, ignore_errors=True)
    return b


sans = bundle_vocabulaire(False)
ok("la file de vocabulaire existe avant tout livre",
   sans["queues"].get("vocab") == 3, str(sans["queues"]))
ok("chaque entrée proposée devient une fiche à trancher",
   {i["title"] for i in sans["items"]} == {"わたし", "あなた", "こんにちは"},
   str([i["title"] for i in sans["items"]]))
ok("la fiche porte prononciation et sens",
   all(i.get("prononciation") and i.get("sens")
       for i in sans["items"] if i["kind"] == "vocabulaire"))
ok("les identifiants y sont stables comme ailleurs",
   [i["id"] for i in bundle_vocabulaire(False)["items"]] == [i["id"] for i in sans["items"]])

avec = bundle_vocabulaire(True)
ok("elle cohabite avec les files d'un livre existant",
   avec["queues"].get("vocab") == 3 and len(avec["queues"]) > 1, str(avec["queues"]))

# ---------------------------------------------------------------- curriculum validé
def curriculum(decisions):
    """propose_vocab → bundle → décisions du professeur → apply_vocab."""
    t = Path(tempfile.mkdtemp(prefix="wb-curr-"))
    (t / "content").mkdir()
    (t / "content" / "vocabulaire_propose.json").write_text(
        json.dumps(PROPOSE, ensure_ascii=False), encoding="utf-8")
    env = {**os.environ, "WB_LANGUE": "japanese"}
    subprocess.run([sys.executable, str(PIPELINE / "bundle.py")], cwd=t, env=env,
                   capture_output=True, check=True)
    ids = [i["id"] for i in json.loads(
        (t / "output" / "review.json").read_text(encoding="utf-8"))["items"]]
    (t / "content" / "decisions.json").write_text(
        json.dumps([{**d, "item_id": ids[d.pop("rang")], "kind": "vocabulaire"}
                    for d in decisions], ensure_ascii=False), encoding="utf-8")
    subprocess.run([sys.executable, str(PIPELINE / "apply_vocab.py")], cwd=t, env=env,
                   capture_output=True, text=True, check=True)
    v = json.loads((t / "content" / "vocabulaire_valide.json").read_text(encoding="utf-8"))
    shutil.rmtree(t, ignore_errors=True)
    return [e for l in v["lecons"] for e in l["entrees"]]


garde = curriculum([{"rang": 0, "action": "ok", "by": "Yuki"}])
ok("une entrée validée est retenue telle quelle",
   garde[0]["ecriture"] == "わたし" and garde[0]["prononciation"] == "watashi")

ecarte = curriculum([{"rang": 1, "action": "drop", "by": "Yuki"}])
ok("une entrée écartée disparaît du curriculum",
   "あなた" not in [e["ecriture"] for e in ecarte] and len(ecarte) == len(garde) - 1,
   str([e["ecriture"] for e in ecarte]))

pron = curriculum([{"rang": 0, "action": "fix", "value": "watakushi", "by": "Yuki"}])
ok("une correction sans écriture cible corrige la prononciation",
   pron[0]["ecriture"] == "わたし" and pron[0]["prononciation"] == "watakushi",
   f"{pron[0]['ecriture']} / {pron[0]['prononciation']}")

mot = curriculum([{"rang": 0, "action": "fix", "value": "ぼく boku", "by": "Yuki"}])
ok("une correction contenant de l'écriture cible remplace le mot",
   mot[0]["ecriture"] == "ぼく" and mot[0]["prononciation"] == "boku",
   f"{mot[0]['ecriture']} / {mot[0]['prononciation']}")

ok("le sens proposé est conservé quand seule la forme change",
   mot[0]["sens"] == "I, me", mot[0]["sens"])

# ------------------------------------------------- le prompt d'une autre langue
# Le livre japonais a été écrit en chinois parce que le prompt recevait le
# glossaire et les paragraphes du livre chinois : le seul contenu concret qu'il
# contenait était chinois. Ce garde-fou existait dans plan.py, pas ici.
import importlib                                                 # noqa: E402
sys.path.insert(0, str(REPO / "pipeline"))
os.environ["WB_LANGUE"] = "japanese"
import langue as _lg                                             # noqa: E402
importlib.reload(_lg)
import generate as _gen                                          # noqa: E402
importlib.reload(_gen)

GLOSSAIRE_ZH = {"langue": "zh-Hans",
                "mots": {"你好": {"pinyin": "nǐ hǎo", "lecon": 1}},
                "caracteres": {"你": 1, "好": 1}}
STYLE_ZH = {"consignes": {"mcq": [{"titre": "T", "consigne": "Choose 你好 or 再见."}]},
            "paragraphes_types": [
                {"texte": "You're walking down a busy street in China. Say {zh:你好} {py:nǐ hǎo}."}]}

g2, s2 = _gen.materiau(GLOSSAIRE_ZH, STYLE_ZH)
ok("le glossaire d'une autre langue est écarté du prompt", g2["mots"] == {}, str(g2["mots"]))
ok("ses caractères aussi", g2["caracteres"] == {}, str(g2["caracteres"]))
ok("les paragraphes types sont gardés — le ton se transporte",
   len(s2["paragraphes_types"]) == 1)
ok("mais leurs mots étrangers sont retirés",
   "你好" not in s2["paragraphes_types"][0]["texte"],
   s2["paragraphes_types"][0]["texte"])
ok("les consignes d'exercices aussi",
   "你好" not in s2["consignes"]["mcq"][0]["consigne"],
   s2["consignes"]["mcq"][0]["consigne"])
ok("le prompt saura d'où viennent ces exemples",
   s2.get("_source_etrangere") == "zh-Hans", str(s2.get("_source_etrangere")))

g3, s3 = _gen.materiau({"langue": "ja", "mots": {"あ": {"pinyin": "a", "lecon": 1}},
                        "caracteres": {"あ": 1}}, STYLE_ZH)
ok("le glossaire de la bonne langue est conservé", g3["mots"] != {})

# --- une leçon dans la mauvaise langue ne s'écrit pas sur le disque
LECON_ZH = {"sections": [{"tableaux": [{"lignes": [
    {"zh": "你好", "pinyin": "nǐ hǎo", "en": "hello"},
    {"zh": "再见", "pinyin": "zài jiàn", "en": "bye"}]}]}]}
LECON_JA = {"sections": [{"tableaux": [{"lignes": [
    {"zh": "こんにちは", "pinyin": "konnichiwa", "en": "hello"},
    {"zh": "さようなら", "pinyin": "sayōnara", "en": "bye"}]}]}]}
refuse = False
try:
    _gen.refuser_si_autre_langue(LECON_ZH, 2)
except RuntimeError as e:
    refuse, message = True, str(e)
ok("une leçon chinoise est refusée dans un livre japonais", refuse)
ok("et le refus nomme la langue attendue", refuse and "Japanese" in message, locals().get("message", ""))
_gen.refuser_si_autre_langue(LECON_JA, 2)
ok("une leçon japonaise passe", True)

# --- l'assemblage refuse un livre à moitié dans l'autre langue
import subprocess as _sp                                         # noqa: E402
bac_a = Path(tempfile.mkdtemp(prefix="wb-asm-"))
(bac_a / "content").mkdir()
(bac_a / "content" / "book_typed.json").write_text(json.dumps(
    {"meta": {}, "chapters": [
        {"kind": "chapter", "num": 1, "title": "UNE", "blocks": []},
        {"kind": "chapter", "num": 2, "title": "DEUX", "blocks": []}]}),
    encoding="utf-8")
(bac_a / "content" / "glossary.json").write_text(
    json.dumps({"langue": "zh-Hans", "mots": {}, "caracteres": {}}), encoding="utf-8")
r_asm = _sp.run([sys.executable, str(PIPELINE / "assemble.py")], cwd=bac_a,
                capture_output=True, text=True,
                env={**os.environ, "WB_LANGUE": "japanese"})
ok("assembler avec des leçons manquantes et une référence chinoise est refusé",
   r_asm.returncode != 0, r_asm.stdout[-200:])
ok("et le refus dit lesquelles manquent et pourquoi",
   "Japanese" in r_asm.stderr and "missing" in r_asm.stderr, r_asm.stderr[-200:])

r_asm = _sp.run([sys.executable, str(PIPELINE / "assemble.py")], cwd=bac_a,
                capture_output=True, text=True,
                env={**os.environ, "WB_LANGUE": "chinese"})
ok("dans la même langue, la reprise reste permise — c'est un brouillon lisible",
   r_asm.returncode == 0, r_asm.stderr[-200:])
titre = json.loads((bac_a / "content" / "book.json").read_text(encoding="utf-8"))["meta"]
ok("et le titre du livre vient de la langue", titre["cover_title"] == "LEARN CHINESE",
   str(titre))
shutil.rmtree(bac_a, ignore_errors=True)

os.environ.pop("WB_LANGUE", None)

# ------------------------------------------------- profondeur de réflexion
# Mesuré sur la leçon 5 du CN10 : la réflexion est 79 % de ce qu'on paie à
# l'effort par défaut. C'est le premier poste de dépense, et il se règle.
ok("le format imposé est demandé quoi qu'il arrive",
   _gen.sortie_demandee()["format"]["type"] == "json_schema")
ok("sans effort demandé, on n'envoie pas le champ",
   "effort" not in _gen.sortie_demandee(),
   "le défaut de l'API est high ; l'écrire n'apporterait rien")
ok("l'effort voyage dans le même output_config que le schéma",
   _gen.sortie_demandee("low") == {"format": {"type": "json_schema",
                                              "schema": _gen.SCHEMA},
                                   "effort": "low"},
   "c'est la place que lui donne l'API")

# ------------------------------------------------- personne ne code le nom en dur
# generate.py cherchait `content/book_typed.json`, que l'étape de mesure avait
# déjà renommé : trois leçons perdues sur un FileNotFoundError. Lancer le script
# ne l'aurait pas montré — il sort avant, sur l'absence de clé. Ce qui se
# vérifie, c'est la règle elle-même : les étapes qui tournent après la mesure
# passent par livre.py et ne nomment aucun des deux fichiers en dur.
for script in ("generate.py", "assemble.py"):
    texte = (REPO / "pipeline" / script).read_text(encoding="utf-8")
    code = "\n".join(l for l in texte.splitlines() if not l.strip().startswith("#"))
    ok(f"{script} ne code pas le nom du livre de référence en dur",
       "content/book_typed.json" not in code and
       "content/reference_typed.json" not in code,
       script)
    ok(f"{script} passe par livre.py", "import livre" in code, script)

# ---------------------------------------------------------------- livre de référence
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import livre                                                     # noqa: E402

bac = Path(tempfile.mkdtemp(prefix="wb-ref-"))
(bac / "content").mkdir()
ici = os.getcwd()
os.chdir(bac)
try:
    manque = False
    try:
        livre.chemin()
    except FileNotFoundError:
        manque = True
    ok("sans livre de référence, l'erreur nomme les deux fichiers cherchés", manque)

    (bac / "content" / "book_typed.json").write_text('{"lessons": []}', encoding="utf-8")
    ok("le livre déposé est trouvé", livre.chemin() == "content/book_typed.json")
    ok("et il se charge", livre.charger() == {"lessons": []})

    # Après la mesure, le livre est renommé pour ne pas polluer les files : c'est
    # ce renommage qui faisait échouer la génération leçon après leçon.
    (bac / "content" / "book_typed.json").rename(bac / "content" / "reference_typed.json")
    ok("le livre mis de côté est trouvé aussi",
       livre.chemin() == "content/reference_typed.json")
    ok("et il se charge encore", livre.charger() == {"lessons": []})
finally:
    os.chdir(ici)
    shutil.rmtree(bac, ignore_errors=True)

# ---------------------------------------------------------------- la clé d'API
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import modele                                                    # noqa: E402

garde = os.environ.get("ANTHROPIC_API_KEY")
os.environ["ANTHROPIC_API_KEY"] = "  sk-ant-faux-pour-le-test\n"
ok("les blancs autour de la clé sont retirés",
   modele.cle() == "sk-ant-faux-pour-le-test", repr(modele.cle()))
ok("une clé nettoyée ne contient aucun caractère interdit en en-tête",
   "\n" not in modele.cle() and "\r" not in modele.cle())
os.environ.pop("ANTHROPIC_API_KEY")
ok("sans clé, on renvoie une chaîne vide, pas None", modele.cle() == "")
if garde is not None:
    os.environ["ANTHROPIC_API_KEY"] = garde

rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
