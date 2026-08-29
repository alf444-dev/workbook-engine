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
| `pipeline/validate.py` — pinyin | ✅ 2 780 paires, 20 signalées (0,7 %) |
| `pipeline/check_exercises.py` | ✅ 0 erreur, 24 avertissements |
| `pipeline/answerkeys.py` — corrigé dérivé | ✅ 3 divergences réelles trouvées |
| `templates/book.typ` — rendu | ✅ 226 p., TOC auto, prêt KDP |
| `pipeline/bundle.py` + `webapp/console.html` | ✅ console de relecture statique |
| Identifiants d'items stables + adresses `book.json` | ✅ `tests/test_bundle_ids.py`, `tests/check_cn10_ids.py` |
| `server/` — liens par rôle, décisions persistées | ✅ `tests/test_server.py` |
| Dépôt du manuscrit depuis le site | ✅ `tests/test_admin.py` |
| Rejeu des décisions + recompilation | ✅ `tests/test_decisions.py` |
| Dépôt Drive, sauvegarde quotidienne, image Docker | ✅ `tests/test_livraison.py` |
| Profil mesuré + config du chinois | ✅ `tests/test_profil.py`, `check_config.py` |
| Plan du livre | ✅ `tests/test_plan.py`, `check_plan.py` |
| Glossaire, voix maison, contrôle de leçon | ✅ `tests/test_generation.py` |
| Génération d'une leçon | ✅ première leçon générée et contrôlée |
| Réglage du prompt, livre complet | ❌ **prochaine étape** |
| Config multi-langues | ✅ `config/japanese.json` écrite sans toucher au code |
| Livre généré piloté depuis l'application | ✅ préparer, proposer, écrire, assembler |

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
- **Un id d'item dérivé de sa position est un piège silencieux.** `bundle.py`
  numérotait les items par rang de production (`pinyin-37`). Comme les décisions
  des relecteurs sont stockées sous cette clé, la recompilation suivante les
  faisait pointer vers d'autres items, sans aucune erreur visible. L'id est
  désormais un hachage du contenu : même id ⇒ même contenu, garanti. Un contenu
  modifié fait réapparaître l'item comme non traité — c'est le sens sûr.
  Figé par `tests/test_bundle_ids.py`.
- **Les index de blocs de `book_typed.json` sont ceux de `book.json`** :
  `exercises.py` enrichit les blocs sur place, sans en ajouter, retirer ni
  réordonner. C'est ce qui permet à l'adresse `target` d'un item de rester
  valable sur la source de vérité (invariant 6).
- **Appliquer les décisions *dans* `book.json` serait destructif** : `convert.py`
  le réécrit depuis le docx à chaque exécution. Les décisions doivent être une
  couche rejouée après conversion, jamais une édition en place.
- **`typst compile --root .` refuse un `templates/` en lien symbolique**
  (« source file must be contained in project root »). L'espace de travail par
  projet **copie** donc le code (100 Ko) et ne lie que `fonts/`, que
  `--font-path` accepte — sinon 18 Mo dupliqués par projet. Voir
  `server/workspace.py`.
- **Les scripts du pipeline ne créaient pas leurs dossiers de sortie.** Invisible
  tant qu'on travaillait dans le dépôt (où `content/` et `output/` existaient
  déjà), bloquant dès le premier espace de travail neuf.
- **Un attribut `hidden` ne masque pas un élément en `display:flex`** : il faut
  `.classe[hidden]{display:none}`. Le bandeau du relecteur s'affichait dans la
  console autonome.
- **`pipeline/pairs.py` est partagé** entre `bundle.py` (qui construit les files)
  et `decisions.py` (qui applique les corrections). Deux parcours séparés des
  paires finiraient par diverger : une correction s'appliquerait alors ailleurs
  que là où le relecteur l'a vue.
- **Les rapports du pipeline s'écrivent à la racine du dépôt** et `.gitignore`
  masque `*.txt`. Un `rm *.txt` de nettoyage emporte donc aussi
  `requirements.txt`, qui est suivi par git — ça s'est produit. Nettoyer avec
  `git clean -X` ou nommer les fichiers explicitement.
- **Le pinyin s'écrit en caractères latins.** Le compter comme de l'anglais
  double le volume mesuré d'une leçon (médiane 1 567 au lieu de 735 mots) et
  aurait donné des quotas de génération inventés. `lesson_profile.py` sépare
  `texte_anglais` et `texte_cible`. Figé par `tests/test_profil.py`.
- **Typst embarque un horodatage** : deux compilations du même contenu ne sont
  pas identiques octet pour octet. Pour comparer deux PDF, figer
  `SOURCE_DATE_EPOCH` — testé, le rendu devient reproductible. Sinon comparer le
  contenu (`content/book.json`, `output/review.json`), qui est déterministe.
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

## Réseau — le piège IPv6

- **Sur Render, `api.anthropic.com` se résout en IPv6** (`2607:6bc0::10`) et le
  conteneur n'a pas de sortie IPv6. La bibliothèque échoue sur
  « APIConnectionError: Connection error. » — un message qui ne dit ni que c'est
  le réseau, ni que c'est l'IPv6. L'IPv4 du même hôte (`160.79.104.10:443`)
  répond parfaitement.
- `pipeline/modele.py` construit **tous** les clients du pipeline et force la
  pile IPv4 (`local_address="0.0.0.0"`). `WB_IPV6=1` désactive ce forçage pour
  un hôte qui n'aurait que de l'IPv6.
- Diagnostic reproductible depuis le Web Shell de Render :
  `getent hosts api.anthropic.com` puis un `socket.connect` sur l'adresse IPv4.
  Le Web Shell est le bon outil : le défaut n'existait que sur l'hôte.
- Rappel : `curl` n'est pas dans l'image finale (il ne sert qu'à la construction).
  Diagnostiquer avec `python3 -c` et le module `socket`.

## Produire un livre depuis l'application

- Un projet a désormais un **genre** : `depot` (un `.docx` déposé) ou
  `generation` (un livre à produire), plus sa langue, son projet de référence
  et sa **phase**.
- Les phases : `mesure → plan → vocabulaire_propose → vocabulaire_valide →
  generation → assemblage → pret`. Ce n'est pas une tâche de fond mais une
  **machine à états** : la troisième attend un humain, le professeur natif peut
  mettre des jours à vider sa file, et un redéploiement Render tue le processus.
- Un livre généré **hérite des mesures de son projet de référence** : on copie
  son `book_typed.json` dans le nouvel espace de travail, puis on y mesure
  profil, glossaire et style. Le projet est ainsi autonome.
- **Les titres se transposent** : « How Chinese actually works » devient « How
  Japanese actually works ». Le champ `nom_anglais` de chaque config porte le
  nom tel qu'il apparaît dans les titres. Les sujets, eux, se transportent tels
  quels — se présenter, les nombres, l'heure valent pour n'importe quelle langue.
- **Le coût est annoncé avant chaque action qui dépense** (`server/couts.py`,
  tarifs et consommations mesurés et datés) : « environ 0,72 $ et 3 min » pour
  une progression, « environ 13,69 $ et 52 min » pour 31 leçons.
- **L'état de chaque leçon est en base** (table `lecons`), pas en mémoire : une
  génération dure une heure, un redéploiement Render tue le processus, et
  relancer ne doit refaire que ce qui manque. `declarer_lecons` n'écrase jamais
  une leçon déjà faite.
- **Une leçon à la fois.** La parallélisation à trois a fait tomber la
  génération dans les limites de débit, sans le dire. Un livre qui met une heure
  de plus vaut mieux qu'un livre qui s'arrête en silence.
- Le livre de référence est **mis de côté** (`reference_typed.json`) après avoir
  livré ses mesures : sinon les files de relecture du nouveau projet montrent
  les items de l'ancien.
- **`GID` est une variable spéciale de zsh** (identifiant de groupe, entier) :
  lui affecter un identifiant de projet déclenche une évaluation arithmétique et
  un message incompréhensible. Ne pas la réutiliser dans les scripts shell.
- C1 ne fait **aucun appel à un modèle** : mesure et planification sont
  déterministes, donc gratuites et instantanées. C'est ce qui permet de les
  tester sans dépenser.

## Serveur

- `server/app.py` (FastAPI) — un lien par projet et par rôle, pas de comptes.
  Le jeton arrive par `/r/<jeton>`, part dans un cookie nommé `wb_<projet>_<rôle>`,
  et l'URL affichée ne le contient plus. Cookie nommé par rôle : un manager peut
  tenir plusieurs liens ouverts sans les écraser.
- Chaque rôle ne reçoit **que sa file** : le lien du professeur externe ne
  contient pas le reste du manuscrit.
- `server/store.py` — SQLite. Les décisions sont un journal *append-only* :
  l'état courant d'un item est sa dernière ligne. Donne l'historique et
  permettra de rejouer les décisions après chaque conversion.
- `webapp/console.html` sert dans les deux modes : bundle inliné par `run.sh`
  (fichier autonome, décisions exportées) ou `null` (servie, décisions au
  serveur, plusieurs relecteurs). C'est ce qui évite d'avoir deux consoles.
- Écriture optimiste côté console : la décision est gardée en local et rejouée
  si le réseau tombe. Une coupure ne coûte pas la session d'un professeur.
- **Dépôt** : `/a/<jeton>` ouvre `webapp/admin.html`. Le jeton vient de
  `WB_ADMIN_TOKEN` au déploiement, sinon il est tiré au premier démarrage et
  gardé en base — il n'y a personne pour l'administrer. Le pipeline tourne en
  tâche de fond et la page suit les étapes de `run.sh` (~8 s sur le CN10).
- Un `.docx` est vérifié comme **zip contenant `word/document.xml`** : ni le nom
  du fichier ni le type déclaré par le navigateur ne font foi. Le nom reçu sert
  à l'affichage, jamais de chemin.
- Un échec doit être lisible **là où il est annoncé** et par un non-développeur :
  la fiche du projet donne l'étape, la dernière ligne d'erreur, et range la
  trace Python dans un repli.
- `data/` est jetable : le supprimer remet le serveur à zéro (projets, liens,
  décisions). Rien d'autre n'y est stocké.
- **Une décision fige son contexte au moment où elle est prise** (nature, paire
  visée, adresse) dans la colonne `decisions.context`. Sinon, une fois la
  correction appliquée l'item sort de la file de relecture — et s'il fallait l'y
  relire pour rejouer la décision, la correction s'annulerait d'elle-même à la
  compilation suivante.
- Le bouton **Recompiler** relance `run.sh` sur le manuscrit déposé, décisions
  rejouées. Une correction de professeur se retrouve dans le PDF sans qu'on
  touche au docx.
- **Dépôt Drive** (`server/drive.py`) : compte de service, portée `drive.file`,
  dossier partagé avec son adresse. Un fichier du même nom est remplacé, jamais
  dupliqué — sinon le dossier du projet se remplit d'un `book.pdf` par
  compilation et plus personne ne sait lequel est le bon. Inactif sans
  `WB_DRIVE_CREDENTIALS`, sans rien casser.
- **Sauvegarde** (`server/backup.py`) : seuls les manuscrits et la base sont
  sauvegardés, le reste se régénère. La base passe par l'API de sauvegarde de
  SQLite — en WAL, un `cp` pendant une écriture donne une archive incohérente.
- **La sauvegarde tourne dans le serveur, pas dans un Cron Job**
  (`server/planning.py`) : un disque persistant Render ne se monte que sur un
  seul service, un cron séparé ne verrait pas les données. Un fil quotidien à
  3 h UTC, plus un rattrapage au démarrage si la dernière archive a plus de 24 h
  — sans lui, une instance qui redémarre chaque jour avant l'heure ne sauvegarde
  jamais. Écrire la condition sur l'âge de l'archive la plus récente, pas sur
  l'absence d'archive.
- **Une archive sur le même disque que les données ne protège pas du disque.**
  Elle couvre la suppression et la corruption, pas la perte du volume. D'où le
  bouton « Download a copy » dans la page d'administration et le dépôt Drive
  optionnel (`WB_DRIVE_BACKUP_FOLDER`) : la seule copie qui compte est celle qui
  est ailleurs.
- **Le livre de référence change de nom en cours de projet.** Déposé en
  `content/book_typed.json`, il devient `content/reference_typed.json` une fois
  ses mesures prises, pour ne pas polluer les files de relecture du nouveau
  livre. `assemble.py` le savait, `generate.py` non : trois leçons perdues sur
  `FileNotFoundError`. La résolution vit maintenant dans `pipeline/livre.py`, et
  un test refuse tout script d'après-mesure qui nommerait un des deux fichiers
  en dur.

- **La série de leçons s'arrête sur une erreur qui ne vient pas de la leçon.**
  Un crédit épuisé a été rejoué trente et une fois de suite. `cause_fatale()`
  reconnaît crédit, authentification et droits ; et trois échecs d'affilée
  arrêtent la série de toute façon. Les leçons non tentées restent à faire, donc
  « Resume » les reprend une fois le compte rechargé.

- **Un état affiché doit être vrai.** La génération concluait toujours par
  `ready` : trente et une leçons en échec s'affichaient sous une pastille verte
  READY. L'état vient maintenant du décompte, et le motif du dernier échec
  remonte jusqu'à la bande de la fiche — sans lui, il faut ouvrir les logs du
  serveur, ce que personne dans l'équipe cliente ne peut faire.

- **La clé d'API est nettoyée de ses blancs** (`modele.cle()`). Un retour à la
  ligne collé avec la clé rend l'en-tête HTTP invalide ; `httpx` lève
  `LocalProtocolError`, que la bibliothèque traduit en
  `APIConnectionError: Connection error.` — message qui ne dit ni que c'est la
  clé, ni que c'est un caractère blanc. Même symptôme que la panne IPv6, cause
  entièrement différente.
- **Les journaux sont expurgés avant écriture** (`store.masquer_secrets`) : un
  traceback de bibliothèque HTTP recopie l'en-tête fautif, clé comprise, et ce
  journal s'affiche sur la page et part dans les archives.
  `store.nettoyer_secrets()` au démarrage traite ce qui est déjà écrit.

- **Chaque réponse porte la version déployée** (`X-Workbook-Version`, tirée de
  `RENDER_GIT_COMMIT`). Sans elle, une construction qui échoue laisse l'ancienne
  image en place et le site répond exactement pareil : on ne peut pas savoir si
  un correctif est en ligne. Vérifier :
  `curl -sI https://workbook-engine.onrender.com/ | grep -i workbook-version`

- **Les versions des dépendances sont figées, et ce n'est pas cosmétique.**
  `requirements.txt` disait `anthropic>=0.40` sans borne : une image reconstruite
  s'est retrouvée avec `anthropic` mais sans `httpx`, et la génération est tombée
  sur `ModuleNotFoundError: No module named 'httpx'` alors qu'aucune ligne de
  code n'avait changé. Piège de lecture : `anthropic` importe `httpx` à son
  propre import, donc le traceback se termine sur `httpx` même quand la commande
  écrite est `import anthropic`. Pour monter une version : la changer dans
  `requirements.txt`, lancer `./tests/tous.sh`, pousser.
- **La construction de l'image vérifie ses propres dépendances** (`RUN pip
  install … && python3 -c "import …" && pip check`). Une image incomplète doit
  échouer à la construction, pas une heure plus tard devant un éditeur.
- **Rien de payant ne se lance sans contrôle préalable** (`app.prete_a_generer`) :
  clé absente ou bibliothèque manquante donnent une phrase qui dit quoi faire, en
  haut de la page et sur le bouton, au lieu d'une carte rouge avec un traceback.

- **`tests/tous.sh` doit appeler `.venv/bin/python3`.** Lancé hors venv, il
  appelait le `python3` du système : `fastapi` et `googleapiclient` manquaient et
  trois suites échouaient pour une raison sans rapport avec le code testé.

- **`curl` sans `-f` enregistre la page d'erreur 404 sous le nom du fichier.**
  Une URL de police morte a produit un `SourceSerif4-Italic.ttf` qui était en
  réalité du HTML : Typst ne s'en plaignait pas — la famille existait par ailleurs —
  et tous les livres ont été composés avec un italique de substitution. Vérifier
  une police avec `file`, et ne jamais télécharger sans `-f`.
  Le bon nom est `SourceSerif4-Italic[opsz,wght].ttf`, pas
  `SourceSerif4[opsz,wght]-Italic.ttf`.
- **`su -c "exec $*"` écrase les guillemets de la commande.** Le CMD
  `sh -c "uvicorn app:app --host …"` arrivait à `su` comme
  `sh -c uvicorn app:app --host …` : uvicorn était lancé sans aucun argument et
  le conteneur s'arrêtait aussitôt. Premier déploiement Render échoué à cause de
  ça. La commande est désormais écrite en toutes lettres dans l'entrypoint.
- **Le disque persistant est monté à l'exécution**, avec un propriétaire inconnu
  à la construction de l'image : c'est la cause la plus fréquente d'un premier
  déploiement raté. `docker-entrypoint.sh` l'ajuste en root puis abandonne les
  privilèges.
- Déploiement : `Dockerfile` + `render.yaml`, notice dans `docs/DEPLOIEMENT.md`,
  qui liste aussi **ce qui n'a pas pu être vérifié** (image non construite,
  Drive non testé contre le vrai Google).

## Progression d'une langue neuve — la quatrième file

- `pipeline/propose_vocab.py` fait proposer par le modèle **toute la progression
  en un seul appel** : la cohérence d'une leçon à l'autre est justement ce qu'on
  veut obtenir (pas de doublon, densité décroissante, rien employé avant d'être
  enseigné). 31 appels séparés se répéteraient.
- Les entrées deviennent une **quatrième file de relecture** (`vocab`), à côté
  de prononciation / exercices / corrigés. Le professeur natif ne relit pas un
  livre : il tranche une liste, avant que le livre n'existe.
- **Le bundle sait se construire sans manuscrit** : dans une langue neuve, la
  file de vocabulaire précède le livre.
- **Un glossaire porte sa langue** et le plan la vérifie : sans ce garde-fou,
  un plan japonais héritait du vocabulaire chinois.
- Premier essai japonais : 409 entrées, 1 doublon, 247 entrées sur le premier
  tiers contre 49 sur le dernier — la courbe demandée. Coût : 2 270 jetons en
  entrée, 28 500 en sortie, environ 0,72 $ pour tout un curriculum.
- `pipeline/apply_vocab.py` tire le **curriculum validé** des décisions :
  valider garde, écarter supprime, corriger remplace. Une correction est
  interprétée par son contenu — si elle contient de l'écriture cible, c'est le
  mot qui change ; sinon c'est sa prononciation. Le professeur n'a pas de champ
  à choisir, il écrit ce qu'il faut lire.
- `plan.py` préfère ce curriculum au glossaire d'un livre de référence, et
  annonce lequel il utilise. Une progression approuvée pour *cette* langue vaut
  mieux qu'une progression empruntée à une autre.
- **La console annonçait « écartez ce qui ne se dit pas » sans bouton pour le
  faire.** Action `drop` ajoutée (raccourci X), visible seulement sur les
  entrées de vocabulaire : écarter une prononciation suspecte n'aurait aucun sens.
- **`tc()` et la dérivation des identifiants sont partagés** (`pipeline/ids.py`,
  `pairs.py`). `bundle.py` mettait le titre de leçon en casse de titre avant de
  calculer l'id, `apply_vocab.py` non : aucune décision ne s'appliquait, en
  silence. Deux définitions d'une clé finissent toujours par diverger.
- Piège de rendu : la console s'ouvrait sur la file « professeur », vide dans ce
  cas, ce qui se lit comme « l'outil n'a rien trouvé ». Elle s'ouvre désormais
  sur la première file non vide, et masque les statistiques à zéro.

## Vocabulaire du quotidien — pourquoi il n'y a pas de contrôle automatique

- Arno : « c'est une question de bon sens, privilégier les mots fréquemment
  utilisés » — *je vais nager* plutôt que *je vais piquer une tête*. C'est donc
  une affaire de **registre**, pas seulement de mots rares.
- **Le livre de référence ne peut pas servir de liste blanche.** Mesuré : 1 412
  des 1 974 entrées du livre généré (72 %) sont absentes du vocabulaire du CN10.
  En restreignant aux caractères totalement inconnus du CN10, il reste 183
  entrées — et ce sont 谁 (qui), 姓 (nom de famille), 从 (venir de), 卖 (vendre),
  爷爷 (grand-père), l'heure. Du vocabulaire de base **que le livre publié
  n'enseigne pas**. Le contrôle mesurerait les lacunes de la référence, pas les
  excès de la génération.
- **Une préférence justifiée, pas une interdiction.** Arno, après lecture :
  « il faut une règle assez flexible qui dit que c'est plus efficace d'utiliser
  des mots courants ». Ma première rédaction interdisait (« pas de mots que le
  lecteur n'emploiera jamais ») ; elle explique désormais pourquoi, et laisse la
  place à un mot moins courant s'il sert vraiment le sujet.
- **L'audience est une contrainte, pas un décor** : adulte anglophone (US, CA,
  UK), débutant complet, peu de temps libre, sessions courtes. La page produit
  vend « Busy Adult Beginners » et « 15-Minute Lessons » — la longueur d'une
  leçon est une promesse commerciale. C'est dans `audience` de chaque config.
- Conséquence : la contrainte vit dans le prompt (avec l'exemple d'Arno) et dans
  la file du professeur natif. Elle redeviendra automatisable le jour où une
  liste de fréquence existera — le champ `progression.reference` de la config
  est prévu pour l'accrocher.
- **Les « 2 000+ mots » de la page Amazon sont une tournure marketing**
  (confirmé par Arno) : le budget de vocabulaire reste celui mesuré, 584
  caractères, pas 2 000.

## Config de langue

- **`pipeline/langue.py` est le point unique** où la langue se déclare.
  `WB_LANGUE=japanese` suffit : plage Unicode de l'écriture, signes de la
  romanisation, vérificateur de prononciation viennent tous de
  `config/<langue>.json`. Neuf fichiers portaient la plage des hanzi en dur.
- **Les clés `zh` et `pinyin` sont des emplacements**, pas du chinois :
  « écriture cible » et « prononciation », quelle que soit la langue. Les
  renommer toucherait le convertisseur, le template Typst, la console et les
  décisions déjà enregistrées, pour un gain cosmétique. Décision assumée.
- **Une langue sans vérificateur de prononciation le dit.** Le japonais n'a pas
  d'équivalent de `pypinyin` (la lecture d'un kanji dépend du contexte) :
  `validation_report.txt` écrit alors « non vérifiée automatiquement, à la
  charge du professeur natif » plutôt que de rester vide. Un rapport vide se lit
  comme « rien à signaler ».
- **Trois provenances, pas deux** : « mesuré » (relevé sur un livre validé dans
  cette langue), « gabarit » (repris du CN10 en attendant), « éditorial » (choix
  humain). `check_config.py` refuse de valider un bloc « gabarit » comme mesuré —
  il n'existe pas encore de livre japonais à quoi le comparer.

- `config/chinese.json` pilotera la génération. Chaque bloc porte sa
  **provenance** : « mesuré » (relevé sur un livre validé par les éditeurs et le
  professeur) ou « éditorial » (choix humain, à discuter). On ne devine pas un
  quota.
- `pipeline/lesson_profile.py` mesure le livre ; `pipeline/check_config.py`
  confronte chaque valeur « mesuré » à cette mesure. Une config qui prétend
  décrire les livres validés mais n'y correspond plus est pire qu'absente.
- Mesuré sur le CN10 : 31 leçons, 5 histoires, 584 caractères, prose 360–1 305
  mots (médiane 735), 5–27 tableaux, 0–4 exercices, romanisation **jamais
  retirée**, vocabulaire neuf cinq fois plus dense au début qu'à la fin.
- **Seul le vocabulaire nouveau dépend de la position dans le livre**
  (r = −0,74 avec le rang de la leçon). Volume, tableaux, dialogues et exercices
  ne montrent aucune tendance (|r| < 0,4). Le plan suit donc une courbe pour le
  vocabulaire et une cible constante ailleurs : c'est tout ce que la mesure
  autorise à affirmer.
- La courbe encadre 90 % des leçons du CN10, contre 39 % pour un plan plat.
  Attention à la lecture : la courbe est ajustée sur ce livre, donc 90 % mesure
  l'ajustement, pas la prédiction. C'est l'écart avec le plan plat qui prouve
  que la pente est réelle.
- **Profiler une leçon isolément compte tout son vocabulaire comme neuf.**
  `lesson_profile.profiler({"chapters": [lecon]})` part d'un glossaire vide : une
  leçon générée y paraissait introduire 76 caractères nouveaux au lieu de 8. Le
  vocabulaire neuf se compte **contre le livre de référence**, jamais en vase clos.
- **Les tableaux du livre ont deux colonnes** : la paire `{zh}{py}` puis le sens
  anglais. Le modèle en propose souvent trois (Chinese / Pinyin / English) — on
  garde la première et la dernière, jamais celle du milieu.
- **Une leçon peut exercer ce qu'elle vient d'enseigner.** Le contrôle de
  vocabulaire compare au livre de référence *plus* ce que la leçon présente
  elle-même en tableau, paire ou dialogue. Sans cette règle, une leçon générée
  qui respecte son quota de vocabulaire neuf était signalée pour l'avoir employé.
- **Un plafond de jetons trop bas coûte le prix d'une génération pour rien.**
  Une leçon complète dépasse 16 000 jetons en sortie : on génère en streaming,
  et `stop_reason == "max_tokens"` est détecté explicitement plutôt que de finir
  en JSON illisible.
- **Un quota présenté comme un plafond est traité comme tel.** Le prompt disait
  « caractères nouveaux : 15 au maximum » et le modèle en produisait 8. Reformulé
  en cible à atteindre, avec sa raison (la progression du livre) et une
  déclaration explicite du vocabulaire introduit : 12.
- **Deux bandes pour deux usages.** Par défaut la bande est l'étendue du livre
  humain : assez large pour ne pas recaler ses auteurs (6 % de leçons signalées).
  `check_lesson.py --serre` resserre à ±35 % de la cible, pour du contenu
  **généré**, qui doit viser la cible et pas seulement rester dans l'enveloppe.
  Ne jamais pointer `--serre` sur un manuscrit humain : il en signalerait 94 %.
- **Un quota impossible à tenir vient parfois du schéma, pas du prompt.** Le
  schéma de génération n'autorisait qu'un tableau par section : avec 7 sections,
  atteindre les 11 tableaux du plan était impossible. Corrigé en tableau de
  tableaux, la leçon générée tombe pile sur 11 tableaux et 65 paires.
- **Le livre a deux numérotations** : les leçons seules (1–31, celles que
  décrit le plan) et les leçons plus les histoires (1–36, l'ordre de lecture).
  Les quotas se comparent au plan, le vocabulaire s'acquiert dans l'ordre de
  lecture. Les confondre a produit trois vagues de faux positifs successives,
  jusqu'à 90 % des leçons signalées.
- **Le motif des paires `{zh}{py}` doit tolérer la mise en forme.** Le
  manuscrit écrit `{zh:你好} *{py:nǐ hǎo}*` ; un motif qui n'accepte que des
  espaces laissait passer **743 paires du CN10, soit 46 %**, jamais vérifiées
  par le contrôle du pinyin. Corrigé dans `pipeline/pairs.py`, partagé par
  `validate.py` et `bundle.py` : 2 780 paires couvertes, taux de signalement
  inchangé (0,72 %).
- **Une bande de contrôle doit être l'étendue mesurée, pas une tolérance
  inventée.** Contrôler à ±50 % de la médiane signalait 71 % des leçons du
  livre validé ; contrôler contre le min et le max observés en signale 0.
- **Le contenu interne aux exercices enseigne** (banques de mots, textes de
  compréhension) : l'exclure ferait passer le contrôle de vocabulaire de 6 % à
  29 % de leçons signalées sur un livre validé.
- **Répartition des exercices par méthode proportionnelle** (Sainte-Laguë) :
  un premier entrelacement naïf poussait tous les types rares dans les premières
  leçons et laissait la fin uniforme.
- Les niveaux HSK visés sont marqués « éditorial » et non confirmés : le CN10
  n'annonce aucun niveau. À valider avec Arno avant de s'en servir comme
  contrainte.

## Briques de génération

- `pipeline/glossary.py` — première apparition de chaque caractère (584) et
  entrée de vocabulaire (493). Rend la difficulté croissante *vérifiable*.
- `pipeline/style.py` — consignes par type d'exercice, paragraphes types, et la
  **base humaine de répétition** : 1,0 % des suites de 5 mots sont répétées 3
  fois ou plus, maximum 38. Toute règle anti-répétitivité se compare à ça.
- `pipeline/check_lesson.py` — quotas, vocabulaire non enseigné, répétitivité,
  réponses présentes. Mesuré sur les 31 leçons du CN10 : **2 signalées (6 %)**,
  toutes deux réelles (un exercice fait choisir 蛋糕, introduit nulle part avant).
  Le seuil de répétition n'est pas choisi : il est déduit de la pire leçon
  humaine, avec 20 % de marge.

## Génération

- `pipeline/generate.py` — une leçon sous contrainte du plan, du glossaire et
  des exemples de style. Sortie **structurée** imposée par un schéma JSON : le
  modèle ne produit jamais de mise en page (invariant 1), et chaque exercice
  porte ses réponses (invariant 2).
- La sortie brute du modèle est conservée (`*_brut.json`) : `--reconvertir`
  reconstruit les blocs sans repayer un appel quand le convertisseur change.
- Première mesure sur la leçon 12 : 5 185 jetons en entrée, ~13 000 en sortie,
  ≈ 0,34 $ et 2 min 30 par leçon, soit ~11 $ le livre.
- Qualité observée : ton juste, prose et dialogues aux quotas, et la leçon
  s'appuie explicitement sur le glossaire (« you already know 天 from 今天 »).
  La leçon générée atteint **toutes ses cibles** et passe le contrôle en bande
  serrée sans remarque. Deux tirages successifs donnent des quotas identiques
  (11 tableaux, 65 paires, 7 sections, 2 dialogues, 9 répliques, 3 exercices) :
  la génération est stable. Coût ≈ 0,45 $ et 3 min par leçon.

## Langue de l'interface

- **Tout ce que voit un utilisateur est en anglais** : la console de relecture,
  la page de dépôt, les messages d'erreur du serveur, les coûts annoncés, les
  noms de langues. Raison : les professeurs natifs changent à chaque langue et
  ne sont pas francophones. Décision d'Arno, 28 août 2026.
- **Le reste demeure en français** : commentaires de code, messages de commit,
  cette mémoire, et les rapports texte du pipeline, lus par l'équipe interne.
- Chaque config porte `nom_affiche` et `public_affiche` : le nom montré dans
  l'application. `langue` et `public` restent en français pour la lecture
  interne des configs.

## Design de la page de dépôt

- Reprise d'un bloc le 28 août. Le défaut : la page faisait trois choses de même
  poids visuel, et sur une fiche de projet **l'action à faire était enterrée**
  sous quatre lignes de liens.
- **Une seule carte « Start a book », deux onglets.** Déposer un manuscrit et
  produire une autre langue créent tous deux un projet : deux formulaires côte à
  côte se disputaient l'attention.
- **La bande « prochaine action » passe avant tout le reste** sur chaque fiche :
  un titre qui dit quoi faire, la barre d'avancement s'il y en a une, le coût
  annoncé, le bouton. Vert quand il y a une action, ambre quand ça attend un
  humain, gris quand il n'y a rien à faire.
- **Le secondaire descend dans des replis** : plan du livre, dossier Drive.
  Les liens de relecture restent visibles — c'est ce qu'on vient copier.
- Pas de thème sombre, comme la console : la palette papier du livre est un
  choix, pas un oubli.

## Design de la console

- Palette reprise du livre : pin `#1A5E52`, ambre `#E5A33C`, papier `#EEF2F0`.
- Typo de la console = typo du livre (Archivo + Source Serif 4), pour que le
  texte relu ait l'allure qu'il aura imprimé. Données en IBM Plex Mono.
- Élément signature : le rail de gauche, le livre vu par la tranche ; chaque
  trait est une leçon, ambre s'il reste des items, vert quand c'est traité.
- Navigation clavier obligatoire (`J`/`K`/`A`/`C`/`S`) : c'est ce qui rend une
  file rapide à vider.
