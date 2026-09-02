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

# Les langues à alphabet latin ont leur propre mode : « mots ».
#
# Le moteur comptait le vocabulaire en caractères de l'écriture cible — ce qui
# n'a pas de sens quand la cible partage l'alphabet de la langue d'explication.
# En mode « mots » : la colonne d'écriture porte le mot espagnol, la colonne de
# prononciation porte une transcription phonétique (« OH-lah »), comme dans les
# livres publiés de la maison, et le vocabulaire se compte en entrées
# enseignées, pas en caractères. Le contrôle de langue ne peut pas prouver que
# le texte est de l'espagnol plutôt que de l'italien — il vérifie seulement
# qu'aucune écriture non latine ne s'y glisse, et le professeur natif porte le
# reste, comme pour toute langue sans vérificateur automatique.
NON_LATINES = KANA + HAN + HANGUL + "Ѐ-ӿͰ-Ͽ؀-ۿ֐-׿฀-๿ऀ-ॿ"

ECRITURES["latin"] = {
    "nom": "Latin alphabet (Spanish, Italian, French, German…)",
    "plage": "", "signature": "", "exclut": NON_LATINES,
    "mode": "mots",
    "romanisation": "phonetic respelling (OH-lah style)",
    "verification": None,
}


def choix():
    """Les écritures proposées, pour une liste déroulante."""
    return [{"cle": cle, "nom": e["nom"], "romanisation": e["romanisation"]}
            for cle, e in ECRITURES.items()]
