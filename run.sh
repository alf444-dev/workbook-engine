#!/usr/bin/env bash
# Workbook Engine — chaîne complète : docx → PDF + rapports
set -e
SRC="${1:?usage: ./run.sh <manuscrit.docx>}"
export WB_SOURCE="$SRC"

echo "1/7  docx → structure"
python3 pipeline/convert.py

echo "2/7  décisions des relecteurs"
python3 pipeline/decisions.py

echo "3/7  typage des exercices + liaison des réponses"
python3 pipeline/exercises.py

echo "4/7  validation linguistique"
python3 pipeline/validate.py

echo "5/7  contrôle des exercices et answer keys"
python3 pipeline/check_exercises.py
python3 pipeline/answerkeys.py

echo "6/7  compilation du livre"
typst compile --font-path fonts --root . templates/book.typ output/book.pdf
echo "→ output/book.pdf"

echo "7/7  console de relecture"
python3 pipeline/bundle.py
python3 - << 'PY'
import pathlib
tpl = pathlib.Path('webapp/console.html').read_text()
data = pathlib.Path('output/review.json').read_text().replace('</script>', '<\\/script>')
pathlib.Path('output/console.html').write_text(tpl.replace('__BUNDLE__', data))
PY
echo "→ output/console.html"
