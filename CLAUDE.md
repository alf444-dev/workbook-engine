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
| Répétition inter-leçons (prompt + contrôle) | ✅ `pipeline/repetition.py`, `tests/test_repetition.py` |
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
- **`convert.py` prend son manuscrit par `WB_SOURCE` ou en argument.** Le défaut
  était `/mnt/user-data/uploads/…`, un chemin hérité de la machine où le fichier
  a été écrit : `python3 pipeline/convert.py livre.docx` échouait sur le fichier
  de quelqu'un d'autre, avec un message qui ne disait pas pourquoi.
- **Le convertisseur est éprouvé sur des manuscrits dégénérés**
  (`tests/test_manuscrits.py`) : document vide, prose sans titres, crochets
  vides, paire non fermée, deux paires collées, emoji, paragraphe de 4 000
  caractères — puis rendu jusqu'au PDF. Le parseur a été taillé sur un seul
  livre ; l'équipe en déposera d'autres.
- **La simultanéité est mesurée, pas supposée** (`tests/test_concurrence.py`) :
  900 écritures et 120 lectures entrelacées, aucun verrou, aucune séquence en
  double, le journal reste append-only et l'état courant est bien la dernière
  décision.

- **Le champ de correction de la console s'ouvrait sous la barre du bas.** Le
  professeur tapait sa correction sans voir ce qu'il écrivait — trouvé en
  pilotant la console dans un vrai navigateur, invisible autrement. Deux causes
  cumulées : `focus()` défile de lui-même et annulait l'animation qui suivait, et
  la boîte venait de passer de `display:none` à visible, donc on mesurait une
  position périmée. D'où `focus({preventScroll:true})`, un reflow forcé, et un
  défilement sans animation.
- **Un livre en échec s'annonçait « en cours de construction »** au professeur,
  et la page se rechargeait indéfiniment. Trois situations, trois messages :
  compilation en cours (se recharge seule), compilation échouée (rien à faire de
  son côté), lien renouvelé (en redemander un).
- **Une seule formulation des sept étapes.** La page d'administration avait sa
  propre liste, `run.sh` la sienne : deux descriptions des mêmes étapes avec des
  mots différents. Elles sont alignées et un test les compare. La page se cale
  sur le numéro (« 4/7 »), pas sur le texte — c'est ce qui a évité que le
  passage à l'anglais casse le suivi.

- **Les libellés « n/7 » de `run.sh` sont relayés tels quels sur la page** que
  lisent les relecteurs : ils sont donc en anglais, et un test refuse un accent
  français dedans. Le relecteur ne voit que « Step 3 of 7 » — le nom de l'étape
  ne lui sert à rien.

- **Une décision ne reconstruit plus la file entière.** Sur une progression de
  465 entrées — la file la plus longue, celle que le professeur vide touche
  après touche — chaque frappe coûtait 75 ms de JavaScript et de mise en page,
  sur une machine rapide. Seule la carte tranchée est redessinée : 8 ms.
- **Aucun défilement animé dans la console.** Deux fois le même piège : un
  `behavior:'smooth'` relancé avant la fin du précédent s'annule, et la carte
  courante finissait hors écran, à 3 000 pixels. Mesuré, pas supposé.

- **`id_scheme` était écrit dans chaque file et lu par personne** : un filet de
  sécurité débranché. Changer le calcul des identifiants aurait fait
  réapparaître comme neufs des items déjà tranchés, en silence. Le serveur le
  compare maintenant au schéma courant et la console prévient le relecteur.
  Les décisions restent en base et continuent d'être rejouées sur le livre — ce
  qu'on perdrait, c'est le rattachement à un item.

- **La console dit au relecteur qu'il a fini.** « 0 to review » en petit ne
  suffit pas à quelqu'un qui n'a reçu aucune formation : une bande annonce que
  tout est réglé et enregistré, et qu'il peut fermer la page.
- **La page d'administration ne chargeait aucune police.** Elle déclarait
  Archivo et Source Serif 4 sans jamais les demander : son titre rendait en
  Georgia, et les deux écrans du même outil ne se ressemblaient pas. Invisible à
  l'œil sur un Mac, mesurable dans le navigateur — `document.fonts.size` valait
  zéro. Les deux pages portent maintenant le même lien, et un test l'exige.

- **Une variable CSS empruntée à l'autre page ne casse rien de visible** — le
  bloc s'affiche simplement sans fond. Un test compare désormais les `var(--x)`
  utilisées aux variables définies, dans les deux pages.

- **Ce que la console propose doit exister côté serveur.**
  `tests/test_console.py` compare les actions envoyées par la page à la liste
  `ACTIONS` du serveur, dans les deux sens. La page a déjà annoncé un raccourci
  que le serveur refusait.

- **`tests/test_securite.py` énumère les routes du serveur** et exige que
  chacune refuse un visiteur sans lien. Une route ajoutée sans garde-fou fait
  échouer le test sans que personne ait à y penser — vérifié en lui présentant
  une route ouverte, qu'il nomme. Il couvre aussi le cloisonnement entre rôles
  et entre projets, la révocation, les entrées hostiles et ce que les refus
  laissent voir.
- **`workspace(pid)` refuse un identifiant qui n'est pas hexadécimal.** Les
  routes HTTP normalisent déjà les `..`, mais `DATA / "projects" / "../.."` sort
  du disque de données : la vérification est au seul endroit qui construit le
  chemin, pas chez chaque appelant.

- **Deux tests exercent la chaîne entière, pas ses morceaux.**
  `tests/test_bout_en_bout.py` rejoue un livre en langue nouvelle hors ligne —
  mesure, plan, progression, décisions du professeur, curriculum, contrôles,
  leçons, assemblage, PDF — et vérifie que la couverture dit « LEARN JAPANESE »
  et que les pages portent des kana. `tests/test_promesse.py` joue le critère de
  validation de `docs/NEXT_TASK.md` à travers le serveur, avec le vrai
  manuscrit : dépôt, file du professeur, correction, recompilation, correction
  présente dans le livre. Chaque étape était testée seule ; le livre écrit dans
  la mauvaise langue est passé entre les mailles parce que rien ne testait la
  suite.
- **Une archive qu'on n'a jamais rouverte n'est pas une sauvegarde.**
  `backup.restaurer()` existe désormais et le trajet complet est exercé —
  archiver, effacer, restaurer, relire les projets et les décisions. Elle refuse
  d'écraser une base existante et ignore tout chemin d'archive qui sortirait de
  `WB_DATA` (`tarfile` ne s'en protège pas seul avant Python 3.12).
- **Un item de relecture change d'identifiant quand son contenu change**, donc
  une correction qui ne satisfait pas le contrôle automatique revient dans la
  file en portant le texte du professeur. C'est voulu (`bundle.py` : « le sens
  sûr de l'erreur »), c'est vérifié, et ce n'est pas un bug — ne pas le
  « corriger » sans mesurer ce qu'on perd.

- **Tout ce qui se vérifie gratuitement se vérifie avant de payer**
  (`pipeline/check_generation.py`, dépliant « Checks before writing » sur la
  fiche). Il relit le plan, la langue du vocabulaire imposé, la provenance du
  glossaire, et surtout **le prompt réel de la leçon 1** : tout caractère d'une
  écriture enseignée qui ne vient pas du vocabulaire prévu est signalé. Chacun
  des signes avant-coureurs du livre chinois-pour-japonais y était visible.
- **Une leçon se refait seule** (`POST /admin/projects/{id}/lecons/{n}/refaire`,
  liste « Lessons » sur la fiche). Refaire la 12 refait la 12, pas la première
  manquante — le piège évident de `a_faire[:1]`. La version remplacée est gardée
  en `lecon_NN_precedente.json`.
- **Les messages destinés à la page sont en anglais**, y compris ceux produits
  par le pipeline (contrôles, refus de langue, refus d'assemblage) : ils sont
  affichés à des relecteurs qui ne parlent pas français. Les commentaires et les
  rapports internes restent en français.

- **On écrit une leçon avant d'en payer trente.** Le livre chinois-pour-japonais
  a coûté 15 $ et n'était visible qu'une fois les 31 leçons écrites et le livre
  assemblé. La page propose maintenant « Write lesson 1 » (moins d'un dollar),
  et `/admin/projects/{id}/lecons/{n}` rend une leçon lisible seule — sans quoi
  vérifier à moindres frais était impossible, l'assemblage exigeant le livre
  complet. Une série volontairement courte n'est pas comptée comme un échec.

- **Le livre de référence sert de forme, jamais de contenu.** Un livre japonais
  est sorti avec 225 pages de chinois sur 238 : le prompt de chaque leçon
  recevait 260 mots du glossaire chinois comme « vocabulaire déjà enseigné » et
  trois paragraphes chinois à imiter, et c'était le seul matériau concret qu'il
  contenait. `plan.py` avait ce garde-fou, `generate.py` non. Désormais
  `generate.materiau()` écarte tout matériau d'une autre langue et retire les
  mots étrangers des exemples de style, en disant au modèle d'où ils viennent.
  Le ton se transporte, le lexique jamais.
- **La validation du professeur doit atteindre la génération.**
  `apply_vocab.py` était écrit, testé, documenté — et appelé par personne ; et
  `plan.py` ne tournait qu'une fois, avant même que le vocabulaire soit proposé.
  La phase « progression approved » était décorative. Le serveur enchaîne
  maintenant `apply_vocab.py` puis `plan.py`, et **refuse d'écrire les leçons
  quand le plan n'impose aucun vocabulaire** — c'est cet état qui a produit le
  livre chinois.
- **Kanji et sinogrammes partagent le même bloc Unicode**, donc « écriture
  cible » ne distingue pas le japonais du chinois. Chaque config déclare une
  `signature` (les kana pour le japonais) et éventuellement un `exclut` ; une
  leçon qui ne la porte pas est refusée avant d'être écrite sur le disque
  (`langue.langue_plausible`). Un contrôle de langue naïf serait passé.
- **Un assemblage à trous est refusé quand la référence est d'une autre
  langue** : reprendre les chapitres manquants donne un livre qui a l'air fini
  et enseigne la mauvaise langue. Dans la même langue, la reprise reste permise —
  c'est un brouillon lisible.

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

- **Un `200` ne prouve pas que l'application tourne** : pendant un redémarrage,
  Render sert une page d'attente qui répond 200 sans porter nos en-têtes. Le
  seul signal fiable est `X-Workbook-Version` — c'est ce que vérifie
  `tests/fumee.py <url>`, à lancer après chaque mise en production.
- **Les en-têtes HTTP sont insensibles à la casse, `dict(r.headers)` non.**
  En HTTP/2 ils arrivent en minuscules, et un `get("X-Workbook-Version")`
  renvoie None sur une réponse parfaitement correcte. Mon propre contrôle a
  commencé par accuser la production d'un défaut qui était le sien.

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

## Un livre dans n'importe quelle langue, sans développeur

Jusqu'ici, lancer un titre en coréen demandait qu'on écrive un fichier de config
à la main. La page le fait maintenant : « The language you need is not in the
list », un nom, un code, une écriture choisie dans une liste.

- **`pipeline/ecritures.py`** — dix systèmes d'écriture avec leur plage Unicode,
  leur signature et ce qu'ils excluent. Le team manager n'a pas à savoir que le
  hangul occupe U+AC00–U+D7A3. Les dix sont vérifiés contre du vrai texte, et
  aucun ne mord sur l'anglais.
- **Les langues à alphabet latin ne sont pas prises en charge, et c'est dit.**
  Tout le moteur distingue l'écriture enseignée de la langue d'explication :
  une colonne pour l'écriture cible, une pour sa prononciation, et le
  vocabulaire nouveau se compte sur les caractères de la cible. Pour l'espagnol,
  cette distinction n'existe pas — la prose anglaise et les mots espagnols
  partagent l'alphabet. Ce n'est pas une limite de la table, c'est une limite du
  moteur ; la taire ferait produire un livre faux.
- **La provenance reste vraie.** Les quotas de la config chinoise sont marqués
  « mesuré » — sur le livre chinois. Recopiés dans une config coréenne ils ne
  mesurent plus rien : `nouvelle_langue.py` les remarque « gabarit Chinese » et
  garde trace de ce qu'ils étaient. C'est un test qui l'a exigé, pas moi.
- **Les langues créées vivent sur le disque persistant** (`WB_DATA/config`), pas
  dans l'image : `config/` est reconstruit à chaque déploiement. `langue.py` y
  regarde d'abord, les espaces de travail les reçoivent, et la sauvegarde les
  emporte — c'est du travail humain qui ne se régénère pas.

## Relecture multi-agents — la mécanique est là, les agents n'ont pas tourné

`pipeline/relecture.py`, phase 3bis de la feuille de route. Quatre décisions,
toutes dictées par des invariants existants :

- **À l'aveugle.** Le paquet ne dit ni d'où vient le texte, ni s'il a été écrit
  par un humain ou par un modèle. Un relecteur qui sait qu'il lit une machine
  cherche des fautes de machine. Neuf tests vérifient qu'aucune trace ne passe.
- **Sous quota** (8 remarques, borné dans le schéma). Sans quota, un modèle en
  trouve toujours plus, et une file qui déborde ne se vide pas : c'est
  l'invariant 4 sous une autre forme.
- **Au vote.** Il faut deux relecteurs indépendants, sur des modèles distincts,
  pour qu'une remarque remonte à un humain ; une voix seule reste en réserve.
  Deux remarques comptent pour la même quand elles visent la même unité et la
  même catégorie — on ne compare pas les phrases, deux relecteurs ne disent
  jamais la même chose de la même façon.
- **Sans réécriture.** Le relecteur constate et localise, il ne récrit pas.

Le prompt **énumère ce que le code vérifie déjà** — prononciation, quotas,
bijection des réponses, caractères non enseignés, répétition — et dit qu'une
remarque sur ces points est perdue. C'est l'invariant 3 appliqué au prompt
lui-même : on ne paie pas un modèle pour refaire ce qu'un programme fait mieux.

Chaque unité porte l'adresse qu'utilisent déjà les décisions : une remarque peut
devenir une correction appliquée au bon endroit, et alimente les files humaines
existantes plutôt que d'en créer une nouvelle.

**Évaluation** : la feuille de route demande de retrouver « les erreurs déjà
identifiées ». Personne n'a encore relu de livre à la main — on sème donc des
défauts connus et on mesure ce que la chaîne en fait, avec un panel simulé. Un
relecteur défaillant sur trois ne fait pas perdre les défauts ; deux, si — et
c'est le sens sûr de l'erreur, on préfère taire que noyer.

Coût mesuré sur les paquets réels du CN10 (~2 900 jetons d'entrée par leçon) :
un panel Opus 5 + Sonnet 5 + Haiku 4.5 revient à **0,14 $ la leçon, 4,45 $ le
livre** — 2,22 $ en batch. Moins cher que d'écrire le livre. Aucun agent n'a
encore tourné : c'est la prochaine dépense à décider.

## Le coût n'était pas le modèle, c'était la réflexion (2 septembre 2026)

Mesuré sur la leçon 5 du CN10, même prompt, même schéma :

| modèle | effort | sortie | dont réflexion | $/leçon | livre de 31 | durée |
|---|---|---|---|---|---|---|
| Opus 5 | high (défaut) | 17 408 | ~79 % | 0,458 | 14,19 | 197 s |
| Opus 5 | medium | 11 597 | **39 %** | 0,313 | 9,69 | 134 s |
| Opus 5 | low | 8 878 | **25 %** | 0,245 | **7,58** | 103 s |
| Sonnet 5 | high (défaut) | 28 215 | ~79 % | 0,291 | 9,03 | 241 s |

Les quatre versions donnent **exactement les mêmes mesures** : un écart de quota
(le même), 0 % de reprise inter-leçons, 15/15 du vocabulaire imposé enseigné.

- **Opus à effort `low` coûte moins cher que Sonnet à effort par défaut**, et va
  deux fois plus vite. La question « Opus ou Sonnet » était mal posée : le coût
  n'est pas dans le choix du modèle mais dans la profondeur de réflexion, qui se
  règle par `output_config: {"effort": …}` (`pipeline/generate.py --effort`).
- **Sonnet écrit 62 % de jetons de plus qu'Opus pour un contenu identique**
  (14,4 k caractères contre 14,8 k, 65 lignes de tableau chacun) : tout l'écart
  est de la réflexion. Le seul rapport des tarifs annonçait 60 % d'économie ;
  la mesure en donne 36 %. Ne jamais déduire une économie d'une grille tarifaire.
- **L'unique écart de quota est le même partout** — 19 à 23 caractères nouveaux
  pour une bande de 26–54. Ce n'est pas un défaut de modèle mais l'incohérence
  déjà connue du plan : la cible compte tous les caractères du livre de
  référence, la liste imposée ne porte que le vocabulaire marqué.
- Ce qui reste à trancher ne se mesure pas ici : la qualité de la prose à effort
  réduit. Elle demande une lecture d'éditeur, à l'aveugle.

## Comparer deux modèles — l'outil, pas encore la réponse

`pipeline/comparer.py` écrit la même leçon avec plusieurs modèles et la note sur
trois critères mécaniques : les bandes de `check_lesson --serre`, la part de
prose reprise aux leçons précédentes, et le vocabulaire imposé réellement
enseigné. Il produit ensuite `A.html` et `B.html` **sans dire lequel est
lequel** — la correspondance est dans `cle.json`, à ouvrir après avoir lu.
Savoir quel modèle on lit suffit à orienter le jugement.

`--simuler` note ce qui est déjà là, sans appeler l'API : l'outil se vérifie et
se rejoue gratuitement.

Tarifs relevés le 2 septembre 2026 (`pipeline/tarifs.py`) : Opus 5 à 5/25 $ le
million de jetons, Sonnet 5 à 2/10 $. Une leçon coûte 0,44 $ contre 0,18 $, un
livre de 31 leçons 13,69 $ contre 5,47 $. **L'API Batch enlève 50 % sur les
deux** — 6,84 $ et 2,74 $ — pour un travail qui prend déjà 52 minutes et n'a
rien d'urgent : c'est le seul levier qui divise la facture sans toucher à ce qui
est écrit.

- **La table des tarifs vit dans `pipeline/`, pas dans `server/`.** Un espace de
  travail ne reçoit que le pipeline (`workspace.CODE`) : un script du moteur qui
  importe le serveur marche sur un poste de développement et tombe en
  production. C'est arrivé en écrivant cet outil ; un test l'interdit désormais.
- **Un tarif inconnu retombe sur le modèle par défaut, jamais sur zéro** :
  une table incomplète doit faire surestimer la dépense, pas l'annoncer gratuite.

## Audit du 2 septembre 2026 — ce qui a été corrigé

- **La répétitivité n'était contrôlée qu'à l'intérieur d'une leçon.** La
  plainte des éditeurs (« très répétitif ») porte sur ce qui revient *d'une
  leçon à l'autre* — et le prompt ne disait pas au modèle ce qui avait déjà
  été écrit. `pipeline/repetition.py` : les tournures et débuts de paragraphe
  employés dans ≥ 2 leçons précédentes vont dans le brief (~170 jetons),
  et `check_lesson.py` mesure la part de prose reprise aux leçons antérieures.
  Seuil déduit du CN10 : 7,2 % (pire leçon humaine 6,0 %, médiane 0,6 %),
  zéro faux positif. Seule la prose compte : en-têtes de tableaux et consignes
  d'exercices sont la voix maison, on veut qu'ils se répètent.
- **Toutes les routes d'action passaient le projet en « running » sans
  vérifier s'il l'était déjà.** Deux clics sur *Write lessons* = deux séries
  payées en parallèle, sur le même espace. `store.reserver()` fait la
  condition **dans la requête SQL** (`WHERE status != 'running'`) — seul
  endroit où deux requêtes simultanées sont sérialisées ; 409 sinon.
- **Un redéploiement laissait le projet « running » pour toujours.**
  `store.reprendre_interrompus()` au démarrage le passe en échec, avec un
  message qui dit de relancer ; les leçons finies sont conservées.
- **Aucun délai sur les sous-processus.** Chien de garde sur `run.sh`
  (`WB_TIMEOUT_RUN`, 15 min) et sur chaque script (`WB_TIMEOUT_SCRIPT`, 30 min).
  Le processus est tué, ce qui ferme le tube et libère la lecture ligne à ligne.
- **Bombe zip** : la borne de 40 Mo portait sur le fichier reçu ; `est_docx`
  borne désormais la taille **dépliée** (300 Mo). `zipfile.writestr` n'accepte
  pas de falsifier `file_size` : le test abaisse la borne au lieu de fabriquer
  une vraie bombe.
- Comparaison du jeton admin en temps constant (`secrets.compare_digest`) ;
  `X-Frame-Options: DENY` et une CSP (`frame-ancestors 'none'`, polices Google
  seules à l'extérieur) ; uvicorn avec `--forwarded-allow-ips=*`, sans quoi
  `request.base_url` restait en `http://` derrière le proxy de Render et les
  liens renouvelés sortaient en http.
- **Un décorateur FastAPI se pose sur la fonction qui le suit
  immédiatement** : insérer une aide entre `@app.get(...)` et `def route()`
  attache la route à l'aide — silencieusement. C'est arrivé pendant cet
  audit ; `test_securite` l'a attrapé.
- `test_langue` dépendait de `content/profile.json` sans le dire : il le
  produit maintenant lui-même si le livre est là.

### Audit UX du même jour

- **Une fiche pose une question, les boutons y répondent.** « Keep / Fix /
  Skip » ne disait pas *quoi* garder — la prononciation écrite ou celle
  suggérée. Chaque type de fiche a sa question (`ASK` dans `console.html`) :
  « Is the pronunciation, as written in the book, correct? » → « Yes, correct /
  No — fix it / Not sure ». Les identifiants d'action (`ok`, `fix`, `skip`,
  `drop`) sont inchangés : le serveur ne voit pas la différence.
- **« Expected » devient « Suggested »**, avec la mention que ça vient d'un
  dictionnaire et peut être faux dans ce contexte. Étiqueter la sortie de
  pypinyin « attendu » poussait le professeur à l'accepter — c'est lui
  l'autorité (invariant 5), pas le dictionnaire.
- **L'accueil dit la taille du travail** : « 15 cards to check — about 5
  minutes ». Un professeur externe qui reçoit un lien craint 240 pages à
  relire ; le lui dire avant son prénom change sa disposition.
- **Les raccourcis clavier disparaissent sur écran tactile** (`@media
  (hover:none)`) : sur un téléphone ils sont du bruit.
- **Page de dépôt : un clic arme, un second lance**, pour tout ce qui coûte
  (`armer()` dans `admin.html`) et pour la révocation d'un lien. Le bouton
  devient « Confirm — about 13.69 $ and 52 min » et se désarme seul après 6 s
  ou au clic ailleurs. Pas de `confirm()` : la boîte du navigateur coupe le fil
  et ne montre pas le prix.

Restent ouverts : la relecture multi-agents à l'aveugle (roadmap, phase
3bis), et l'essai de Sonnet à la place d'Opus pour les leçons, avec
`check_lesson --serre` comme juge — potentiellement cinq fois moins cher.

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
