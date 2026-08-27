# Tâche suivante — déposer un manuscrit depuis le site

## Le besoin

Aujourd'hui le pipeline se lance en ligne de commande et la console de relecture
est un fichier statique regénéré à la main. Arno et son team manager doivent
pouvoir déposer un `.docx` sur une page et récupérer le PDF et les files de
relecture, sans passer par un développeur.

## Ce qui est demandé

Une petite application web, un écran par projet :

1. **Dépôt** — glisser un `.docx`, voir la progression des étapes du pipeline.
2. **Résultat** — télécharger le PDF, consulter les trois rapports.
3. **Relecture** — la console existante, alimentée par le projet déposé.
4. **Décisions** — les relecteurs enregistrent leurs choix côté serveur au lieu
   d'exporter un fichier, pour que plusieurs personnes travaillent en parallèle
   sans se marcher dessus.

## Contraintes techniques

- Le pipeline est en Python et le rendu utilise le binaire `typst` : **un
  hébergement statique ne suffit pas**. Netlify convient pour la console seule,
  pas pour l'exécution. Prévoir un petit serveur (Render, Fly, Railway, ou une
  VM) capable de lancer Python et Typst.
- La compilation d'un livre de 240 pages prend quelques secondes ; un traitement
  synchrone avec barre de progression suffit, pas besoin de file de jobs.
- 6 personnes en interne, des professeurs externes qui changent à chaque langue :
  **pas de système de comptes**. Un lien par projet et par rôle suffit.
- Les manuscrits ne sont pas publics : les liens doivent être non devinables et
  le site non indexable.

## Découpage suggéré

1. Backend minimal : `POST /projects` (upload docx) → lance le pipeline → renvoie
   un identifiant de projet ; `GET /projects/:id` → état, rapports, PDF.
2. Stockage des décisions : `POST /projects/:id/decisions`, relu par la console.
3. Application des décisions à `content/book.json`, puis recompilation — c'est ce
   qui ferme la boucle : une correction de professeur se retrouve dans le PDF
   sans intervention manuelle.
4. Page projet : dépôt, état, rapports, liens vers les files de relecture.

## Critère de validation

Le team manager dépose un manuscrit, obtient le PDF, envoie un lien à un
professeur qui n'a jamais vu l'outil ; celui-ci traite sa file ; le manager
recompile et les corrections sont dans le livre. Sans ligne de commande.

## Attention

- Ne pas casser le fonctionnement en ligne de commande : `./run.sh` doit
  continuer à marcher, le serveur l'appelle.
- Ne pas remplacer le Google Drive de l'équipe. Idéalement, déposer le PDF
  compilé dans le dossier du projet.
- Vérifier le taux de faux positifs sur le CN10 entier avant d'ajouter des
  contrôles.
