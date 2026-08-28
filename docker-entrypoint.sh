#!/bin/sh
# Le disque persistant est monté à l'exécution : son propriétaire n'est pas
# connu au moment de construire l'image. C'est la cause la plus fréquente d'un
# premier déploiement qui échoue. On l'ajuste ici, puis on abandonne les
# privilèges — le serveur ne tourne jamais en root.
#
# La commande est écrite en toutes lettres plutôt que reprise de CMD : passer
# des arguments à `su -c` à travers "$*" écrase les guillemets, et
# `sh -c "uvicorn app:app --host …"` devenait `uvicorn` sans aucun argument.
set -e
DATA="${WB_DATA:-/data}"
PORT="${PORT:-8000}"
SERVEUR="uvicorn app:app --app-dir server --host 0.0.0.0 --port $PORT"

mkdir -p "$DATA" 2>/dev/null || true

if [ "$(id -u)" = "0" ]; then
  chown -R workbook "$DATA" 2>/dev/null || true
  exec su workbook -s /bin/sh -c "exec $SERVEUR"
fi

if [ ! -w "$DATA" ]; then
  echo "erreur : $DATA n'est pas accessible en écriture pour $(id -un)." >&2
  echo "Vérifier le montage du disque persistant (voir docs/DEPLOIEMENT.md)." >&2
  exit 1
fi
exec $SERVEUR
