# Workbook Engine

Chaîne de production de workbooks de langues : d'un manuscrit `.docx` à un PDF
prêt pour l'impression, avec validation automatique du contenu.

## Démarrage

```bash
./setup.sh                                   # dépendances + polices
./run.sh input/742_CN10_FINAL_Manuscript.docx
open output/console.html                     # console de relecture
```

Le binaire `typst` doit être installé séparément
(https://github.com/typst/typst/releases).

## Serveur de relecture

```bash
pip install -r server/requirements.txt
python3 server/seed.py input/742_CN10_FINAL_Manuscript.docx --nom "Learn Chinese — CN10"
uvicorn app:app --app-dir server
```

Puis ouvrir le **lien de dépôt** imprimé au premier démarrage
(`/a/<jeton>`, ou `WB_ADMIN_TOKEN` fixé au déploiement) : on y glisse un `.docx`,
on suit les étapes, on récupère le livre, les rapports et les liens de relecture.
`seed.py` fait la même chose en ligne de commande.

Chaque projet est compilé dans son propre espace de travail (`data/projects/<id>/`)
par le `run.sh` inchangé. Chaque lien ouvre la console
sur **une seule file** ; les décisions sont enregistrées côté serveur, donc
plusieurs relecteurs peuvent vider la même file en même temps. Pas de comptes :
le lien fait l'autorisation, et le prénom demandé une fois sert à l'attribution.

## Tests

```bash
python3 tests/test_bundle_ids.py    # identifiants stables (manuscrit d'essai)
python3 tests/test_server.py        # cloisonnement des liens, journal des décisions
python3 tests/test_admin.py         # dépôt : ce qui est accepté, ce qui est refusé
python3 tests/test_decisions.py     # rejeu des corrections sur le livre
python3 tests/test_livraison.py     # dépôt Drive et sauvegarde
python3 tests/test_generation.py    # glossaire, style, conformité des leçons
python3 tests/test_langue.py        # une langue s'ajoute sans toucher au code
python3 tests/check_cn10_ids.py     # idem sur le CN10 réel, après ./run.sh
```

## Documentation

- `CLAUDE.md` — contexte, invariants et pièges du projet. **À lire en premier.**
- `docs/ROADMAP.md` — les trois couches et les phases de développement.
- `docs/NEXT_TASK.md` — la tâche en cours.
- `docs/DEPLOIEMENT.md` — mettre l'outil en ligne, Drive, sauvegarde.

Produit :

| Fichier | Contenu |
|---|---|
| `output/book.pdf` | le livre complet, mis en page |
| `validation_report.txt` | paires écriture ↔ prononciation suspectes |
| `exercise_report.txt` | incohérences exercices ↔ réponses |
| `answerkey_diff.txt` | écarts entre l'answer key écrite à la main et celle dérivée des exercices |
| `decisions_report.txt` | ce que les décisions des relecteurs ont changé dans le livre |
| `output/console.html` | console de relecture : trois files par rôle, autonome |

## Étapes

1. **`convert.py`** — lit le `.docx` (styles Word, numérotation de listes, tableaux)
   et produit `content/book.json`, la source de vérité structurée.
2. **`decisions.py`** — rejoue les décisions des relecteurs sur `content/book.json`.
   Sans `content/decisions.json`, l'étape ne fait rien. Les corrections sont une
   couche rejouée à chaque compilation, jamais une écriture définitive : le
   manuscrit reste la source, et un nouveau dépôt n'efface pas le travail des
   relecteurs.
3. **`exercises.py`** — type chaque exercice (8 types), en extrait la structure
   (items, options, colonnes, banque de mots) et y rattache ses réponses.
4. **`validate.py`** — vérifie chaque paire hanzi ↔ pinyin avec `pypinyin`
   (hétéronymes et erhua gérés).
5. **`check_exercises.py`** — bijection des matching, réponse présente parmi les
   options, cohérence du nombre de réponses, banque de mots.
6. **`answerkeys.py`** — dérive l'answer key des exercices eux-mêmes et la
   compare à celle du manuscrit.
7. **`bundle.py`** — assemble le bundle consommé par la console web.
8. **`templates/book.typ`** — applique la charte : TOC automatique, footers par
   section, pages spéciales, 6×9 avec gutter.

## Config de langue

```bash
python3 pipeline/lesson_profile.py    # mesure le livre → content/profile.json
python3 pipeline/check_config.py      # confronte config/chinese.json à la mesure
```

```bash
python3 pipeline/plan.py              # quotas par leçon → content/plan.json
python3 pipeline/check_plan.py        # le plan encadre-t-il le livre réel ?
python3 pipeline/propose_vocab.py     # progression d'une langue neuve, à faire valider
python3 pipeline/glossary.py          # glossaire maître → content/glossary.json
python3 pipeline/style.py             # voix maison → content/style.json
python3 pipeline/check_lesson.py      # conformité des leçons au plan
```

`config/chinese.json` décrit ce que sont réellement les livres validés : quotas
par leçon, exercices utilisés, courbe du vocabulaire. Chaque bloc porte sa
provenance — mesurée ou éditoriale — et les valeurs mesurées sont revérifiables.

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
