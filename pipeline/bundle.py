#!/usr/bin/env python3
"""Workbook Engine — bundle de relecture pour la console web.

Rassemble tout ce qu'un relecteur doit voir (et rien d'autre) dans un seul
fichier JSON : la liste des leçons, et les items signalés avec leur contexte.
"""
import hashlib, json, os, re, unicodedata
from collections import Counter

from pairs import RE_PAIR, plain, scan

BOOK = "content/book_typed.json"
OUT = "output/review.json"

book = json.load(open(BOOK))

def tc(s):
    """Casse de titre qui respecte les apostrophes et les sigles."""
    out = []
    for w in s.split():
        keep = {"CN10"}
        out.append(w if w in keep else w[:1].upper() + w[1:].lower())
    return " ".join(out)

# ---------------------------------------------------------------- leçons
lessons, section = [], None
for ch in book["chapters"]:
    if ch["kind"] == "section":
        section = f"Section {ch['num']} — {ch['title']}"
        continue
    if ch["kind"] not in ("chapter", "story", "intro", "conclusion"):
        continue
    title = (f"Story {ch['num']}: {ch['title']}" if ch["kind"] == "story" else ch["title"])
    lessons.append({"id": len(lessons), "title": tc(title), "kind": ch["kind"],
                    "section": tc(section) if section else "—"})

index_by_title = {l["title"].lower(): l["id"] for l in lessons}

def lesson_id(name):
    n = name.lower().strip()
    if n in index_by_title:
        return index_by_title[n]
    for t, i in index_by_title.items():
        if n in t or t in n:
            return i
    return None

# ---------------------------------------------------------------- items
# Les identifiants sont la clé sous laquelle les décisions des relecteurs sont
# stockées : ils doivent survivre à une recompilation. Un id dérivé du rang
# (« le 38e item produit ») désignerait un autre contenu à l'exécution suivante,
# silencieusement. On le dérive donc du contenu, ce qui garantit : même id ⇒
# même contenu. Un contenu modifié fait réapparaître l'item comme non traité —
# c'est le sens sûr de l'erreur.
ID_SCHEME = 1

items = []
_id_used = Counter()

def stable_id(kind, lesson, title, detail):
    sig = "\x00".join(str(x) for x in (ID_SCHEME, kind, lesson or "", title, detail))
    base = f"{kind}-{hashlib.sha1(sig.encode()).hexdigest()[:10]}"
    _id_used[base] += 1
    n = _id_used[base]
    return base if n == 1 else f"{base}-{n}"

def add(kind, queue, lesson, title, detail, extra=None, target=None):
    """`target` localise l'item dans content/book.json :
    {"path": [...], "field": clé ou index de colonne, "occurrence": n}
    `path` mène à l'objet contenant, `field` au texte, `occurrence` à la paire
    {zh}{py} visée dans ce texte. None quand l'item ne vient pas du manuscrit."""
    it = {"id": stable_id(kind, lesson, title, detail),
          "kind": kind, "queue": queue,
          "lesson": lesson, "lesson_id": lesson_id(lesson or ""),
          "title": title, "detail": detail, "target": target}
    if extra:
        it.update(extra)
    items.append(it)

# 1. prononciation (file du professeur natif)
pairs_checked = 0
try:
    from pypinyin import pinyin, Style
    HAS = True
except ImportError:
    HAS = False

if HAS:
    def flat(s):
        s = unicodedata.normalize("NFD", s.lower()).replace("u\u0308", "v")
        s = re.sub(r"[\u0300-\u036f]", "", s)
        return re.sub(r"[^a-zv]", "", s)

    def check(zh, py_given):
        if re.search(r"[0-9０-９]", zh):
            return True
        zh_clean = re.sub(r"[^\u4e00-\u9fff]", "", zh)
        if not zh_clean:
            return True
        for tok in re.findall(r"[A-Za-z][A-Za-z\-]*", zh):
            py_given = re.sub(re.escape(tok), "", py_given, count=1, flags=re.I)
        opts = []
        for chx in zh_clean:
            rs = set(flat(r) for r in pinyin(chx, style=Style.NORMAL, heteronym=True)[0])
            if chx == "儿": rs |= {"r", "er", ""}
            if chx == "一": rs |= {"yi"}
            if chx == "不": rs |= {"bu"}
            opts.append(sorted(rs, key=len, reverse=True))
        given = flat(py_given)
        from functools import lru_cache
        @lru_cache(maxsize=None)
        def m(i, pos):
            if i == len(opts):
                return pos == len(given)
            return any(given.startswith(r, pos) and m(i + 1, pos + len(r)) for r in opts[i])
        return m(0, 0) or any(m(0, p) for p in range(1, len(given)))

    for i, ch in enumerate(book["chapters"]):
        name = tc(f"Story {ch['num']}: {ch['title']}" if ch["kind"] == "story" else ch["title"])
        for chap, z, p, ctx, target in scan(ch.get("blocks", []), name, ["chapters", i]):
            pairs_checked += 1
            if not check(z, p):
                add("pinyin", "teacher", chap, z,
                    f"Prononciation notée « {p} »",
                    {"zh": z, "pinyin": p, "context": ctx,
                     "expected": " ".join(x[0] for x in pinyin(re.sub(r"[^\u4e00-\u9fff]", "", z),
                                                               style=Style.TONE))},
                    target=target)

# 2. exercices (file de l'éditeur)
ex_target = {}          # (leçon, « titre (#n) ») → adresse du bloc exercice
for i, ch in enumerate(book["chapters"]):
    if ch["kind"] not in ("chapter", "story"):
        continue
    name = tc(f"Story {ch['num']}: {ch['title']}" if ch["kind"] == "story" else ch["title"])
    for j, ex in enumerate(ch["blocks"]):
        if ex["type"] != "exercise":
            continue
        label = f"{ex['title']} (#{ex['num']})"
        ex_target[(name, label)] = {"path": ["chapters", i, "blocks", j],
                                    "field": None, "occurrence": 0}
        kind = ex.get("ex_type")
        d = ex.get("data") or {}
        answers = [plain(a["text"]) for a in (ex.get("answers") or [])]
        n_items = len(d.get("items", d.get("col_a", [])))
        if kind == "open_ended" or not answers:
            continue
        if n_items and len(answers) != n_items:
            add("exercise", "editor", name, label,
                f"{len(answers)} réponses pour {n_items} questions détectées",
                {"ex_type": kind, "answers": answers,
                 "items": [plain(x.get("prompt") or x.get("statement") or x.get("text", ""))
                           for x in d.get("items", [])][:8]},
                target=ex_target[(name, label)])

# 2bis. avertissements du contrôle des exercices (file de l'éditeur)
if os.path.exists("output/exercise_issues.json"):
    seen = {(i["lesson"], i["title"]) for i in items if i["kind"] == "exercise"}
    for iss in json.load(open("output/exercise_issues.json")):
        key = (tc(iss["lesson"]), iss["ex"])
        if key in seen:
            continue
        seen.add(key)
        add("exercise", "editor", tc(iss["lesson"]), iss["ex"], iss["msg"],
            {"severity": iss["sev"]}, target=ex_target.get(key))

# 3. answer keys (file du manager)
if os.path.exists("answerkey_diff.txt"):
    txt = open("answerkey_diff.txt").read()
    for m in re.finditer(r"leçon\s+: (.+?)\n\s+answer key : (.+?)(?:\n|$)", txt):
        real, pub = m.group(1).strip(), m.group(2).replace("← formulation différente", "").strip()
        add("answerkey", "manager", tc(real), tc(real),
            f"L'answer key du manuscrit indique « {pub} »", {"published": pub})
    sec = txt.split("SANS LEÇON CORRESPONDANTE")
    if len(sec) > 1:
        for line in sec[1].strip().splitlines():
            line = line.strip()
            if line and not line.startswith("="):
                add("answerkey", "manager", "", line,
                    "Bloc de réponses sans leçon correspondante dans le manuscrit",
                    {"published": line})

# ---------------------------------------------------------------- sortie
queues = Counter(i["queue"] for i in items)
bundle = {
    "project": os.environ.get("WB_PROJECT") or tc(book.get("meta", {}).get("book_title", "Workbook")),
    "source": os.path.basename(os.environ.get("WB_SOURCE", "manuscrit.docx")),
    "id_scheme": ID_SCHEME,
    "stats": {
        "lessons": len(lessons),
        "blocks": sum(len(c.get("blocks", [])) for c in book["chapters"]),
        "exercises": sum(1 for c in book["chapters"] for b in c.get("blocks", [])
                         if b["type"] == "exercise"),
        "pairs_checked": pairs_checked,
    },
    "queues": dict(queues),
    "lessons": lessons,
    "items": items,
}
os.makedirs("output", exist_ok=True)
json.dump(bundle, open(OUT, "w"), ensure_ascii=False, indent=1)
print(f"bundle : {len(items)} items à relire  {dict(queues)}  → {OUT}")
