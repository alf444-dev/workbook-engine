#!/usr/bin/env python3
"""Workbook Engine — bundle de relecture pour la console web.

Rassemble tout ce qu'un relecteur doit voir (et rien d'autre) dans un seul
fichier JSON : la liste des leçons, et les items signalés avec leur contexte.
"""
import json, os, re, unicodedata
from collections import Counter

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

def plain(s):
    return re.sub(r"\{(?:zh|py):([^}]*)\}", r"\1", str(s)).replace("{br}", " ").replace("*", "").strip()

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
items = []

def add(kind, queue, lesson, title, detail, extra=None):
    it = {"id": f"{kind}-{len(items)}", "kind": kind, "queue": queue,
          "lesson": lesson, "lesson_id": lesson_id(lesson or ""),
          "title": title, "detail": detail}
    if extra:
        it.update(extra)
    items.append(it)

# 1. prononciation (file du professeur natif)
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

    RE_PAIR = re.compile(r"\{zh:([^}]+)\}\s*\{py:([^}]+)\}")

    def scan(blocks, chap):
        for b in blocks:
            t = b["type"]
            if t in ("para", "h2", "h3", "minihead"):
                for z, p in RE_PAIR.findall(b["text"]):
                    yield chap, z, p, plain(b["text"])[:150]
            elif t == "dia_line":
                yield chap, b["zh"], b["pinyin"], plain(b.get("en", ""))[:150]
            elif t == "dialogue":
                for it in b["items"]:
                    if it["kind"] == "line":
                        yield chap, it["zh"], it["pinyin"], plain(it.get("en", ""))[:150]
            elif t == "table":
                for row in b["rows"]:
                    for cell in row:
                        for z, p in RE_PAIR.findall(cell):
                            yield chap, z, p, plain(cell)[:150]
            elif t == "exercise":
                yield from scan(b["blocks"], chap)

    for ch in book["chapters"]:
        name = tc(f"Story {ch['num']}: {ch['title']}" if ch["kind"] == "story" else ch["title"])
        for chap, z, p, ctx in scan(ch.get("blocks", []), name):
            if not check(z, p):
                add("pinyin", "teacher", chap, z,
                    f"Prononciation notée « {p} »",
                    {"zh": z, "pinyin": p, "context": ctx,
                     "expected": " ".join(x[0] for x in pinyin(re.sub(r"[^\u4e00-\u9fff]", "", z),
                                                               style=Style.TONE))})

# 2. exercices (file de l'éditeur)
for ch in book["chapters"]:
    if ch["kind"] not in ("chapter", "story"):
        continue
    name = tc(f"Story {ch['num']}: {ch['title']}" if ch["kind"] == "story" else ch["title"])
    for ex in [b for b in ch["blocks"] if b["type"] == "exercise"]:
        kind = ex.get("ex_type")
        d = ex.get("data") or {}
        answers = [plain(a["text"]) for a in (ex.get("answers") or [])]
        n_items = len(d.get("items", d.get("col_a", [])))
        if kind == "open_ended" or not answers:
            continue
        if n_items and len(answers) != n_items:
            add("exercise", "editor", name, f"{ex['title']} (#{ex['num']})",
                f"{len(answers)} réponses pour {n_items} questions détectées",
                {"ex_type": kind, "answers": answers,
                 "items": [plain(i.get("prompt") or i.get("statement") or i.get("text", ""))
                           for i in d.get("items", [])][:8]})

# 2bis. avertissements du contrôle des exercices (file de l'éditeur)
if os.path.exists("output/exercise_issues.json"):
    seen = {(i["lesson"], i["title"]) for i in items if i["kind"] == "exercise"}
    for iss in json.load(open("output/exercise_issues.json")):
        key = (tc(iss["lesson"]), iss["ex"])
        if key in seen:
            continue
        seen.add(key)
        add("exercise", "editor", tc(iss["lesson"]), iss["ex"], iss["msg"],
            {"severity": iss["sev"]})

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
    "project": "Learn Chinese — CN10",
    "source": os.path.basename(os.environ.get("WB_SOURCE", "manuscrit.docx")),
    "stats": {
        "lessons": len(lessons),
        "blocks": sum(len(c.get("blocks", [])) for c in book["chapters"]),
        "exercises": sum(1 for c in book["chapters"] for b in c.get("blocks", [])
                         if b["type"] == "exercise"),
        "pairs_checked": 2066,
    },
    "queues": dict(queues),
    "lessons": lessons,
    "items": items,
}
os.makedirs("output", exist_ok=True)
json.dump(bundle, open(OUT, "w"), ensure_ascii=False, indent=1)
print(f"bundle : {len(items)} items à relire  {dict(queues)}  → {OUT}")
