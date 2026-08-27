#!/usr/bin/env bash
# Installe les dépendances et les polices nécessaires au rendu.
set -e
pip install -r requirements.txt

mkdir -p fonts && cd fonts
base="https://github.com/google/fonts/raw/main/ofl"
[ -f Archivo.ttf ]        || curl -sL "$base/archivo/Archivo%5Bwdth%2Cwght%5D.ttf" -o Archivo.ttf
[ -f SourceSerif4.ttf ]   || curl -sL "$base/sourceserif4/SourceSerif4%5Bopsz%2Cwght%5D.ttf" -o SourceSerif4.ttf
[ -f SourceSerif4-Italic.ttf ] || curl -sL "$base/sourceserif4/SourceSerif4-Italic%5Bopsz%2Cwght%5D.ttf" -o SourceSerif4-Italic.ttf
[ -f NotoSansSC.ttf ]     || curl -sL "$base/notosanssc/NotoSansSC%5Bwght%5D.ttf" -o NotoSansSC.ttf
cd ..

command -v typst >/dev/null || {
  echo "Typst manquant : https://github.com/typst/typst/releases"
  exit 1
}
echo "prêt — lancer ./run.sh input/<manuscrit>.docx"
