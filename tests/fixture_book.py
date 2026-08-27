#!/usr/bin/env python3
"""Manuscrit d'essai partagé par les tests."""

# ---------------------------------------------------------------- manuscrit d'essai
# Huit paires écriture ↔ prononciation, dont trois fautives, et un doublon exact
# de l'une d'elles dans un exercice — pour couvrir tous les types de blocs que
# scan() traverse : paragraphe, dialogue, tableau, ligne isolée, exercice imbriqué.
FAUTIF = "Wrong: {zh:你的老师呢？} {py:Nǐ ne?} here."

BOOK = {
    "meta": {"book_title": "LEARN CHINESE"},
    "chapters": [
        {"kind": "section", "num": 1, "title": "GETTING STARTED", "blocks": []},
        {"kind": "chapter", "num": 1, "title": "GREETINGS", "blocks": [
            {"type": "para", "text": "Say {zh:你好} {py:nǐ hǎo} to greet."},
            {"type": "para", "text": FAUTIF},
            {"type": "dialogue", "items": [
                {"kind": "line", "speaker": "A", "zh": "谢谢", "pinyin": "xièxie", "en": "Thanks"},
                {"kind": "stage", "text": "(they smile)"},
                {"kind": "line", "speaker": "B", "zh": "不客气", "pinyin": "bú kèqi", "en": "You're welcome"},
            ]},
            {"type": "table", "ncols": 2, "rows": [
                ["{zh:老师} {py:lǎoshī}", "teacher"],
                ["{zh:学生} {py:xuésheng}", "student"],
            ]},
            {"type": "exercise", "num": 1, "title": "Practice", "ex_type": "translation",
             "blocks": [
                 {"type": "para", "text": FAUTIF},
                 {"type": "dia_line", "speaker": "A", "zh": "再见", "pinyin": "zai", "en": "Bye"},
             ]},
            {"type": "exercise", "num": 2, "title": "Translate", "ex_type": "translation",
             "blocks": [],
             "data": {"items": [{"prompt": "one"}, {"prompt": "two"}]},
             "answers": [{"text": "un"}]},
        ]},
        {"kind": "story", "num": 1, "title": "A DAY OUT", "blocks": []},
    ],
}

PAIRES_ATTENDUES = 8
