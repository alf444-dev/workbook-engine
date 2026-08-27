# Workbook Engine

Chaîne de production de workbooks de langues : d'un manuscrit `.docx` à un PDF
prêt pour l'impression, avec validation automatique du contenu.

## Utilisation

```bash
./run.sh chemin/vers/manuscrit.docx
```

Produit :

| Fichier | Contenu |
|---|---|
| `output/book.pdf` | le livre complet, mis en page |
| `validation_report.txt` | paires écriture ↔ prononciation suspectes |
| `exercise_report.txt` | incohérences exercices ↔ réponses |
| `answerkey_diff.txt` | écarts entre l'answer key écrite à la main et celle dérivée des exercices |

## Étapes

1. **`convert.py`** — lit le `.docx` (styles Word, numérotation de listes, tableaux)
   et produit `content/book.json`, la source de vérité structurée.
2. **`exercises.py`** — type chaque exercice (8 types), en extrait la structure
   (items, options, colonnes, banque de mots) et y rattache ses réponses.
3. **`validate.py`** — vérifie chaque paire hanzi ↔ pinyin avec `pypinyin`
   (hétéronymes et erhua gérés).
4. **`check_exercises.py`** — bijection des matching, réponse présente parmi les
   options, cohérence du nombre de réponses, banque de mots.
5. **`answerkeys.py`** — dérive l'answer key des exercices eux-mêmes et la
   compare à celle du manuscrit.
6. **`templates/book.typ`** — applique la charte : TOC automatique, footers par
   section, pages spéciales, 6×9 avec gutter.

## Types d'exercices

`matching` · `mcq` · `fill_blank` · `true_false` · `translation` ·
`sentence_building` · `comprehension` · `open_ended`

Ajouter un type = un parseur dans `exercises.py` + un bloc de rendu dans
`templates/book.typ`.

## Dépendances

```bash
pip install python-docx pypinyin
# + le binaire typst et les polices dans fonts/
```
