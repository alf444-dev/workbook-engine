# Plan — un moteur qui écrit comme la maison, vite, et sans effort pour l'équipe

État au 2 septembre 2026 : 71 commits, 16 suites de tests, la chaîne complète
docx → PDF, la génération pilotée depuis la page, un panel de relecture à
l'aveugle, l'effort de réflexion mesuré. Ce plan part de ce qui existe.

Trois axes, dans l'ordre d'impact sur le produit :

1. **Humaniser** — que les livres sortent avec la voix de la maison, pas celle
   d'un modèle. C'est ce qui décide si les éditeurs relisent ou réécrivent.
2. **Accélérer et alléger** — moins cher, plus vite, sans toucher au texte.
3. **Simplifier** — que l'équipe n'ait jamais à comprendre le moteur.

Chaque chantier a une mesure de succès. Aucun ne se valide « à l'œil ».

---

## Comment travailler ce plan avec Claude Code

Ce fichier vit dans `docs/PLAN.md`. `CLAUDE.md` doit y renvoyer, sinon il
n'est pas lu au démarrage d'une session.

**Règles de travail, valables pour chaque chantier :**

1. **Un chantier à la fois.** Proposer le découpage avant d'écrire une ligne.
2. **Mesurer avant de dépenser.** Tout ce qui peut se vérifier sur ce qui
   existe déjà (`--simuler`, le CN10, les leçons déjà générées) se vérifie
   d'abord. Aucun appel à l'API sans annoncer le coût estimé et attendre un
   accord explicite. Plafond par session : 5 $ sauf accord contraire.
3. **Une mesure de succès atteinte, ou le chantier n'est pas fini.** Pas de
   « ça a l'air mieux ».
4. **`tests/tous.sh` au vert avant chaque commit.** Un chantier ajoute ses
   propres vérifications.
5. **`CLAUDE.md` mis à jour à la fin de chaque chantier** : l'état, et les
   pièges rencontrés dans la section prévue. C'est la mémoire du projet.
6. **Ne pas toucher aux invariants** de `CLAUDE.md`. En cas de doute, demander.

**L'indicateur qui juge le projet** : la part de paragraphes que les éditeurs
réécrivent encore, livre après livre. À afficher sur le tableau de bord (3.2)
dès que la vue d'édition (1.3) existe. S'il ne descend pas, le reste n'a pas
d'importance.

**Message d'ouverture :**

> Lis CLAUDE.md, puis docs/PLAN.md en entier — c'est le plan produit, avec
> ses règles de travail en tête. On commence par le chantier 1.1,
> `pipeline/voix.py`. Propose-moi la liste exacte des signaux que tu comptes
> mesurer et comment tu déduis chaque bande du CN10, avant de coder. Ensuite
> mesure les leçons déjà générées avec `--simuler`, sans appel à l'API, et
> montre-moi ce qui dépasse. On ne branche rien dans le brief tant que je n'ai
> pas vu ces chiffres.

---

## Axe 1 — Humaniser

### 1.1 Mesurer ce qui « sent l'IA » — sur le livre humain d'abord

Aujourd'hui `check_lesson` vérifie les quotas (mots, tableaux, dialogues),
le vocabulaire imposé et la répétition. Rien ne mesure la **voix**. Or ce que
les éditeurs appellent « robotique » est mesurable, et le CN10 donne la
référence de ce qu'un texte humain se permet :

| Signal | Ce que fait un modèle | Ce qu'on mesure |
|---|---|---|
| Rythme | phrases de longueur uniforme | écart-type de la longueur des phrases (l'humain est irrégulier) |
| Tics | « It's worth noting », « Let's dive in », « Whether you're… or… », « In today's… », « a testament to » | fréquence pour mille mots, liste alimentée par les réécritures des éditeurs (1.3) |
| Listes de trois | « clear, simple, and effective » | proportion d'énumérations à exactement trois termes |
| Questions rhétoriques | « Sound familiar? » | densité |
| Ponctuation | tirets longs, points d'exclamation | densité |
| Débuts de phrase | « This », « It's », « You'll » en rafale | part des phrases commençant par le même mot que la précédente |
| Adverbes | « truly », « simply », « effectively » | part des mots en -ly |

**Livrable** : `pipeline/voix.py`, bandes déduites du CN10 avec 20 % de marge
(invariant 4), branché dans `check_lesson` et dans `comparer.py`.
**Succès** : aucune leçon humaine signalée ; une leçon générée sans consigne de
voix signalée sur au moins deux signaux (à vérifier sur celles déjà écrites,
`--simuler`, sans dépenser).

### 1.2 La leçon humaine la plus proche comme modèle entier

Le brief donne trois paragraphes types. Un modèle imite bien mieux une **leçon
complète** de même nature — une leçon sur les nombres modèle une leçon sur les
nombres, avec sa structure, ses transitions, sa façon d'introduire un tableau.

**Livrable** : dans `generate.brief`, retrouver la leçon du livre de référence
la plus proche (même section, mêmes composants, quotas voisins) et la joindre
comme exemple, à la place des trois paragraphes. Coût : ~2 000 jetons, que le
cache de prompt (2.1) rend presque gratuits.
**Succès** : `voix.py` et `repetition.py` meilleurs sur la même leçon, à
l'aveugle dans `comparer.py`.

### 1.3 Capturer les réécritures des éditeurs — le chantier le plus important

C'est le trou du produit. Les éditeurs « humanisent » les leçons, et ce travail
est perdu à chaque livre : il ne revient jamais dans le moteur.

**Livrable** : une vue de leçon **éditable** dans la console (rôle éditeur).
Lire la leçon générée, cliquer un paragraphe, le réécrire en place,
enregistrer. Chaque enregistrement stocke la paire *(avant, après)*.

Ces paires deviennent trois choses :
- des **exemples négatifs/positifs dans le brief** : « n'écris pas ceci ;
  écris cela » — le signal le plus direct qui existe pour apprendre une voix ;
- la **liste des tics** de `voix.py`, alimentée par ce que les éditeurs
  suppriment réellement, pas par une liste générique ;
- la **mesure du produit** : la part de paragraphes réécrits par livre. C'est
  le chiffre qui dit si l'outil marche. S'il ne baisse pas de livre en livre,
  le reste ne sert à rien.

**Succès** : la part de paragraphes réécrits baisse entre le livre N et le
livre N+1, toutes choses égales.

### 1.4 Le panel corrige, il ne fait plus que voter

Le panel à l'aveugle vote « faible » sur des passages. Aujourd'hui le verdict
remonte ; la suite est de régénérer. Régénérer une leçon entière pour trois
phrases faibles coûte cher et remet en jeu ce qui était bon.

**Livrable** : réécriture **ciblée** des seuls passages votés faibles, par un
modèle qui ne voit que le passage, son contexte immédiat et la consigne de
voix, puis re-mesure. Le reste de la leçon ne bouge pas.
**Succès** : nombre de passages votés faibles au second tour < au premier,
pour un coût par leçon < 0,10 $.

### 1.5 Trancher l'effort de réflexion par une lecture à l'aveugle

`comparer.py` a montré que l'effort `low` divise le coût par deux avec les
mêmes mesures mécaniques. Reste la prose. Deux éditeurs lisent `A.html` et
`B.html` sans savoir lequel est lequel, votent, on ouvre `cle.json`.

**Succès** : si `low` n'est pas distingué de `high` par les éditeurs, il
devient le défaut. C'est une décision à 7 $ par livre, qui se prend en une
heure.

---

## Axe 2 — Accélérer et alléger

### 2.1 Cache de prompt

Le brief a un long préfixe stable — consigne, voix maison, glossaire, leçon
modèle (1.2). Marquer ce préfixe `cache_control: ephemeral` le fait payer
une fois puis à 10 % du tarif pendant cinq minutes. Sur une série de 31
leçons enchaînées, c'est l'essentiel de l'entrée.

**Livrable** : `generate.py`, quatre lignes. **Succès** : coût d'entrée par
leçon divisé par 5 sur `couts.py`, mesuré, pas déduit.

### 2.2 L'API Batch pour les 30 leçons restantes

La première leçon reste synchrone : on la lit avant de payer les autres. Les
trente suivantes n'ont rien d'urgent — 52 minutes, personne n'attend devant.
Batch enlève 50 % et lève la contrainte du parallélisme.

**Livrable** : `generate.py --batch`, la page affiche « écrites cette nuit ».
**Succès** : un livre à moins de 4 $ toutes phases comprises.

### 2.3 Parallélisme par vagues

L'anti-répétition inter-leçons a besoin des leçons précédentes ; c'est ce qui
force la séquence. Compromis : les leçons d'une **même section** s'écrivent en
parallèle (elles ne se voient pas entre elles), les sections en séquence.
Dix vagues au lieu de trente-et-une étapes.

**Succès** : livre écrit en < 20 min en direct, sans hausse de reprise
inter-leçons mesurée par `repetition.py`.

### 2.4 Cache de mesures

`lesson_profile`, `glossary`, `style` se recalculent à chaque `run.sh` sur un
livre de référence qui ne change pas. Les mettre en cache par empreinte du
`book.json`. Gain : ~8 s sur 20 par compilation ; surtout, un `run.sh` sous
10 s rend la recompilation « instantanée » dans la page.

---

## Axe 3 — Simplifier

### 3.1 La vue d'édition est aussi la vue de lecture

Le 1.3 donne aux éditeurs *un* endroit : lire, réécrire, valider une leçon.
Pas de docx, pas de Drive, pas d'aller-retour. Le team manager voit, par
leçon, qui l'a lue et combien de paragraphes ont bougé.

### 3.2 Un tableau de bord par livre en cours

Arno mène deux livres en parallèle. Une ligne par livre : phase, prochain
geste, qui le porte, coût engagé, coût restant estimé. Rien de plus. Ce qui
existe par fiche projet, remonté d'un cran.

### 3.3 Prévenir au lieu de faire attendre

Une file vidée par un professeur, un livre assemblé, une écriture terminée :
un message (mail ou Slack) à qui a lancé. Aujourd'hui il faut revenir voir.
Un webhook et trois phrases.

### 3.4 Le livre d'essai

Un bouton « livre d'essai » : trois leçons, pas trente-et-une, toutes phases
comprises, en dix minutes et moins d'un dollar. C'est ce qu'on montre à un
nouveau professeur, et ce qu'on lance avant de s'engager sur une langue.

---

## Axe 4 — Ne jamais régresser

Chaque changement de prompt ou de modèle se note sur le même jeu de leçons,
sans dépenser (`comparer.py --simuler`, `check_lesson`, `voix.py`,
`repetition.py`). Un changement qui fait baisser une mesure ne passe pas, même
s'il « a l'air mieux ».

**Livrable** : `tests/test_qualite.py` — un corpus de leçons générées
archivées avec leurs scores, rejoué à chaque commit qui touche `generate.py`
ou `config/`.

---

## Ordre d'exécution

| # | Chantier | Effort | Dépense | Débloque |
|---|---|---|---|---|
| 1 | 1.1 `voix.py` — mesurer la voix sur le CN10 | 1 j | 0 $ | tout l'axe 1 se mesure |
| 2 | 2.1 cache de prompt | ½ j | 0 $ | 1.2 devient gratuit |
| 3 | 1.5 lecture à l'aveugle `low` vs `high` | 1 h d'éditeurs | 0 $ | −50 % par livre, tout de suite |
| 4 | 1.2 leçon modèle entière | 1 j | ~1 $ de tests | voix plus proche dès la génération |
| 5 | 1.3 vue d'édition + paires (avant, après) | 3 j | 0 $ | la seule boucle d'apprentissage réelle |
| 6 | 1.4 réécriture ciblée après le panel | 2 j | ~2 $ de tests | qualité sans régénération |
| 7 | 2.2 Batch pour les 30 leçons | 1 j | 0 $ | livre sous 4 $ |
| 8 | 2.3 vagues par section | 1 j | ~3 $ | livre en 20 min |
| 9 | 3.2, 3.3, 3.4 tableau de bord, alertes, essai | 2 j | 0 $ | l'équipe travaille sans toi |
| 10 | Axe 4 non-régression | 1 j | 0 $ | on peut changer le prompt sans peur |

Les trois premiers ne dépensent rien et se font en deux jours. Le cinquième est
le plus long et le plus important : c'est lui qui transforme l'outil, de « un
générateur qu'on corrige » en « un générateur qui apprend des corrections ».

---

## Ce qu'on ne fera pas

- **Fine-tuner un modèle.** Le volume (un livre de 31 leçons par langue) est
  trop faible pour l'emporter sur des exemples bien choisis dans le prompt, et
  chaque langue repartirait de zéro. Les paires (avant, après) dans le brief
  font le même travail, sans coût fixe, et restent lisibles.
- **Générer par lots de leçons.** Arno l'a constaté : le modèle condense. La
  leçon reste l'unité ; on parallélise, on ne regroupe pas.
- **Laisser un agent valider la langue.** Le professeur natif reste l'autorité
  (invariant 5). Les agents trient et réduisent, ils ne décident pas.
- **Une interface de plus.** Tout passe par les deux pages qui existent :
  dépôt pour le manager, console pour les relecteurs. La vue d'édition est un
  onglet de la console, pas une troisième page.
