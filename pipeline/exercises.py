#!/usr/bin/env python3
"""CN10 pipeline — étape 1bis : typage des exercices + liaison des réponses.

Transforme les exercices en prose libre du manuscrit en structures typées
portant leurs propres réponses, puis régénère l'answer key.
"""
import json, re, sys
from collections import Counter

IN = "content/book.json"
OUT = "content/book_typed.json"

# ---------------------------------------------------------------- helpers
def plain(s):
    """Retire les marqueurs pour l'analyse (garde le texte lisible)."""
    s = re.sub(r"\{(?:zh|py):([^}]*)\}", r"\1", s)
    return s.replace("{br}", " ").replace("*", "").strip()

def has_blank(s):
    return bool(re.search(r"_{2,}", s))

RE_OPT_INLINE = re.compile(r"(?:^|\s)([A-E])[.)]\s*")
RE_OPT_RAW = re.compile(r"(?:^|[\s*\t])([A-E])[.)][ \t*]*")
RE_LETTER_ITEM = re.compile(r"^\s*([A-E])[.)]\s*(.+)$", re.S)
RE_NUM_ITEM = re.compile(r"^\s*(\d{1,2})[.)]\s*(.+)$", re.S)

# ---------------------------------------------------------------- typage
TYPE_RULES = [
    ("matching",        r"match"),
    ("mcq",             r"multiple choice|choose the correct|correct word"),
    ("fill_blank",      r"fill in the blank|fill-in-the-blank|complete each|complete the"),
    ("true_false",      r"true or false|true/false"),
    ("translation",     r"translat"),
    ("sentence_building", r"sentence building|build the"),
    ("comprehension",   r"comprehension|understanding|what would you say|who are you|situational"),
]

RE_OPEN = re.compile(r"your own|introducing yourself|about you\b|try (writing|introducing)", re.I)

def guess_type(title, blocks):
    t = title.lower()
    joined = " ".join(plain(b.get("text", "")) for b in blocks if b["type"] == "para")
    if RE_OPEN.search(joined) or RE_OPEN.search(title):
        return "open_ended"
    for name, pat in TYPE_RULES:
        if re.search(pat, t):
            return name
    # secours : la forme parle
    text = " ".join(plain(b.get("text", "")) for b in blocks if b["type"] == "para").lower()
    for name, pat in TYPE_RULES:
        if re.search(pat, text):
            return name
    if any(b["type"] == "table" and b["ncols"] == 2 and
           "column" in plain(b["rows"][0][0]).lower() for b in blocks if b["type"] == "table"):
        return "matching"
    if any(has_blank(json.dumps(b, ensure_ascii=False)) for b in blocks):
        return "fill_blank"
    return "comprehension"

# ---------------------------------------------------------------- parsers
def split_cell_items(cell):
    """Cellule 'A. you {br} B. don't understand' → items.
    Une ligne sans étiquette qui suit un item étiqueté en est la continuation
    (typiquement le pinyin sous la phrase chinoise) et ne compte pas comme item."""
    parts = [p.strip() for p in cell.split("{br}") if p.strip()]
    out = []
    for p in parts:
        m = RE_LETTER_ITEM.match(plain(p)) or RE_NUM_ITEM.match(plain(p))
        if m:
            body = p[len(m.group(0)) - len(m.group(2)):].strip()
            out.append({"label": m.group(1), "text": body})
        elif out and out[-1]["label"] is not None:
            out[-1]["text"] += " " + p          # continuation
        else:
            out.append({"label": None, "text": p})
    return out

def parse_matching(ex):
    """Table 2 colonnes : en-têtes variables (Column A/B, Chinese/English…),
    items soit empilés dans une cellule ({br}), soit une ligne par item."""
    for b in ex["blocks"]:
        if b["type"] != "table" or b["ncols"] < 2 or not b["rows"]:
            continue
        rows = b["rows"]
        first = [plain(c).lower() for c in rows[0]]
        # en-tête = ligne courte sans contenu pédagogique
        is_head = (len(rows) > 1 and all(len(h) < 22 for h in first)
                   and not any(re.search(r"[\u4e00-\u9fff]", c) for c in rows[0]))
        head = rows[0] if is_head else None
        body = rows[1:] if is_head else rows
        col_a, col_b = [], []
        for row in body:
            if len(row) < 2:
                continue
            col_a += split_cell_items(row[0])
            col_b += split_cell_items(row[1])
        col_a = [it for it in col_a if it["text"].strip()]
        col_b = [it for it in col_b if it["text"].strip()]
        if len(col_a) >= 2 and len(col_b) >= 2:
            for i, it in enumerate(col_a):
                it["label"] = it["label"] or str(i + 1)
            for i, it in enumerate(col_b):
                it["label"] = it["label"] or ("ABCDEFGH"[i] if i < 8 else str(i))
            res = {"col_a": col_a, "col_b": col_b}
            if head:
                res["head"] = [plain(h) for h in head[:2]]
            return res
    return None

def parse_mcq(ex):
    """Énoncés + options, quelle que soit leur forme dans le manuscrit :
    options inline (A. x  B. y), une par paragraphe (liste Word niveau 1),
    ou en chinois (lignes de dialogue). Les énoncés peuvent eux aussi être
    des paragraphes numérotés ou des lignes chinoises."""
    # aplatir les blocs en unités élémentaires
    units = []
    for b in ex["blocks"]:
        if b["type"] == "para" and b["text"].strip():
            units.append({"raw": b["text"].strip(), "lvl": b.get("list", {}).get("ilvl"), "zh": False})
        elif b["type"] == "dia_line":
            units.append({"raw": b["zh"] + (" {py:%s}" % b["pinyin"] if b.get("pinyin") else ""),
                          "lvl": None, "zh": True})
        elif b["type"] == "dialogue":
            for it in b["items"]:
                if it["kind"] == "line":
                    units.append({"raw": it["zh"] + (" {py:%s}" % it["pinyin"] if it.get("pinyin") else ""),
                                  "lvl": None, "zh": True})

    # 1er passage : rôle évident
    for u in units:
        inline = list(RE_OPT_RAW.finditer(u["raw"]))
        if u["lvl"] == 1 or inline:
            u["role"], u["inline"] = "opt", inline
        elif u["zh"]:
            u["role"] = "?"
        elif u["lvl"] == 0 or plain(u["raw"]).endswith(":"):
            u["role"] = "prompt"
        else:
            u["role"] = "text"

    # 2e passage : lignes chinoises — énoncé si suivies d'options, sinon options
    for i, u in enumerate(units):
        if u["role"] != "?":
            continue
        nxt = next((v for v in units[i + 1:] if v["role"] != "text"), None)
        u["role"] = "prompt" if (nxt and nxt["role"] == "opt") else "opt"
        u["inline"] = []

    items, cur = [], None
    for u in units:
        if u["role"] == "prompt":
            cur = {"prompt": u["raw"], "options": []}
            items.append(cur)
        elif u["role"] == "opt" and cur is not None:
            if u.get("inline"):
                pos = [(m.start(), m.group(1), m.end()) for m in u["inline"]]
                if pos[0][0] > 0 and plain(u["raw"][:pos[0][0]]):
                    cur["options"].append({"label": None, "text": u["raw"][:pos[0][0]].strip(" \t*")})
                for j, (start, lab, end) in enumerate(pos):
                    stop = pos[j + 1][0] if j + 1 < len(pos) else len(u["raw"])
                    txt = u["raw"][end:stop].strip(" \t*")
                    if plain(txt):
                        cur["options"].append({"label": lab, "text": txt})
            else:
                cur["options"].append({"label": None, "text": u["raw"]})

    items = [it for it in items if len(it["options"]) >= 2]
    for it in items:
        for i, o in enumerate(it["options"]):
            o["label"] = o["label"] or ("ABCDE"[i] if i < 5 else str(i))
    return {"items": items} if items else None

def parse_fill_blank(ex):
    """Banque de mots (table 1 col) + phrases à trous."""
    bank, items = [], []
    for b in ex["blocks"]:
        if b["type"] == "table" and b["ncols"] == 1 and len(b["rows"]) == 1:
            cell = b["rows"][0][0]
            bank = [p.strip() for p in re.split(r"[,，]|\{br\}", cell) if p.strip()]
        elif b["type"] in ("para", "dia_line"):
            txt = b.get("text") or b.get("zh", "")
            if has_blank(txt) or has_blank(b.get("pinyin", "")):
                items.append({"prompt": txt if b["type"] == "para" else b.get("zh", ""),
                              "en": b.get("en", "")})
        elif b["type"] == "dialogue":
            for it in b["items"]:
                blob = json.dumps(it, ensure_ascii=False)
                if has_blank(blob):
                    items.append({"prompt": it.get("zh", it.get("text", "")), "en": it.get("en", "")})
    if items or bank:
        return {"bank": bank, "items": items}
    return None

def parse_true_false(ex):
    """Affirmations numérotées (Word ilvl=0) ; sinon paires (contexte, affirmation)."""
    numbered = [b["text"] for b in ex["blocks"]
                if b["type"] == "para" and b.get("list", {}).get("ilvl") == 0 and b["text"].strip()]
    if len(numbered) >= 2:
        return {"items": [{"statement": t} for t in numbered]}
    paras = [b["text"] for b in ex["blocks"] if b["type"] == "para" and b["text"].strip()]
    if len(paras) < 3:
        return None
    body = paras[1:]
    items = [{"context": body[i], "statement": body[i + 1]} for i in range(0, len(body) - 1, 2)]
    return {"items": items} if items else None

def parse_generic(ex):
    """Questions listées (comprehension, translation, sentence building)."""
    items = []
    for b in ex["blocks"]:
        if b["type"] != "para":
            continue
        txt = b["text"].strip()
        if not txt:
            continue
        if b.get("list", {}).get("ilvl") == 0 or RE_NUM_ITEM.match(plain(txt)):
            items.append({"prompt": re.sub(r"^\s*\d{1,2}[.)]\s*", "", txt)})
    return {"items": items} if items else None

def parse_open_ended(ex):
    items = [{"prompt": b["text"]} for b in ex["blocks"]
             if b["type"] == "para" and has_blank(b["text"])]
    return {"items": items} if items else None

PARSERS = {
    "open_ended": parse_open_ended,
    "matching": parse_matching,
    "mcq": parse_mcq,
    "fill_blank": parse_fill_blank,
    "true_false": parse_true_false,
}

# ---------------------------------------------------------------- answer keys
def norm_title(s):
    s = plain(s).upper()
    s = re.sub(r"[^A-Z0-9 ]", "", s)
    s = re.sub(r"\bEVERYDAY\b", "EVERY DAY", s)
    return re.sub(r"\s+", " ", s).strip()

def parse_answer_key(ans_chapter):
    """{titre de leçon normalisé: [ [réponses ex.1], [réponses ex.2], … ]}"""
    out, cur = {}, None
    for b in ans_chapter["blocks"]:
        if b["type"] in ("minihead", "h2", "h3"):
            t = norm_title(b["text"])
            if re.fullmatch(r"SECTION \d+", t):
                continue
            cur = t
            out.setdefault(cur, [])
        elif b["type"] == "table" and cur:
            for row in b["rows"]:
                answers = []
                for cell in row:
                    for piece in cell.split("{br}"):
                        piece = piece.strip()
                        if not piece:
                            continue
                        m = RE_NUM_ITEM.match(plain(piece))
                        answers.append({"n": int(m.group(1)) if m else None,
                                        "text": re.sub(r"^\s*\d{1,2}[.)]\s*", "", piece).strip()})
                if answers:
                    out[cur].append(answers)
    return out

# ---------------------------------------------------------------- main
def main():
    book = json.load(open(IN))
    ans_ch = next((c for c in book["chapters"] if c["kind"] == "answers"), None)
    keys = parse_answer_key(ans_ch) if ans_ch else {}

    types = Counter()
    parsed_ok = Counter()
    bound = 0
    unbound_lessons = []
    align_warn = []

    for ch in book["chapters"]:
        if ch["kind"] not in ("chapter", "story"):
            continue
        title_n = norm_title(ch["title"])
        lesson_keys = keys.get(title_n)
        if lesson_keys is None:
            # secours : correspondance partielle
            for k in keys:
                if k and (k in title_n or title_n in k or
                          len(set(k.split()) & set(title_n.split())) >= max(2, len(k.split()) - 2)):
                    lesson_keys = keys[k]
                    break
        if lesson_keys is None:
            unbound_lessons.append(ch["title"])
            lesson_keys = []
        exs = [b for b in ch["blocks"] if b["type"] == "exercise"]
        cursor = 0
        for ex in exs:
            kind = guess_type(ex["title"], ex["blocks"])
            ex["ex_type"] = kind
            types[kind] += 1
            parser = PARSERS.get(kind, parse_generic)
            data = parser(ex) or parse_generic(ex)
            if data:
                ex["data"] = data
                parsed_ok[kind] += 1
            if kind == "open_ended":
                continue                      # production libre : pas de corrigé
            if cursor < len(lesson_keys):
                ex["answers"] = lesson_keys[cursor]
                cursor += 1
                bound += 1
        graded = sum(1 for e in exs if e.get("ex_type") != "open_ended")
        if lesson_keys and graded != len(lesson_keys):
            align_warn.append((ch["title"], graded, len(lesson_keys)))

    json.dump(book, open(OUT, "w"), ensure_ascii=False, indent=1)
    total = sum(types.values())
    print(f"exercices typés : {total}")
    for k, n in types.most_common():
        print(f"  {k:18s} {n:3d}   structure extraite : {parsed_ok[k]}/{n}")
    print(f"\nréponses liées : {bound}/{total}")
    if align_warn:
        print(f"\nalignement answer key incertain ({len(align_warn)} leçons) :")
        for t, g, k in align_warn:
            print(f"   - {t[:46]:46s} {g} exercices notés / {k} blocs de réponses")
    if unbound_lessons:
        print(f"leçons sans answer key retrouvée ({len(unbound_lessons)}) :")
        for t in unbound_lessons:
            print("   -", t[:60])

if __name__ == "__main__":
    main()
