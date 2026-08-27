#!/usr/bin/env python3
"""CN10 pipeline — validation des exercices et de leurs réponses.

Vérifie ce qu'un relecteur humain ne peut pas vérifier de façon fiable :
la correspondance exercice ↔ answer key, item par item.
"""
import json, re
from collections import Counter

book = json.load(open("content/book_typed.json"))

def plain(s):
    return re.sub(r"\{(?:zh|py):([^}]*)\}", r"\1", str(s)).replace("{br}", " ").replace("*", "").strip()

issues = []
checked = Counter()

def add(sev, lesson, ex, msg):
    issues.append({"sev": sev, "lesson": lesson, "ex": ex, "msg": msg})

for ch in book["chapters"]:
    if ch["kind"] not in ("chapter", "story"):
        continue
    for ex in [b for b in ch["blocks"] if b["type"] == "exercise"]:
        L, E = ch["title"], f"{ex['title']} (#{ex['num']})"
        kind = ex.get("ex_type")
        data = ex.get("data") or {}
        answers = ex.get("answers")

        if kind == "open_ended":
            checked["open_ended"] += 1
            continue
        if answers is None:
            add("ERR", L, E, "aucune réponse trouvée dans l'answer key")
            continue

        n_ans = len(answers)
        letters = [a["text"].strip().upper() for a in answers]

        if kind == "matching":
            a, b = data.get("col_a", []), data.get("col_b", [])
            checked["matching"] += 1
            if len(a) != len(b):
                add("ERR", L, E, f"colonnes déséquilibrées : {len(a)} items en A, {len(b)} en B")
            if n_ans != len(a):
                add("ERR", L, E, f"{n_ans} réponses pour {len(a)} items")
            # bijection : chaque lettre utilisée une seule fois
            used = [x for x in letters if re.fullmatch(r"[A-H]", x)]
            if used:
                dup = [k for k, v in Counter(used).items() if v > 1]
                if dup:
                    add("ERR", L, E, f"réponses en double (pas de bijection) : {', '.join(dup)}")
                valid = {it["label"] for it in b}
                unknown = [x for x in used if x not in valid]
                if unknown:
                    add("ERR", L, E, f"réponse hors colonne B : {', '.join(unknown)}")
                missing = sorted(valid - set(used))
                if len(used) == len(a) and missing:
                    add("WARN", L, E, f"items de la colonne B jamais utilisés : {', '.join(missing)}")

        elif kind == "mcq":
            items = data.get("items", [])
            checked["mcq"] += 1
            if items and n_ans != len(items):
                add("ERR", L, E, f"{n_ans} réponses pour {len(items)} questions")
            for i, it in enumerate(items):
                opts = it.get("options", [])
                labels = {o["label"] for o in opts}
                if len(opts) < 2:
                    add("WARN", L, E, f"question {i+1} : moins de 2 options détectées")
                if i < n_ans:
                    a = letters[i]
                    if labels and re.fullmatch(r"[A-E]", a) and a not in labels:
                        add("ERR", L, E, f"question {i+1} : réponse {a} absente des options {sorted(labels)}")

        elif kind == "fill_blank":
            items, bank = data.get("items", []), data.get("bank", [])
            checked["fill_blank"] += 1
            if items and n_ans != len(items):
                add("WARN", L, E, f"{n_ans} réponses pour {len(items)} trous détectés")
            if bank:
                bank_p = [plain(x) for x in bank]
                for i, a in enumerate(answers):
                    ap = plain(a["text"])
                    if ap and not any(ap in x or x in ap for x in bank_p):
                        add("WARN", L, E, f"réponse {i+1} « {ap[:24]} » absente de la banque de mots")

        elif kind == "true_false":
            items = data.get("items", [])
            checked["true_false"] += 1
            if items and n_ans != len(items):
                add("ERR", L, E, f"{n_ans} réponses pour {len(items)} affirmations")
            bad = [x for x in letters if x not in ("T", "F", "TRUE", "FALSE")]
            if bad:
                add("ERR", L, E, f"réponses non booléennes : {', '.join(bad[:4])}")

        else:
            items = data.get("items", [])
            checked[kind or "autre"] += 1
            if items and n_ans != len(items):
                add("WARN", L, E, f"{n_ans} réponses pour {len(items)} questions")

# ---- rapport
errs = [i for i in issues if i["sev"] == "ERR"]
warns = [i for i in issues if i["sev"] == "WARN"]
print(f"exercices contrôlés : {sum(checked.values())}  {dict(checked)}")
print(f"erreurs : {len(errs)}   avertissements : {len(warns)}")

with open("exercise_report.txt", "w") as f:
    f.write("CN10 — contrôle automatique des exercices et answer keys\n")
    f.write(f"{sum(checked.values())} exercices contrôlés — {len(errs)} erreurs, {len(warns)} avertissements\n\n")
    for sev, group in (("ERREURS", errs), ("AVERTISSEMENTS", warns)):
        f.write(f"\n{'='*60}\n{sev}\n{'='*60}\n")
        cur = None
        for i in group:
            if i["lesson"] != cur:
                cur = i["lesson"]
                f.write(f"\n{cur}\n")
            f.write(f"  [{i['ex']}] {i['msg']}\n")
import os
os.makedirs("output", exist_ok=True)
os.makedirs("output", exist_ok=True)
json.dump(issues, open("output/exercise_issues.json", "w"), ensure_ascii=False, indent=1)
print("→ exercise_report.txt + output/exercise_issues.json")
for i in errs[:8]:
    print(f"  ERR  {i['lesson'][:34]:34s} {i['msg'][:60]}")
