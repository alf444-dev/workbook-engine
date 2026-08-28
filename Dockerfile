# Workbook Engine — image de production.
#
# Le pipeline a besoin de Python et du binaire Typst, plus les polices : un
# hébergement statique ne suffit pas. Tout est figé ici pour que le livre
# compilé sur le serveur soit celui compilé sur un poste de travail.

ARG TYPST_VERSION=v0.15.1

# ---------------------------------------------------------------- outils
FROM debian:bookworm-slim AS outils
ARG TYPST_VERSION
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates xz-utils \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://github.com/typst/typst/releases/download/${TYPST_VERSION}/typst-x86_64-unknown-linux-musl.tar.xz" \
      -o /tmp/typst.tar.xz \
 && tar xJf /tmp/typst.tar.xz -C /tmp \
 && mv /tmp/typst-x86_64-unknown-linux-musl/typst /usr/local/bin/typst \
 && typst --version

# Les mêmes polices que setup.sh — substituts libres d'Archivo, Source Serif 4
# et Noto Sans SC. Une police manquante ne casse pas la compilation, elle
# change la mise en page en silence : elles sont donc dans l'image.
WORKDIR /polices
RUN base="https://github.com/google/fonts/raw/main/ofl" \
 && curl -fsSL "$base/archivo/Archivo%5Bwdth%2Cwght%5D.ttf"          -o Archivo.ttf \
 && curl -fsSL "$base/sourceserif4/SourceSerif4%5Bopsz%2Cwght%5D.ttf" -o SourceSerif4.ttf \
 && curl -fsSL "$base/sourceserif4/SourceSerif4-Italic%5Bopsz%2Cwght%5D.ttf" -o SourceSerif4-Italic.ttf \
 && curl -fsSL "$base/notosanssc/NotoSansSC%5Bwght%5D.ttf"            -o NotoSansSC.ttf

# ---------------------------------------------------------------- image finale
FROM python:3.12-slim

COPY --from=outils /usr/local/bin/typst /usr/local/bin/typst

WORKDIR /app
# Dépendances d'abord : cette couche ne change qu'avec les requirements.
COPY requirements.txt ./requirements.txt
COPY server/requirements.txt ./server-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r server-requirements.txt

COPY pipeline/ ./pipeline/
COPY config/ ./config/
COPY templates/ ./templates/
COPY webapp/ ./webapp/
COPY server/ ./server/
COPY run.sh ./
COPY --from=outils /polices/ ./fonts/
RUN chmod +x run.sh

# Le serveur écrit dans /data (disque persistant) et jamais dans /app.
ENV WB_DATA=/data \
    WB_HTTPS=1 \
    PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 workbook && mkdir -p /data && chown workbook /data
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Démarre en root le temps d'ajuster le disque monté, puis abandonne les
# privilèges : voir docker-entrypoint.sh.
EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
