#!/usr/bin/env python3
"""Créer un livre dans n'importe quelle langue, sans développeur.

Jusqu'ici, lancer un titre en coréen demandait qu'on écrive un fichier de
config à la main. Ce test couvre la chaîne entière : la table des écritures, le
générateur de config, l'endpoint, la persistance sur le disque — et surtout que
la config produite traverse réellement le moteur.

    python3 tests/test_langues.py
"""
import json, os, re, shutil, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="wb-langues-"))
os.environ["WB_DATA"] = str(TMP)
os.environ["WB_ADMIN_TOKEN"] = "jeton"
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "server"))

import ecritures, nouvelle_langue                                # noqa: E402

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


# ---------------------------------------------------------------- les écritures
EXEMPLES = {
    "hangul": ("안녕하세요", ["こんにちは", "你好", "Hello"]),
    "kana-kanji": ("こんにちは", ["안녕하세요", "Hello"]),
    "han-simplifie": ("你好", ["こんにちは", "Hello"]),
    "cyrillique": ("Привет", ["Hello", "你好"]),
    "grec": ("Γειά σου", ["Hello", "Привет"]),
    "arabe": ("مرحبا", ["Hello", "שלום"]),
    "hebreu": ("שלום", ["Hello", "مرحبا"]),
    "thai": ("สวัสดี", ["Hello", "你好"]),
    "devanagari": ("नमस्ते", ["Hello", "สวัสดี"]),
}
for cle, (sien, etrangers) in EXEMPLES.items():
    e = ecritures.ECRITURES[cle]
    plage = re.compile(f"[{e['plage']}]")
    ok(f"{cle} reconnaît son écriture", bool(plage.search(sien)), sien)
    for etranger in etrangers:
        if etranger == "Hello":
            ok(f"{cle} ne prend pas l'anglais pour la langue cible",
               not plage.search(etranger))
ok("aucune écriture ne mord sur l'anglais",
   not any(re.search(f"[{e['plage']}]", "Hello world, 2026.")
           for e in ecritures.ECRITURES.values() if e["plage"]))
ok("le japonais a une signature, sinon le chinois y passerait",
   ecritures.ECRITURES["kana-kanji"]["signature"], "les kanji partagent le bloc des hanzi")
ok("le chinois exclut les kana",
   re.search(f"[{ecritures.ECRITURES['han-simplifie']['exclut']}]", "ひらがな"))
ok("toutes les plages non vides compilent",
   all(re.compile(f"[{e['plage']}]") for e in ecritures.ECRITURES.values()
       if e["plage"]))
# ---------------------------------------------------------------- alphabet latin
ok("l'alphabet latin est une écriture proposée", "latin" in ecritures.ECRITURES)
ok("il est en mode « mots » — compter des caractères n'y a pas de sens",
   ecritures.ECRITURES["latin"].get("mode") == "mots")
conf_es, avert_es = nouvelle_langue.construire("Spanish", "es", "latin",
                                               json.loads((REPO / "config" / "chinese.json")
                                                          .read_text(encoding="utf-8")))
ok("une config espagnole se construit", conf_es["code"] == "es")
ok("le mode voyage dans la config", conf_es["ecriture"]["mode"] == "mots")
ok("et la prononciation est une transcription phonétique",
   "respelling" in conf_es["ecriture"]["romanisation"])
(TMP / "config").mkdir(parents=True, exist_ok=True)
(TMP / "config" / "spanish.json").write_text(
    json.dumps(conf_es, ensure_ascii=False), encoding="utf-8")
import importlib                                                 # noqa: E402
import langue                                                    # noqa: E402
os.environ["WB_LANGUE"] = "spanish"
es = importlib.reload(langue)
ok("de l'espagnol passe son contrôle de langue",
   es.langue_plausible(["la playa", "buenos días", "¿cómo estás?"])[0])
ok("une écriture non latine glissée est refusée",
   not es.langue_plausible(["la playa", "你好"])[0])
ok("du japonais aussi", not es.langue_plausible(["hola", "こんにちは"])[0])
ok("le titre suit", es.titres_du_livre()["cover_title"] == "LEARN SPANISH")
ok("SCRIPT à plage vide ne matche rien au lieu de casser",
   not es.SCRIPT.search("abc 你好 123"),
   "une plage vide donnait « [] », une expression invalide")

# ---------------------------------------------------------------- la config produite
reference = json.loads((REPO / "config" / "chinese.json").read_text(encoding="utf-8"))
conf, avertissements = nouvelle_langue.construire("Korean", "ko", "hangul", reference)
sans_marqueurs = lambda d: {k: v for k, v in d.items() if not k.startswith("_")}
ok("les valeurs du gabarit sont reprises telles quelles",
   sans_marqueurs(conf["quotas_lecon"]) == sans_marqueurs(reference["quotas_lecon"])
   and sans_marqueurs(conf["structure_du_livre"])
       == sans_marqueurs(reference["structure_du_livre"]),
   "c'est le principe : même mise en page, même équilibre")
# Le point délicat : dans la config chinoise ces quotas sont « mesurés », sur le
# livre chinois. Recopiés ici, ils ne mesurent plus rien.
ok("les quotas recopiés deviennent un gabarit, plus une mesure",
   conf["quotas_lecon"].get("_provenance", "").startswith("gabarit"),
   str(conf["quotas_lecon"].get("_provenance")))
ok("et l'on garde trace de ce qu'ils étaient",
   "mesuré" in conf["quotas_lecon"].get("_provenance_origine", ""),
   str(conf["quotas_lecon"].get("_provenance_origine")))
ok("les valeurs, elles, sont identiques",
   {k: v for k, v in conf["quotas_lecon"].items() if not k.startswith("_")}
   == {k: v for k, v in reference["quotas_lecon"].items() if not k.startswith("_")})
ok("ce qui est propre à la langue est marqué éditorial",
   conf["ecriture"]["_provenance"] == "éditorial",
   "une hypothèse ne doit pas se faire passer pour une mesure")
ok("la config porte de quoi distinguer la langue de ses voisines",
   conf["ecriture"]["signature"] and conf["ecriture"]["exclut"])
ok("le nom de fichier est sûr",
   nouvelle_langue.ardoise("Français (canadien)!") == "francais_canadien")
ok("l'absence de contrôle de prononciation est signalée",
   any("prononciation" in a for a in avertissements), str(avertissements))
mauvaise = False
try:
    nouvelle_langue.construire("X", "xx", "klingon", reference)
except ValueError:
    mauvaise = True
ok("une écriture inconnue est refusée", mauvaise)

# ---------------------------------------------------------------- le moteur l'accepte
(TMP / "config").mkdir(parents=True, exist_ok=True)
nouvelle_langue.ecrire(conf, TMP / "config" / "korean.json")
os.environ["WB_LANGUE"] = "korean"
lg = importlib.reload(langue)
ok("le moteur charge une langue posée sur le disque persistant",
   lg.CODE == "ko" and lg.ANGLAIS == "Korean", f"{lg.CODE}/{lg.ANGLAIS}")
ok("elle est proposée parmi les langues connues", "korean" in lg.disponibles(),
   str(lg.disponibles()))
ok("du coréen passe son contrôle de langue",
   lg.langue_plausible(["안녕하세요", "물", "사람"])[0])
ok("du chinois y est refusé", not lg.langue_plausible(["你好", "再见"])[0])
ok("du japonais aussi", not lg.langue_plausible(["こんにちは", "みず"])[0])
ok("le titre du livre suit la langue",
   lg.titres_du_livre()["cover_title"] == "LEARN KOREAN")

# ---------------------------------------------------------------- par le serveur
from fastapi.testclient import TestClient                        # noqa: E402
import store, workspace, app as appmod                           # noqa: E402
store.init()
client = TestClient(appmod.app)
client.get("/a/jeton")

ok("les écritures sont offertes à la page",
   len(client.get("/admin/ecritures").json()["ecritures"]) == len(ecritures.ECRITURES))
r = client.post("/admin/langues", json={"nom": "Thai", "code": "th",
                                        "ecriture": "thai"})
ok("une langue se crée depuis la page", r.status_code == 200, r.text[:150])
ok("et la réponse dit ce qui reste à valider",
   r.json().get("avertissements"), r.text[:150])
ok("elle apparaît aussitôt dans la liste des langues",
   "thai" in [l["code"] for l in client.get("/admin/projects").json()["langues"]])
ok("elle est écrite sur le disque persistant, pas dans l'image",
   (TMP / "config" / "thai.json").exists()
   and not (REPO / "config" / "thai.json").exists(),
   "sinon elle disparaîtrait au déploiement suivant")
ok("un doublon est refusé",
   client.post("/admin/langues", json={"nom": "Thai", "code": "th",
                                       "ecriture": "thai"}).status_code == 409)
ok("un code qui n'en est pas un est refusé",
   client.post("/admin/langues", json={"nom": "X", "code": "123",
                                       "ecriture": "thai"}).status_code == 400)
ok("une écriture inventée est refusée",
   client.post("/admin/langues", json={"nom": "Y", "code": "yy",
                                       "ecriture": "klingon"}).status_code == 400)
ok("créer une langue exige le lien du manager",
   TestClient(appmod.app).post("/admin/langues",
                               json={"nom": "Z", "code": "zz",
                                     "ecriture": "thai"}).status_code == 403)

# ---------------------------------------------------------------- elle suit le projet
pid = store.create_project("Essai", "x.docx")
workspace.prepare(pid)
ok("un espace de travail reçoit les langues ajoutées",
   (workspace.workspace(pid) / "config" / "thai.json").exists(),
   "sinon le projet ne trouverait pas sa config")
ok("et garde celles du dépôt",
   (workspace.workspace(pid) / "config" / "chinese.json").exists())

import backup                                                    # noqa: E402
import tarfile                                                   # noqa: E402
archive = backup.archiver(horodatage="essai-langues")
with tarfile.open(archive, "r:gz") as t:
    dedans = t.getnames()
ok("la sauvegarde emporte les langues créées",
   any(n.endswith("config/thai.json") for n in dedans), str(dedans)[:200])

# ---------------------------------------------------------------- la page
page = client.get("/a/jeton", follow_redirects=True).text
ok("la page propose d'ajouter une langue", 'id="ajout-langue"' in page)
ok("et l'alphabet latin est dans la liste des écritures",
   any(e["cle"] == "latin"
       for e in client.get("/admin/ecritures").json()["ecritures"]))

shutil.rmtree(TMP, ignore_errors=True)
rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
