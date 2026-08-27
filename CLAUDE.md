# CLAUDE.md — mémoire du projet

Contexte permanent pour toute session de travail sur ce dépôt. À lire en entier
avant de modifier quoi que ce soit.

## Ce qu'on construit

Une chaîne de production de workbooks de langues pour un éditeur (Arno, Speak
Abroad Academy) qui publie des livres type « Learn Chinese for Adult Beginners »
(~240 pages, vendus sur KDP).

Aujourd'hui un livre lui prend ~6 mois : ses éditeurs génèrent les leçons avec
ChatGPT une par une, réécrivent presque tout (sortie jugée « 50 % exploitable,
très répétitive »), un professeur natif relit le manuscrit entier, puis quelqu'un
remonte tout à la main sous InDesign.

L'outil vise trois couches :

1. **Spécificités de la langue** — une config par langue qui pilote le reste
   (système d'écriture, progression HSK/JLPT/TOPIK/CEFR, types d'exercices
   activés, champs de contenu).
2. **Génération** — leçon par leçon (grouper dégrade la qualité), mais pilotée
   par script et contrainte par un plan, un glossaire maître et des exemples de
   style tirés des livres déjà validés.
3. **Formatting** — appliqué par un template, jamais généré. ✅ **fait**

Plus une **boucle humaine** : personne ne relit le livre en entier, chacun reçoit
une file d'items à trancher.

## Équipe cliente (dimensionne les choix produit)

- Arno : dirigeant, suit l'avancement.
- 1 team manager : supervise, organise les fichiers, valide.
- 4 éditeurs : 2 par projet, 2 projets en parallèle.
- Professeurs natifs externes, **différents à chaque langue** → toute interface
  qui leur est destinée doit être utilisable sans compte et sans formation.

Fichiers actuellement sur Google Drive, un dossier par projet
(`manuscrit/`, `graphique/`). On ne remplace pas le Drive : on s'y ajoute.

## État actuel

| Composant | État |
|---|---|
| `pipeline/convert.py` — docx → structure | ✅ 1 seul bloc non classé sur 2 516 |
| `pipeline/exercises.py` — typage + réponses | ✅ 82/82 typés, 8 types |
| `pipeline/validate.py` — pinyin | ✅ 2 066 paires, 15 signalées (0,7 %) |
| `pipeline/check_exercises.py` | ✅ 0 erreur, 24 avertissements |
| `pipeline/answerkeys.py` — corrigé dérivé | ✅ 3 divergences réelles trouvées |
| `templates/book.typ` — rendu | ✅ 226 p., TOC auto, prêt KDP |
| `pipeline/bundle.py` + `webapp/console.html` | ✅ console de relecture statique |
| Upload de documents depuis le site | ❌ **prochaine tâche** |
| Couche génération | ❌ |
| Config multi-langues | ❌ |

Livre de référence : `input/742_CN10_FINAL_Manuscript.docx` (à déposer, non
versionné). Lancer : `./run.sh input/742_CN10_FINAL_Manuscript.docx`.

## Invariants — ne pas les casser

1. **Le formatting n'est jamais généré par un modèle.** Il est appliqué par
   `templates/book.typ` à partir de données structurées. C'est ce qui rend les
   erreurs de mise en page impossibles par construction.
2. **Le corrigé est dérivé des exercices**, jamais recopié. Chaque exercice porte
   ses réponses. C'est ce qui a supprimé une classe d'erreurs qui survivait à la
   relecture humaine dans le livre publié.
3. **Le code passe avant les agents.** Tout ce qui est vérifiable de façon
   déterministe (prononciation, quotas, bijections, banque de mots) ne doit pas
   être confié à un modèle.
4. **Un outil de contrôle qui crie au loup perd sa crédibilité.** Avant d'ajouter
   une règle, vérifier son taux de faux positifs sur le CN10 en entier.
5. **Le professeur natif reste l'autorité finale sur la langue cible.** Les
   contrôles automatiques trient et réduisent le volume, ils ne valident pas.
6. **`content/book.json` est la source de vérité.** Les corrections humaines s'y
   appliquent, jamais sur le PDF ni sur le docx.

## Pièges déjà rencontrés (ne pas les redécouvrir)

- **La numérotation des exercices est portée par Word (`numPr`), invisible dans
  `paragraph.text`.** Sans elle, les QCM perdent leurs questions. Extraite dans
  `convert.py::list_info`, exposée en `block["list"]["ilvl"]`.
- **Le manuscrit est irrégulier** : 8 sections sur 10 ne sont pas en style
  Heading mais en `normal` 20 pt ; il contient sa propre table des matières à
  ignorer ; 163 mini-titres sont de simples paragraphes en gras.
- **Ne jamais regrouper les lignes chinoises en panneau de dialogue à
  l'intérieur d'un exercice** : ce sont des énoncés ou des options. Ce
  regroupement avait avalé un QCM entier.
- **Les options de QCM ont trois formes** : inline (`A. x  B. y`), une par
  paragraphe (liste Word niveau 1), ou en chinois (lignes de dialogue). Le
  parseur classe en deux passes, la seconde résolvant les lignes chinoises selon
  leur voisin.
- **Vérification du pinyin** : comparer les syllabes sans les tons, avec
  backtracking sur les hétéronymes, tolérance erhua (儿), 一, 不, exclusion des
  tokens latins (noms propres, « Wi-Fi », « QR ») et des chiffres arabes.
  Sans ces règles, 16 % de faux positifs ; avec, 0,7 %.
- **Faux positif du comparateur de corrigés** : les stories s'appellent
  `STORY n: TITRE` dans le corrigé et `TITRE` dans la structure. Comparer sur le
  titre d'affichage.
- **Typst** : les fonctions doivent être définies avant usage ; `render-exercise`
  reçoit `render-blocks` en paramètre de repli. La page blanche finale se calcule
  via un `<book-end>` ancré, sinon le compteur ne converge pas.

## Conventions

- Python 3, sans framework, dépendances : `python-docx`, `pypinyin`.
- Rendu : binaire `typst`, polices dans `fonts/` (Archivo, Source Serif 4,
  Noto Sans SC — substituts libres ; Arno a peut-être les licences des originales).
- Chaque étape du pipeline lit et écrit des fichiers, aucun état en mémoire
  partagé : on peut relancer une étape seule.
- Les rapports destinés aux humains sont en français, le contenu des livres en
  anglais.
- Commits en français, une phrase à l'impératif.

## Design de la console

- Palette reprise du livre : pin `#1A5E52`, ambre `#E5A33C`, papier `#EEF2F0`.
- Typo de la console = typo du livre (Archivo + Source Serif 4), pour que le
  texte relu ait l'allure qu'il aura imprimé. Données en IBM Plex Mono.
- Élément signature : le rail de gauche, le livre vu par la tranche ; chaque
  trait est une leçon, ambre s'il reste des items, vert quand c'est traité.
- Navigation clavier obligatoire (`J`/`K`/`A`/`C`/`S`) : c'est ce qui rend une
  file rapide à vider.
