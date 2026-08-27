# Mettre l'outil en ligne

Le pipeline est en Python et le rendu appelle le binaire Typst : un hébergement
statique ne suffit pas. Il faut une machine qui exécute l'image Docker et un
disque qui survit aux redéploiements.

## Pourquoi Render

Le besoin réel : Python et Typst, un disque persistant pour les manuscrits et
les décisions, une dizaine d'utilisateurs, un trafic négligeable — et
**personne dans l'équipe pour administrer une machine**. Render fait tourner le
`Dockerfile` tel quel, monte un disque, gère le certificat et redéploie sur
`git push`.

Le disque persistant impose une **instance unique**. C'est une contrainte, et
ici c'est ce qu'on veut : elle rend SQLite suffisant et supprime toute question
de coordination entre serveurs.

Ordre de grandeur : plan Starter 7 $/mois + disque 5 Go à ~1,25 $/mois.

Si un jour il faut du cron, des agents de relecture ou plus de puissance, une VM
(Hetzner, ~4 €/mois) reprend la même image Docker sans rien réécrire.

## Déployer

1. Pousser le dépôt sur GitHub (privé).
2. Sur Render : **New → Blueprint**, pointer sur le dépôt. `render.yaml` décrit
   le service, le disque et les variables.
3. Attendre la première construction (elle télécharge Typst et les polices).
4. Dans **Environment**, relever la valeur générée de `WB_ADMIN_TOKEN`.

Le lien de dépôt à donner au team manager est :

```
https://<votre-service>.onrender.com/a/<WB_ADMIN_TOKEN>
```

C'est le seul lien à retenir : tout le reste (projets, liens de relecture) se
crée depuis cette page.

Le conteneur démarre en root le temps d'ajuster le propriétaire du disque monté
(`docker-entrypoint.sh`), puis abandonne ses privilèges : le serveur ne tourne
jamais en root. Si le disque reste inaccessible, le démarrage s'arrête sur un
message explicite plutôt que sur une trace Python.

## Variables d'environnement

| Variable | Rôle |
|---|---|
| `WB_DATA` | racine des données. `/data` sur Render, le disque persistant. |
| `WB_ADMIN_TOKEN` | le lien de dépôt. Sans elle, un jeton est tiré au premier démarrage et gardé en base. |
| `WB_HTTPS` | `1` en production : les cookies ne partent qu'en HTTPS. |
| `WB_DRIVE_CREDENTIALS` | le JSON du compte de service Google. Absente, le dépôt Drive est simplement inactif. |
| `WB_DRIVE_BACKUP_FOLDER` | dossier Drive où déposer les sauvegardes. |
| `ANTHROPIC_API_KEY` | génération des leçons. Absente, seul le pipeline docx → PDF fonctionne. |

## La clé de génération

À créer sur **[platform.claude.com/settings/keys](https://platform.claude.com/settings/keys)**
(Settings → API keys), de préférence dans un **workspace dédié au projet**
(`/settings/workspaces`) pour suivre la consommation livre par livre.

L'**expiration se choisit à la création et ne se modifie plus** : une clé expirée
renvoie `401` et ne se réactive pas. Pour un serveur qui tourne en continu,
prendre *Never* et ne laisser vivre la clé que dans les variables
d'environnement de Render.

La clé n'est jamais dans le dépôt : `sync: false` dans `render.yaml` signifie
que Render la demande une fois dans son interface et ne la versionne pas.

## Déposer dans le Drive de l'équipe

On ne remplace pas le Drive, on s'y ajoute : après chaque compilation, le livre
et les rapports sont déposés dans le dossier du projet.

1. Dans la console Google Cloud : créer un projet, activer **Google Drive API**,
   créer un **compte de service**, puis une clé JSON.
2. Coller le contenu du JSON dans `WB_DRIVE_CREDENTIALS` sur Render.
3. Dans le Drive, **partager le dossier du projet avec l'adresse e-mail du
   compte de service**, en accès *Éditeur*.
4. Sur la page de dépôt, coller le lien du dossier dans le champ **Dossier
   Drive** du projet.

La portée demandée est `drive.file` : l'outil ne voit que les fichiers qu'il a
lui-même déposés, rien d'autre du Drive. Un fichier du même nom est **remplacé**,
jamais dupliqué — sinon le dossier se remplirait d'un `book.pdf` par
compilation.

Personne n'a de compte à créer : ni les éditeurs, ni les professeurs externes.

## Sauvegarde

`data/` contient les manuscrits déposés et toutes les décisions des relecteurs.
Tout le reste — livre, rapports, files — se régénère.

```bash
python3 server/backup.py                      # archive dans data/backups/
python3 server/backup.py --drive <dossier>    # et dépôt dans le Drive
```

La base est copiée par l'API de sauvegarde de SQLite, pas par `cp` : en mode WAL,
copier le fichier pendant qu'un relecteur enregistre donnerait une archive
incohérente. Les 14 dernières archives sont gardées.

À mettre en cron quotidien (`0 3 * * *`) — sur Render, un *Cron Job* pointant
sur la même image ; sur une VM, une ligne de crontab.

**Restaurer** : décompresser l'archive dans `WB_DATA`, remettre `workbooks.db`
et les `projects/*/input/`, puis recompiler chaque projet depuis la page de
dépôt. Les décisions sont dans la base et seront rejouées.

## Ce qui n'a pas été vérifié

- **L'image Docker n'a pas été construite** : Docker n'était pas disponible sur
  le poste où elle a été écrite. Les mêmes étapes (téléchargement de Typst,
  polices, dépendances) ont été jouées à la main sous macOS et fonctionnent, mais
  la première construction demandera peut-être un ajustement.
- **Le dépôt Drive n'a pas été testé contre le vrai Google** : aucun compte de
  service n'était disponible. La logique est testée contre une doublure de l'API
  (`tests/test_livraison.py`) ; le premier dépôt réel est à surveiller.
