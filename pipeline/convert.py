#!/usr/bin/env python3
"""CN10 pipeline — étape 1 : docx → book.json (source de vérité structurée)."""
import json, re, sys
import langue
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

import os
SRC = os.environ.get("WB_SOURCE", "/mnt/user-data/uploads/742_CN10_FINAL_Manuscript.docx")
OUT = "content/book.json"

CJK = r"\u3000-\u303f\u4e00-\u9fff\uff00-\uffef"
RE_ZH = re.compile(rf"([{CJK}]+)")
RE_PY = re.compile(r"\[([^\[\]]{1,120}?)\]")
# ligne de dialogue : ZH…[pinyin] (+ éventuel "(english)" après retour/tab)
RE_DIA = re.compile(rf"^\s*(?:([A-Za-z]{{1,12}}|[\u4e00-\u9fff]{{1,4}})\s*[：:]\s*)?([{CJK}][^\[\]]*)\[([^\[\]]+)\]\s*(?:[\n\t\s]*\((.+?)\))?\s*$", re.S)
SPEAKER_STOP = {"example", "note", "tip", "answer", "hint", "pattern", "bonus"}
RE_SECTION = re.compile(r"^SECTION\s+(\d+)\s*:\s*(.+)$", re.I)
RE_STORY = re.compile(r"^STORY\s+(\d+)\s*:\s*(.+)$", re.I)

NSW = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

def list_info(p):
    """Niveau de liste Word (invisible dans le texte mais porteur de la numérotation)."""
    pPr = p._p.find(NSW + "pPr")
    if pPr is None:
        return None
    numPr = pPr.find(NSW + "numPr")
    if numPr is None:
        return None
    ilvl = numPr.find(NSW + "ilvl")
    numId = numPr.find(NSW + "numId")
    return {"ilvl": int(ilvl.get(NSW + "val")) if ilvl is not None else 0,
            "numId": numId.get(NSW + "val") if numId is not None else None}

def max_size(p):
    sizes = [r.font.size.pt for r in p.runs if r.font.size]
    return max(sizes) if sizes else None

def fully_bold(p):
    runs = [r for r in p.runs if r.text.strip()]
    return bool(runs) and all(r.bold for r in runs)

def run_text(p):
    """Texte avec marqueurs **gras** / *italique* (hors zh déjà stylé)."""
    out = []
    for r in p.runs:
        t = r.text
        if not t:
            continue
        if r.bold and t.strip():
            t = f"**{t}**"
        elif r.italic and t.strip():
            t = f"*{t}*"
        out.append(t)
    return "".join(out) if out else p.text

def mark_inline(s):
    """Wrappe zh et [pinyin] en marqueurs {zh:} / {py:}."""
    s = RE_ZH.sub(lambda m: "{zh:%s}" % m.group(1), s)
    def py_repl(m):
        inner = m.group(1)
        if re.search(r"[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü]", inner) or re.fullmatch(r"[A-Za-z\u0100-\u024F\s'!?.,;:\-–—]+", inner):
            return "{py:%s}" % inner
        return m.group(0)
    return RE_PY.sub(py_repl, s)

def table_to_block(tb):
    ncols = len(tb.columns)
    rows = []
    for r in tb.rows:
        cells = []
        seen = set()
        for c in r.cells:
            if id(c._tc) in seen:  # cellules fusionnées
                continue
            seen.add(id(c._tc))
            cells.append(mark_inline(c.text.strip().replace("\n", "{br}").replace("\t", " ")))
        rows.append(cells)
    return {"type": "table", "ncols": ncols, "rows": rows}

def main():
    d = Document(SRC)
    body = []
    for ch in d.element.body.iterchildren():
        if ch.tag.endswith("}p"):
            body.append(Paragraph(ch, d))
        elif ch.tag.endswith("}tbl"):
            body.append(Table(ch, d))

    chapters = []   # {kind, num, title, blocks}
    cur = None      # chapitre courant
    ex = None       # exercice ouvert (liste de blocs)
    section_count = 0
    chap_count = 0
    ex_count = 0
    stats = {"paras": 0, "dialogue_lines": 0, "tables": 0, "exercises": 0, "unclassified": 0}

    def close_ex():
        nonlocal ex
        ex = None

    def push(block):
        (ex["blocks"] if ex is not None else cur["blocks"]).append(block)

    def new_chapter(kind, title, num=None, section=None):
        nonlocal cur, ex_count
        close_ex()
        cur = {"kind": kind, "title": title, "num": num, "section": section, "blocks": []}
        chapters.append(cur)
        ex_count = 0

    skip_toc = False
    for el in body:
        if isinstance(el, Table):
            if cur is None:
                continue
            stats["tables"] += 1
            push(table_to_block(el))
            continue
        text = el.text.strip()
        style = el.style.name
        if not text:
            continue
        if style == "Title":
            continue  # titre du livre — géré par la couverture
        # TOC du manuscrit : on la supprime (la nôtre est générée)
        if text.upper().startswith("TABLE OF CONTENTS"):
            skip_toc = True
            continue
        is_big_section = RE_SECTION.match(text) and (style == "Heading 1" or (max_size(el) or 0) >= 18)
        if skip_toc:
            if style == "Heading 1" or is_big_section:
                skip_toc = False
            else:
                continue
        # sections en style normal 20pt (manuscrit inconsistant)
        if is_big_section and style != "Heading 1":
            m = RE_SECTION.match(text)
            section_count = int(m.group(1))
            close_ex()
            chapters.append({"kind": "section", "num": section_count, "title": m.group(2).strip(), "blocks": []})
            cur = None
            continue
        if style == "Heading 1":
            m = RE_SECTION.match(text)
            if m:
                section_count = int(m.group(1))
                close_ex()
                chapters.append({"kind": "section", "num": section_count, "title": m.group(2).strip(), "blocks": []})
                cur = None
                continue
            m = RE_STORY.match(text)
            if m:
                new_chapter("story", m.group(2).strip(), num=int(m.group(1)), section=section_count)
                continue
            up = text.upper()
            if up.startswith("INTRODUCTION"):
                new_chapter("intro", "Introduction"); continue
            if up.startswith("CONCLUSION"):
                new_chapter("conclusion", "Conclusion"); continue
            if up.startswith("ANSWER KEY"):
                new_chapter("answers", "Answer Keys"); continue
            chap_count += 1
            new_chapter("chapter", text, num=chap_count, section=section_count)
            continue
        if cur is None:
            stats["unclassified"] += 1
            continue
        if style == "Heading 2":
            close_ex()
            push({"type": "h2", "text": mark_inline(run_text(el))}); continue
        if style == "Heading 3":
            close_ex()
            push({"type": "h3", "text": mark_inline(run_text(el))}); continue
        if style == "Heading 4":
            ex_count += 1
            stats["exercises"] += 1
            ex_block = {"type": "exercise", "num": ex_count, "title": text, "blocks": []}
            close_ex()
            cur["blocks"].append(ex_block)
            ex = ex_block
            continue
        # paragraphe normal — dialogue ?
        m = RE_DIA.match(el.text.strip())
        if m:
            stats["dialogue_lines"] += 1
            speaker = (m.group(1) or "").strip()
            if speaker.lower() in SPEAKER_STOP:
                speaker = ""
            zh_full = m.group(2).strip()
            if not speaker:
                ms = re.match(r"^([^：:\[\]\s]{1,6})\s*[：:]\s*(.+)$", zh_full, re.S)
                if ms and not ms.group(1).endswith(("说", "问", "答", "喊")):
                    speaker, zh_full = ms.group(1), ms.group(2).strip()
            push({"type": "dia_line", "speaker": speaker, "zh": zh_full,
                  "pinyin": m.group(3).strip(), "en": (m.group(4) or "").strip()})
            continue
        if fully_bold(el) and len(text) < 60 and not text.endswith(":") and "{zh:" not in mark_inline(text):
            push({"type": "minihead", "text": mark_inline(text)})
            continue
        stats["paras"] += 1
        blk = {"type": "para", "text": mark_inline(run_text(el))}
        li = list_info(el)
        if li:
            blk["list"] = li
        push(blk)

    # 1) fusionner les paras "(traduction)" dans la dia_line qui précède
    RE_EN = re.compile(r"^\(([^()]{1,200})\)$")
    def merge_en(blocks):
        out = []
        for b in blocks:
            if b["type"] == "exercise":
                b["blocks"] = merge_en(b["blocks"])
                out.append(b); continue
            if (b["type"] == "para" and out and out[-1]["type"] == "dia_line"
                    and not out[-1]["en"]):
                m = RE_EN.match(re.sub(r"\*+", "", b["text"]).strip())
                if m and "{zh:" not in b["text"]:
                    out[-1]["en"] = m.group(1)
                    continue
            out.append(b)
        return out
    for ch in chapters:
        ch["blocks"] = merge_en(ch["blocks"])

    # 2) regrouper stage + dia_line consécutifs en blocs dialogue
    for ch in chapters:
        def group(blocks):
            out, i = [], 0
            while i < len(blocks):
                b = blocks[i]
                if b["type"] == "exercise":
                    # dans un exercice, les lignes chinoises sont des énoncés ou des
                    # options : on ne les fusionne pas en panneau de dialogue
                    out.append(b); i += 1; continue
                is_stage = (b["type"] == "para" and b["text"].rstrip().endswith(":")
                            and i + 1 < len(blocks) and blocks[i + 1]["type"] == "dia_line"
                            and len(b["text"]) < 120)
                if b["type"] == "dia_line" or is_stage:
                    items = []
                    while i < len(blocks):
                        b2 = blocks[i]
                        if b2["type"] == "dia_line":
                            items.append({"kind": "line", **{k: b2.get(k, "") for k in ("speaker", "zh", "pinyin", "en")}})
                            i += 1
                        elif (b2["type"] == "para" and b2["text"].rstrip().endswith(":")
                              and i + 1 < len(blocks) and blocks[i + 1]["type"] == "dia_line"
                              and len(b2["text"]) < 120):
                            items.append({"kind": "stage", "text": b2["text"]})
                            i += 1
                        else:
                            break
                    nlines = sum(1 for x in items if x["kind"] == "line")
                    if nlines >= 2:
                        out.append({"type": "dialogue", "items": items})
                    else:
                        for x in items:
                            if x["kind"] == "stage":
                                out.append({"type": "para", "text": x["text"]})
                            else:
                                out.append({"type": "dia_line", **{k: x.get(k, "") for k in ("speaker", "zh", "pinyin", "en")}})
                else:
                    out.append(b); i += 1
            return out
        ch["blocks"] = group(ch["blocks"])

    book = {
        # Le titre vient de la config de langue : écrit en dur, il a mis
        # « LEARN CHINESE » sur la couverture d'un livre de japonais.
        "meta": langue.titres_du_livre(),
        "chapters": chapters,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(book, f, ensure_ascii=False, indent=1)
    n_sections = sum(1 for c in chapters if c["kind"] == "section")
    print(f"chapitres: {len(chapters)} (dont {n_sections} sections, {chap_count} leçons)")
    print("stats:", stats)

if __name__ == "__main__":
    main()
