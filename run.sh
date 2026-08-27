#!/usr/bin/env bash
# Workbook Engine — chaîne complète : docx → PDF + rapports
set -e
SRC="${1:?usage: ./run.sh <manuscrit.docx>}"
export WB_SOURCE="$SRC"

echo "1/5  docx → structure"
python3 pipeline/convert.py

echo "2/5  typage des exercices + liaison des réponses"
python3 pipeline/exercises.py

echo "3/5  validation linguistique"
python3 pipeline/validate.py

echo "4/5  contrôle des exercices et answer keys"
python3 pipeline/check_exercises.py
python3 pipeline/answerkeys.py

echo "5/5  compilation du livre"
typst compile --font-path fonts --root . templates/book.typ output/book.pdf
echo "→ output/book.pdf"
