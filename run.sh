#!/usr/bin/env bash
# Workbook Engine — chaîne complète : docx → PDF + rapports
#
# Les lignes « n/7 » sont relayées telles quelles sur la page de suivi, que
# lisent des relecteurs qui ne parlent pas français : elles sont en anglais.
set -e
SRC="${1:?usage: ./run.sh <manuscrit.docx>}"
export WB_SOURCE="$SRC"

echo "1/7  reading the manuscript"
python3 pipeline/convert.py

echo "2/7  replaying reviewer decisions"
python3 pipeline/decisions.py

echo "3/7  typing exercises and linking answers"
python3 pipeline/exercises.py

echo "4/7  checking pronunciations"
python3 pipeline/validate.py

echo "5/7  checking exercises and answer keys"
python3 pipeline/check_exercises.py
python3 pipeline/answerkeys.py

echo "6/7  typesetting the book"
typst compile --font-path fonts --root . templates/book.typ output/book.pdf
echo "→ output/book.pdf"

echo "7/7  building the review queues"
python3 pipeline/bundle.py
python3 - << 'PY'
import pathlib
tpl = pathlib.Path('webapp/console.html').read_text()
data = pathlib.Path('output/review.json').read_text().replace('</script>', '<\\/script>')
pathlib.Path('output/console.html').write_text(tpl.replace('__BUNDLE__', data))
PY
echo "→ output/console.html"
