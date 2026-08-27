# Workbook Engine — Roadmap

Outil de production de workbooks de langues : de l'idée de livre au PDF prêt pour l'impression, avec les humains là où ils apportent vraiment quelque chose.

---

## 1. Le problème actuel

Un livre = ~6 mois et des centaines d'heures.

| Étape | Aujourd'hui | Le coût réel |
|---|---|---|
| Plan du livre | Fait à la main | Densité non cadrée : les leçons du CN10 vont de 455 à 1 486 mots |
| Génération | ChatGPT, leçon par leçon, piloté par un humain | 2 éditeurs × ~31 leçons × 2 projets en parallèle |
| Qualité de sortie | ~50 % exploitable | Les éditeurs réécrivent presque tout : ton robotique, formulations répétées |
| Relecture prof | Lecture linéaire du manuscrit entier | 244 pages à lire pour trouver quelques dizaines d'erreurs |
| Answer keys | Copiées-collées à la fin du livre | Erreurs qui survivent à toute la chaîne (voir §2) |
| Formatting | Remontage manuel sous InDesign | Un poste entier, refait à chaque version |

**Le goulot n'est pas la génération, c'est la réécriture.** Deux personnes qui réécrivent au lieu de valider, c'est là que partent les mois.

---

## 2. Ce que l'outil fait

Trois couches, plus une boucle humaine par-dessus.

### Couche 1 — Spécificités de la langue

Un fichier de configuration par langue, écrit une fois, qui pilote tout le reste :

- **Système d'écriture** : y a-t-il des caractères à enseigner, en combien de leçons, avec quels exercices dédiés, et à quel rythme la romanisation s'efface.
  *Coréen* : hangul en quelques leçons, romanisation retirée progressivement.
  *Japonais* : kana puis kanji, furigana maintenu jusqu'à la fin.
  *Portugais* : aucune couche d'écriture, mais genre, conjugaison, ser/estar, et le choix européen/brésilien.
- **Axes pédagogiques propres** : tons (chinois), niveaux de politesse (japonais, coréen), genre et accord (langues latines).
- **Progression de référence** : HSK, JLPT, TOPIK, CEFR.
- **Champs de contenu** : hanzi/pinyin, kanji/furigana/rōmaji, hangul/romanisation — le schéma des blocs s'adapte.
- **Types d'exercices activés** : le tracé de caractères existe pour le coréen, pas pour le portugais.

Cette config génère le plan du livre, puis contraint chaque leçon.

### Couche 2 — Génération du contenu

Génération leçon par leçon (grouper dégrade la qualité — c'est le bon choix), mais **pilotée par un script, pas par un humain**. C'est ce qui fait disparaître le coût de volume.

Chaque leçon est générée avec :

- son **quota** issu du plan : nombre de mots, de tableaux, de dialogues, d'exercices, de mots de vocabulaire nouveaux ;
- le **glossaire maître** : tout ce qui a déjà été enseigné, pour que la difficulté soit réellement croissante et vérifiable ;
- les **formulations déjà utilisées** dans le livre, pour éliminer la répétitivité à la source ;
- des **exemples de style tirés des livres validés** : le CN10 final est passé par éditeurs *et* prof, c'est la voix maison approuvée. Aujourd'hui ce travail de réécriture est jeté à chaque titre ; ici il devient l'entrée du modèle.

Sortie : du contenu structuré (pas de la prose libre), avec **chaque exercice typé** et portant sa propre réponse.

Catalogue d'exercices (7 types réels identifiés dans le CN10, derrière 18 intitulés différents) :
`fill_blank` · `matching` · `mcq` · `true_false` · `translation` · `sentence_building` · `comprehension` · `mini_challenge`

### Couche 3 — Formatting

Le formatting n'est pas généré, il est **appliqué** — donc sans erreur possible par construction.

- Brief graphique codé une fois dans un template.
- Compilation du livre entier en une commande : TOC automatique avec numéros de page, footers par section, pages spéciales, format 6×9 avec gutter, prêt KDP.
- **Answer keys générées depuis les exercices**, jamais recopiées.

### Boucle humaine — des files d'attente, pas un manuscrit

Personne ne relit le livre en entier.

- **Éditeur** : reçoit les blocs signalés (répétitions détectées, leçon hors quota, ton robotique). Corrige dans la source structurée — la correction ne se perd jamais au reformatage.
- **Prof natif** : reçoit des lots homogènes (paires écriture/prononciation douteuses, puis vocabulaire nouveau, puis répliques de dialogue). Relire 464 items similaires est bien plus rapide que lire un livre.
- **Team manager** : tableau de bord, attribution des leçons, approbation finale avant compilation.
- **Capitalisation** : les corrections du prof enrichissent le glossaire, les réécritures de l'éditeur enrichissent les exemples de style. Chaque livre part meilleur que le précédent.

### Couche de relecture — agents en cascade

Objectif : que le contenu arrive aux humains **déjà nettoyé**, et que ce qui remonte soit uniquement ce qui demande un vrai jugement.

**Règle n°1 : le code passe avant les agents.** Tout ce qui est vérifiable de façon déterministe ne doit jamais être confié à une IA — prononciation, quotas, vocabulaire hors glossaire, bijection des matching, cohérence des answer keys. C'est plus fiable, gratuit, et reproductible. Les agents ne traitent que ce qui relève du jugement : naturel de la langue, ton, clarté pédagogique, répétitivité.

**Relecture à l'aveugle.** Chaque relecteur reçoit le contenu **sans provenance** : il ne sait pas s'il relit de l'IA, un éditeur humain, ou un autre agent, et il ne voit pas les commentaires des relecteurs précédents. C'est ce qui évite deux biais majeurs : l'indulgence envers du texte présenté comme déjà validé, et l'alignement moutonnier sur l'avis d'un autre relecteur.

**Critique forcée, jamais « est-ce que c'est bon ? »** À cette question un modèle répond oui. Les consignes sont à quota et à choix forcé : « identifie les 3 phrases les plus faibles », « liste les tournures qu'un locuteur natif n'emploierait jamais », « repère ce qui est déjà dit ailleurs dans le livre ». On obtient des critiques exploitables au lieu d'une approbation polie.

**Relecteurs indépendants et modèles différents.** Plusieurs relectures en parallèle, sans se voir, et si possible sur des modèles distincts de celui qui a généré : un modèle qui se relit lui-même partage ses propres angles morts, les erreurs sont corrélées. Le tri se fait sur l'accord :

| Résultat | Action |
|---|---|
| Tous d'accord : bon | Passe |
| Tous d'accord : problème | Réécriture automatique, puis nouvelle relecture |
| Désaccord | Monte dans la file humaine — c'est là qu'un jugement est vraiment utile |

**Les agents signalent, ils ne réécrivent pas en silence.** Chaque remarque porte sa localisation et sa raison. La réécriture est une étape séparée et tracée — sans quoi on perd l'historique et on risque d'écraser une correction du professeur.

**Le professeur natif reste l'autorité finale sur la langue cible.** Les agents trient et réduisent le volume ; ils ne valident jamais une langue à sa place.

**Comment on saura que cette couche marche** : on la fait tourner sur le CN10, dont les erreurs sont désormais connues (les 15 paires signalées, les dérives d'answer keys). Un système de relecture se mesure sur des erreurs connues, il ne se croit pas sur parole.

---

## 3. Preuves déjà obtenues (manuscrit CN10)

Le pipeline a tourné sur le manuscrit réel, du docx au PDF :

- **242 pages** formatées automatiquement, en une commande, au design du brief.
- **1 seul bloc mal classé** sur tout le livre — malgré un manuscrit irrégulier (8 sections sur 10 hors style Heading, TOC parasite, 163 mini-titres en simple gras).
- **1 921 paires hanzi ↔ pinyin vérifiées par code**, dont 15 signalées pour relecture. Avec de vraies erreurs dedans (你的老师呢？ traduit « Nǐ ne? », un xièxie présent dans le pinyin et absent du chinois).
- **Answer keys : dérive confirmée** dans le livre publié — « EVERY DAY » devenu « EVERYDAY », « CURRENCY » devenu « MONEY », 3 leçons sur 36 non retrouvables par leur nom. Passé au travers des éditeurs *et* du prof.
- **Profil d'une leçon type extrait automatiquement** : 828 mots, 2 sections, 13 tableaux, 3 dialogues, 3 exercices, 38 mots de vocabulaire nouveaux — le cahier des charges déduit des livres existants plutôt que deviné.

---

## 4. Développement — les phases

Principe : **le pipeline avant l'interface.** L'interface se refait vite, le pipeline doit être juste. Ne pas construire l'app complète avant que le moteur soit éprouvé sur 2 ou 3 livres.

### Phase 0 — Service manuel *(fait)*

Aucune interface. Arno envoie un docx, il reçoit PDF + rapport de validation.

**Livrables** : convertisseur docx → structure, validateur automatique, template du livre.
**Validé si** : le PDF est présentable tel quel et le rapport trouve de vraies erreurs. ✅

### Phase 1 — Exercices typés et answer keys

Le catalogue d'exercices et la génération automatique des réponses.

**Livrables** : les 8 types d'exercices, rendu de chacun, answer keys générées, vérifications automatiques (bijection des matching, réponse présente parmi les options, vocabulaire des trous déjà enseigné).
**Validé si** : les 82 exercices du CN10 sont rendus correctement et l'answer key régénérée fait apparaître seule les divergences du livre publié.

### Phase 2 — App minimale (un écran)

Une page par projet : upload du manuscrit → rapport de validation → téléchargement du PDF.

**Livrables** : web app hébergée, un lien par projet, dépôt automatique du PDF dans le dossier Drive du projet.
**Validé si** : Arno et son team manager compilent un livre sans passer par toi.
*Pas de comptes, pas de permissions — 6 personnes en interne, un lien suffit.*

### Phase 3 — Files de review par rôle

Le routage du travail humain, la vraie valeur du système.

**Livrables** : détection des blocs à réviser, file éditeur, file prof (par lots, sans compte, utilisable sans formation — les profs changent à chaque langue), attribution des leçons avec propriétaire et état, tableau de bord manager.
**Validé si** : un prof externe traite sa file sans qu'on lui explique quoi que ce soit, et deux éditeurs travaillent sur le même projet sans se marcher dessus.

### Phase 3bis — Relecture multi-agents

À construire juste après les files humaines : les agents alimentent ces files, ils n'ont d'intérêt que si le routage existe déjà.

**Livrables** : relecteurs à l'aveugle sur consignes à quota, exécution parallèle sur modèles distincts, tri par accord/désaccord, remarques localisées et tracées, réécriture en étape séparée.
**Validé si** : lancé sur le CN10, le système retrouve les erreurs déjà identifiées manuellement, et le volume qui remonte aux humains diminue sans que des erreurs connues passent au travers.

### Phase 4 — Couche génération

Le plan du livre et la génération leçon par leçon automatisée.

**Livrables** : format de config de langue, générateur de plan, boucle de génération avec glossaire et anti-répétition, extraction du style depuis les livres validés.
**Validé si** : une leçon régénérée est jugée aussi bonne que la version humaine existante — mesuré par comparaison directe avec le CN10 final.

### Phase 5 — Passage à l'échelle multi-langues

**Livrables** : config coréen ou japonais complète, gestion du système d'écriture et de la romanisation dégressive, exercices spécifiques (tracé de caractères).
**Validé si** : un nouveau titre démarre en écrivant une config, sans toucher au moteur.

---

## 5. Ce que ça change

| | Avant | Après |
|---|---|---|
| Délai par livre | ~6 mois | quelques semaines |
| Rôle des éditeurs | réécrivent tout | valident et arbitrent |
| Relecture prof | 244 pages | quelques dizaines d'items ciblés |
| Formatting | poste manuel InDesign | une commande |
| Answer keys | source d'erreurs récurrente | impossible à faire diverger |
| Nouveau titre | tout recommencer | écrire une config |
| Nouvelle version | remontage complet | recompilation en quelques secondes |

Le gain économique n'est pas le formatting : c'est que **2 éditeurs qui valident au lieu de réécrire doublent le débit de la boîte sans embauche**.
