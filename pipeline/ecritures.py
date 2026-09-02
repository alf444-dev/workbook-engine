#!/usr/bin/env python3
"""Les systèmes d'écriture connus, pour qu'ajouter une langue ne demande pas
de connaître Unicode.

Le team manager d'Arno doit pouvoir lancer un titre en coréen sans savoir que
le hangul occupe le bloc U+AC00–U+D7A3. Il choisit une écriture dans cette
table ; les plages viennent d'ici.

Trois champs par écriture, et le troisième est le plus important :

- `plage` — ce qui compte comme « écriture cible » : sert à mesurer le
  vocabulaire, à repérer les caractères non enseignés.
- `signature` — ce qu'un texte réellement écrit dans cette langue contient et
  qu'un texte d'une langue voisine ne contient pas. Les kanji japonais et les
  sinogrammes chinois partagent leur bloc : sans les kana comme signature, une
  leçon chinoise passe pour du japonais. C'est arrivé, sur 225 pages.
- `exclut` — ce qu'un texte de cette langue ne peut pas contenir.

Les langues à écriture latine ne sont pas ici, et ce n'est pas un oubli : voir
`LATINES` en bas de fichier.
"""

KANA = "぀-ゟ゠-ヿ"
HAN = "一-鿿"
HANGUL = "가-힣ᄀ-ᇿ"

ECRITURES = {
    "han-simplifie": {
        "nom": "Chinese characters (simplified)",
        "plage": HAN, "signature": "", "exclut": KANA,
        "romanisation": "Hanyu Pinyin",
        "verification": "pypinyin",
    },
    "han-traditionnel": {
        "nom": "Chinese characters (traditional)",
        "plage": HAN, "signature": "", "exclut": KANA,
        "romanisation": "Hanyu Pinyin",
        "verification": "pypinyin",
    },
    "kana-kanji": {
        "nom": "Japanese (hiragana, katakana, kanji)",
        "plage": KANA + HAN, "signature": KANA, "exclut": HANGUL,
        "romanisation": "Hepburn rōmaji",
        "verification": None,
    },
    "hangul": {
        "nom": "Korean (hangul)",
        "plage": HANGUL, "signature": HANGUL, "exclut": KANA,
        "romanisation": "Revised Romanization",
        "verification": None,
    },
    "cyrillique": {
        "nom": "Cyrillic",
        "plage": "Ѐ-ӿ", "signature": "Ѐ-ӿ", "exclut": "",
        "romanisation": "scientific transliteration",
        "verification": None,
    },
    "grec": {
        "nom": "Greek",
        "plage": "Ͱ-Ͽ", "signature": "Ͱ-Ͽ", "exclut": "",
        "romanisation": "ISO 843 transliteration",
        "verification": None,
    },
    "arabe": {
        "nom": "Arabic",
        "plage": "؀-ۿ", "signature": "؀-ۿ", "exclut": "",
        "romanisation": "ALA-LC romanization",
        "verification": None,
    },
    "hebreu": {
        "nom": "Hebrew",
        "plage": "֐-׿", "signature": "֐-׿", "exclut": "",
        "romanisation": "ALA-LC romanization",
        "verification": None,
    },
    "thai": {
        "nom": "Thai",
        "plage": "฀-๿", "signature": "฀-๿", "exclut": "",
        "romanisation": "RTGS",
        "verification": None,
    },
    "devanagari": {
        "nom": "Devanagari",
        "plage": "ऀ-ॿ", "signature": "ऀ-ॿ", "exclut": "",
        "romanisation": "IAST",
        "verification": None,
    },
}

# Pourquoi l'espagnol ou l'italien n'y sont pas.
#
# Tout le moteur repose sur une distinction entre l'écriture enseignée et la
# langue d'explication : une colonne pour l'écriture cible, une pour sa
# prononciation, et le comptage du vocabulaire nouveau se fait sur les
# caractères de l'écriture cible. Pour une langue à alphabet latin, cette
# distinction n'existe pas — la prose anglaise et les mots espagnols occupent le
# même alphabet, et tout ce qui compte des « caractères de la langue cible »
# compterait aussi l'anglais.
#
# Ce n'est pas une limite de cette table, c'est une limite du moteur. Ajouter
# l'espagnol demande de décider ce que devient la colonne de prononciation et
# comment se mesure le vocabulaire nouveau. Le dire ici plutôt que de laisser
# quelqu'un créer un titre espagnol qui sortira faux.
LATINES = ("espagnol, italien, portugais, allemand, néerlandais, et toute autre "
           "langue à alphabet latin")


def choix():
    """Les écritures proposées, pour une liste déroulante."""
    return [{"cle": cle, "nom": e["nom"], "romanisation": e["romanisation"]}
            for cle, e in ECRITURES.items()]
