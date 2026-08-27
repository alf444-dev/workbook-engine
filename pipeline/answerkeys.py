#!/usr/bin/env python3
"""CN10 pipeline — answer key dérivée des exercices.

L'answer key n'est plus un chapitre écrit à la main : elle est construite à
partir des exercices eux-mêmes. Les titres, l'ordre et la numérotation ne
peuvent donc plus diverger. Le script produit aussi le diff avec la version
publiée, pour montrer ce que la méthode manuelle avait laissé passer.
"""
import json, re, difflib

book = json.load(open("content/book_typed.json"))

def plain(s):
    return re.sub(r"\{(?:zh|py):([^}]*)\}", r"\1", str(s)).replace("{br}", " ").replace("*", "").strip()

def norm(s):
    s = plain(s).upper()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", "", s)).strip()

# ---------- 1. answer key générée
generated = []           # [{section, lesson, exercises:[{title, type, answers}]}]
section = None
for ch in book["chapters"]:
    if ch["kind"] == "section":
        section = {"num": ch["num"], "title": ch["title"]}
        continue
    if ch["kind"] not in ("chapter", "story"):
        continue
    exs = []
    for ex in [b for b in ch["blocks"] if b["type"] == "exercise"]:
        if ex.get("ex_type") == "open_ended":
            continue
        exs.append({"num": ex["num"], "title": ex["title"], "type": ex.get("ex_type"),
                    "answers": [a["text"] for a in (ex.get("answers") or [])]})
    if exs:
        display = (f"STORY {ch['num']}: {ch['title']}" if ch["kind"] == "story" else ch["title"])
        generated.append({"section": section, "lesson": display,
                          "kind": ch["kind"], "exercises": exs})

json.dump(generated, open("content/answer_key.json", "w"), ensure_ascii=False, indent=1)

# ---------- 2. answer key publiée (telle qu'écrite dans le manuscrit)
ans_ch = next((c for c in book["chapters"] if c["kind"] == "answers"), None)
published = []
for b in (ans_ch["blocks"] if ans_ch else []):
    if b["type"] in ("minihead", "h2", "h3"):
        t = plain(b["text"])
        if not re.fullmatch(r"SECTION \d+", t.upper()):
            published.append(t)

lessons_real = [g["lesson"] for g in generated]
pub_norm = {norm(p): p for p in published}
real_norm = {norm(l): l for l in lessons_real}

lines = []
lines.append("CN10 — answer key : version publiée vs version générée\n")
lines.append(f"{len(lessons_real)} leçons avec exercices notés, "
             f"{sum(len(g['exercises']) for g in generated)} exercices corrigés\n")
lines.append(f"{len(published)} titres dans l'answer key publiée\n")

lines.append("\n" + "=" * 64 + "\nTITRES QUI DIVERGENT\n" + "=" * 64 + "\n")
drift = 0
for nreal, real in real_norm.items():
    if nreal in pub_norm:
        if plain(pub_norm[nreal]) != plain(real):
            drift += 1
            lines.append(f"\n  leçon    : {real}\n  answer key : {pub_norm[nreal]}\n")
        continue
    close = difflib.get_close_matches(nreal, list(pub_norm), n=1, cutoff=0.55)
    if close:
        drift += 1
        lines.append(f"\n  leçon    : {real}\n  answer key : {pub_norm[close[0]]}   ← formulation différente\n")
    else:
        drift += 1
        lines.append(f"\n  leçon    : {real}\n  answer key : ABSENTE\n")
if drift == 0:
    lines.append("\n  aucune\n")

extra = [p for n, p in pub_norm.items() if n not in real_norm
         and not difflib.get_close_matches(n, list(real_norm), n=1, cutoff=0.55)]
if extra:
    lines.append("\n" + "=" * 64 + "\nTITRES DE L'ANSWER KEY SANS LEÇON CORRESPONDANTE\n" + "=" * 64 + "\n")
    for e in extra:
        lines.append(f"  {e}\n")

open("answerkey_diff.txt", "w").writelines(lines)

print(f"answer key générée : {len(generated)} leçons, "
      f"{sum(len(g['exercises']) for g in generated)} exercices")
print(f"divergences avec la version publiée : {drift}")
print(f"titres publiés sans leçon correspondante : {len(extra)}")
print("→ answerkey_diff.txt")
