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
# Derrière le proxy de Render, le trafic arrive en HTTP avec X-Forwarded-Proto.
# Sans --forwarded-allow-ips, uvicorn n'accepte ces en-têtes que de 127.0.0.1
# et request.base_url reste en http:// : les liens renouvelés depuis la page
# sortaient en http. Le conteneur n'est joignable que par ce proxy.
SERVEUR="uvicorn app:app --app-dir server --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips=*"

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
