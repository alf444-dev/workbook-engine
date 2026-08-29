#!/usr/bin/env python3
"""Plusieurs relecteurs à la fois, sans se marcher dessus.

C'est une exigence du brief : six personnes en interne, des professeurs
externes, tous sur le même livre en même temps. SQLite en WAL le permet, mais
« permet » n'est pas « fait » — un `busy_timeout` trop court ou une écriture
hors transaction se voit seulement sous charge.

On mesure donc : aucune décision perdue, aucun numéro de séquence en double,
aucune base verrouillée, et le journal reste append-only.

    python3 tests/test_concurrence.py
"""
import json, os, shutil, sys, tempfile, threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="wb-conc-"))
os.environ["WB_DATA"] = str(TMP)
os.environ["WB_ADMIN_TOKEN"] = "jeton"
sys.path.insert(0, str(REPO / "server"))

from fastapi.testclient import TestClient                        # noqa: E402
import store, workspace, app as appmod                           # noqa: E402

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


store.init()
pid = store.create_project("Concurrence", "x.docx")

RELECTEURS = 8
PAR_RELECTEUR = 25
ITEMS = [f"pinyin-{i:03d}" for i in range(PAR_RELECTEUR)]

ws = workspace.workspace(pid)
(ws / "output").mkdir(parents=True, exist_ok=True)
(ws / "output" / "review.json").write_text(json.dumps({
    "project": "c", "source": "x.docx", "id_scheme": 1,
    "stats": {"lessons": 0, "blocks": 0, "exercises": 0, "pairs_checked": 0},
    "lessons": [],
    "items": [{"id": i, "kind": "pinyin", "queue": "teacher", "lesson": "L",
               "lesson_id": "l", "title": "你好", "detail": "d", "target": None,
               "zh": "你好", "pinyin": "x"} for i in ITEMS]}), encoding="utf-8")

# ---------------------------------------------------------------- 1. écritures directes
erreurs, sequences = [], []
verrou = threading.Lock()


def travailler(n):
    try:
        for item in ITEMS:
            seq = store.record(pid, item, "teacher", "fix", f"valeur-{n}",
                               f"relecteur-{n}", {"kind": "pinyin"})
            with verrou:
                sequences.append(seq)
    except Exception as e:                                   # noqa: BLE001
        with verrou:
            erreurs.append(f"{type(e).__name__}: {e}")


fils = [threading.Thread(target=travailler, args=(n,)) for n in range(RELECTEURS)]
for f in fils:
    f.start()
for f in fils:
    f.join()

attendu = RELECTEURS * PAR_RELECTEUR
ok("aucune écriture ne tombe sur une base verrouillée", not erreurs,
   "\n      ".join(erreurs[:4]))
ok(f"les {attendu} décisions sont toutes écrites", len(sequences) == attendu,
   str(len(sequences)))
ok("aucun numéro de séquence en double", len(set(sequences)) == len(sequences),
   f"{len(sequences) - len(set(sequences))} doublons")

with store.connect() as cx:
    total = cx.execute("SELECT count(*) FROM decisions WHERE project_id=?",
                       (pid,)).fetchone()[0]
ok("et elles sont toutes en base", total == attendu, str(total))

courant = store.current(pid)
ok("chaque item n'a qu'un état courant", len(courant) == PAR_RELECTEUR,
   str(len(courant)))
ok("le journal garde toute l'histoire, il n'écrase rien",
   len(store.history(pid, ITEMS[0])) == RELECTEURS,
   str(len(store.history(pid, ITEMS[0]))))
ok("l'état courant est la dernière décision, pas une au hasard",
   all(d["seq"] == max(h["seq"] for h in store.history(pid, i))
       for i, d in courant.items()))

# ---------------------------------------------------------------- 2. par le serveur
client = TestClient(appmod.app)
jeton = next(l["token"] for l in store.links_for(pid) if l["role"] == "teacher")
client.get(f"/r/{jeton}", follow_redirects=True)

reponses, soucis = [], []


def poster(n):
    c = TestClient(appmod.app)
    c.get(f"/r/{jeton}", follow_redirects=True)
    for item in ITEMS[:10]:
        try:
            r = c.post(f"/p/{pid}/teacher/decisions",
                       json={"item_id": item, "action": "ok", "by": f"r{n}"})
            with verrou:
                reponses.append(r.status_code)
        except Exception as e:                               # noqa: BLE001
            with verrou:
                soucis.append(f"{type(e).__name__}: {e}")


fils = [threading.Thread(target=poster, args=(n,)) for n in range(RELECTEURS)]
for f in fils:
    f.start()
for f in fils:
    f.join()

ok("aucune requête ne casse sous la simultanéité", not soucis,
   "\n      ".join(soucis[:4]))
ok("toutes les décisions passent par HTTP",
   reponses and all(s == 200 for s in reponses),
   str(sorted(set(reponses))))

# ---------------------------------------------------------------- 3. lecture pendant écriture
# Les deux côtés font un nombre de tours fixe : sinon les écritures finissent
# avant la première lecture et le test ne mesure rien.
LECTURES, ECRITURES = 40, 300
lu, ecrit = [], []


def lire():
    c = TestClient(appmod.app)
    c.get(f"/r/{jeton}", follow_redirects=True)
    for _ in range(LECTURES):
        r = c.get(f"/p/{pid}/teacher/decisions")
        with verrou:
            lu.append(r.status_code)


def ecrire():
    for n in range(ECRITURES):
        try:
            store.record(pid, ITEMS[n % len(ITEMS)], "teacher", "fix",
                         f"pendant-{n}", "x", {})
            with verrou:
                ecrit.append(True)
        except Exception as e:                               # noqa: BLE001
            with verrou:
                ecrit.append(f"{type(e).__name__}: {e}")


fils = [threading.Thread(target=lire) for _ in range(3)] + \
       [threading.Thread(target=ecrire) for _ in range(3)]
for f in fils:
    f.start()
for f in fils:
    f.join()

ok("les lectures ont bien eu lieu pendant les écritures",
   len(lu) == 3 * LECTURES and len(ecrit) == 3 * ECRITURES,
   f"{len(lu)} lectures, {len(ecrit)} écritures")
ok("lire la file pendant que d'autres écrivent ne casse jamais",
   lu and all(s == 200 for s in lu), str(sorted(set(lu))))
ok("et aucune écriture n'échoue pendant les lectures",
   all(e is True for e in ecrit),
   str([e for e in ecrit if e is not True][:3]))

shutil.rmtree(TMP, ignore_errors=True)
rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
