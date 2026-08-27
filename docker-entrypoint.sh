#!/bin/sh
# Le disque persistant est monté à l'exécution : son propriétaire n'est pas
# connu au moment de construire l'image. C'est la cause la plus fréquente d'un
# premier déploiement qui échoue. On l'ajuste ici, puis on abandonne les
# privilèges — le serveur ne tourne jamais en root.
set -e
DATA="${WB_DATA:-/data}"
mkdir -p "$DATA" 2>/dev/null || true      # l'erreur utile est plus bas

if [ "$(id -u)" = "0" ]; then
  chown -R workbook "$DATA" 2>/dev/null || true
  exec su workbook -s /bin/sh -c "exec $*"
fi

if [ ! -w "$DATA" ]; then
  echo "erreur : $DATA n'est pas accessible en écriture pour $(id -un)." >&2
  echo "Vérifier le montage du disque persistant (voir docs/DEPLOIEMENT.md)." >&2
  exit 1
fi
exec "$@"
