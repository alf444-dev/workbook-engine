#!/usr/bin/env python3
"""Parcours des paires écriture ↔ prononciation, et adressage dans book.json.

Partagé par `bundle.py` (qui construit les files de relecture) et par
`decisions.py` (qui applique les corrections). Deux copies de ce parcours
finiraient par diverger : une correction s'appliquerait alors ailleurs que là
où le relecteur l'a vue.

Une adresse est {"path": [...], "field": clé ou index, "occurrence": n} :
`path` mène à l'objet contenant, `field` au texte, `occurrence` à la paire
`{zh:…} {py:…}` visée à l'intérieur de ce texte.
"""
import re

# Le manuscrit met parfois la prononciation en gras : « {zh:你好} *{py:nǐ hǎo}* ».
# Un motif qui n'accepte que des espaces entre les deux balises laisse passer
# 743 paires du CN10 — 46 % — jamais vérifiées par le contrôle du pinyin.
# On tolère donc la ponctuation de mise en forme, et elle seule : accepter
# n'importe quoi rapprocherait des balises appartenant à deux paires voisines.
RE_PAIR = re.compile(r"\{zh:([^}]+)\}[\s*_]{0,6}\{py:([^}]+)\}")


def plain(s):
    return (re.sub(r"\{(?:zh|py):([^}]*)\}", r"\1", str(s))
            .replace("{br}", " ").replace("*", "").strip())


def scan(blocks, chap, base):
    """Rend (leçon, hanzi, pinyin, contexte, adresse) pour chaque paire.

    Les index de blocs de book_typed.json sont ceux de book.json :
    exercises.py enrichit les blocs sur place, sans en ajouter, en retirer ni
    les réordonner. Une adresse relevée sur l'un vaut donc sur l'autre.
    """
    for j, b in enumerate(blocks):
        t = b["type"]
        path = base + ["blocks", j]
        if t in ("para", "h2", "h3", "minihead"):
            for n, (z, p) in enumerate(RE_PAIR.findall(b["text"])):
                yield chap, z, p, plain(b["text"])[:150], \
                    {"path": path, "field": "text", "occurrence": n}
        elif t == "dia_line":
            yield chap, b["zh"], b["pinyin"], plain(b.get("en", ""))[:150], \
                {"path": path, "field": "pinyin", "occurrence": 0}
        elif t == "dialogue":
            for k, it in enumerate(b["items"]):
                if it["kind"] == "line":
                    yield chap, it["zh"], it["pinyin"], plain(it.get("en", ""))[:150], \
                        {"path": path + ["items", k], "field": "pinyin", "occurrence": 0}
        elif t == "table":
            for r, row in enumerate(b["rows"]):
                for c, cell in enumerate(row):
                    for n, (z, p) in enumerate(RE_PAIR.findall(cell)):
                        yield chap, z, p, plain(cell)[:150], \
                            {"path": path + ["rows", r], "field": c, "occurrence": n}
        elif t == "exercise":
            yield from scan(b["blocks"], chap, path)


def parcourir(book):
    """Toutes les paires du livre, avec leur adresse."""
    for i, ch in enumerate(book["chapters"]):
        nom = ch.get("title", "")
        yield from scan(ch.get("blocks", []), nom, ["chapters", i])


def conteneur(book, target):
    """Suit `path` jusqu'à l'objet qui porte le texte visé."""
    node = book
    for step in target["path"]:
        node = node[step]
    return node


def lire(book, target):
    """Rend la paire (hanzi, pinyin) présente à cette adresse, ou None."""
    try:
        node = conteneur(book, target)
        if target["field"] == "pinyin":
            return node["zh"], node["pinyin"]
        paires = RE_PAIR.findall(node[target["field"]])
        return paires[target["occurrence"]]
    except (KeyError, IndexError, TypeError):
        return None


def ecrire_pinyin(book, target, nouveau):
    """Remplace la prononciation à cette adresse. Rend True si c'est fait."""
    try:
        node = conteneur(book, target)
        if target["field"] == "pinyin":
            node["pinyin"] = nouveau
            return True
        texte = node[target["field"]]
        n = target["occurrence"]
        vu = -1

        def remplacer(m):
            nonlocal vu
            vu += 1
            return "{zh:%s} {py:%s}" % (m.group(1), nouveau) if vu == n else m.group(0)

        node[target["field"]] = RE_PAIR.sub(remplacer, texte)
        return vu >= n
    except (KeyError, IndexError, TypeError):
        return False
