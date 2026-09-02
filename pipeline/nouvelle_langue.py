#!/usr/bin/env python3
"""Crée la config d'une langue nouvelle, sans toucher au code.

Une config se divise en deux moitiés, et une seule est à fournir :

- **Le gabarit** — structure du livre, quotas par leçon, courbe du vocabulaire,
  répartition des exercices. Mesuré sur le livre validé, identique quelle que
  soit la langue : c'est tout le principe, « même mise en page, même équilibre,
  même courbe de difficulté ». On le recopie depuis la config de référence, avec
  ses marqueurs de provenance.
- **La langue** — son écriture, sa romanisation, son nom. Fourni ici.

Ce que la personne qui lance un titre n'a pas à savoir : la plage Unicode de
l'écriture. Elle choisit dans `pipeline/ecritures.py`.

    python3 pipeline/nouvelle_langue.py --nom Korean --code ko --ecriture hangul

Rien de ce qui est écrit ici n'est mesuré : les champs propres à la langue
portent la provenance « éditorial », c'est-à-dire « à confronter au professeur
natif ». Le gabarit, lui, garde la sienne.
"""
import argparse, json, re, sys, unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ecritures import ECRITURES, LATINES                         # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
CONFIGS = RACINE / "config"

# Ce qui vient du livre de référence et ne dépend pas de la langue.
DU_GABARIT = ("structure_du_livre", "quotas_lecon", "courbe_du_vocabulaire",
              "types_exercices")
# Ce qui vient de l'éditeur et vaut pour tous ses titres.
DE_LA_MAISON = ("public", "langue_d_explication", "audience", "public_affiche")


def ardoise(nom):
    """Un nom de fichier sûr, tiré du nom anglais de la langue."""
    plat = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", plat.lower()).strip("_") or "langue"


def construire(nom_anglais, code, ecriture, reference, romanisation=None,
               public=None):
    """La config complète. Rend (dictionnaire, avertissements)."""
    if ecriture not in ECRITURES:
        raise ValueError(f"écriture inconnue : {ecriture}. "
                         f"Choix : {', '.join(sorted(ECRITURES))}")
    e = ECRITURES[ecriture]
    avertissements = []

    conf = {
        "_lisez_moi": (
            f"Config de {nom_anglais}, créée depuis le gabarit de "
            f"{reference.get('nom_anglais') or reference.get('langue')}. "
            "Les blocs « gabarit » sont mesurés sur le livre validé et ne "
            "dépendent pas de la langue. Les blocs « éditorial » sont des "
            "hypothèses : à confronter au professeur natif avant de générer "
            "un livre entier."),
        "langue": nom_anglais.lower(),
        "code": code,
        "nom_anglais": nom_anglais,
        "nom_affiche": nom_anglais,
        "ecriture": {
            "_provenance": "éditorial",
            "systeme": e["nom"],
            "romanisation": romanisation or e["romanisation"],
            "romanisation_degressive": False,
            "plage_unicode": e["plage"],
            "signature": e["signature"],
            "exclut": e["exclut"],
            "verification_prononciation": e["verification"],
            "_signature_note": (
                "Ce qu'un texte de cette langue contient et qu'un texte d'une "
                "langue voisine ne contient pas. Sans elle, une leçon écrite "
                "dans la mauvaise langue passerait le contrôle."),
        },
        "progression": {
            "_provenance": "éditorial",
            "_a_valider_avec": "le professeur natif",
            "reference": None,
            "_note": ("Aucun référentiel de niveaux n'est déclaré : le plan "
                      "reprend la courbe du livre de référence."),
        },
        "axes_pedagogiques": {
            "_provenance": "éditorial",
            "_a_valider_avec": "le professeur natif",
            "_note": ("À remplir avec le professeur : ce qui structure "
                      "l'apprentissage de cette langue en particulier."),
        },
    }

    origine = reference.get("nom_anglais") or reference.get("langue") or "la référence"
    for cle in DU_GABARIT:
        if cle not in reference:
            avertissements.append(f"la référence n'a pas de bloc « {cle} »")
            continue
        bloc = json.loads(json.dumps(reference[cle]))
        # La provenance doit rester vraie. Dans la config d'origine ces valeurs
        # sont « mesurées » — sur ce livre-là. Recopiées ici, elles ne mesurent
        # plus rien : elles servent de gabarit. Garder le mot « mesuré »
        # ferait passer une hypothèse pour un fait, ce que les marqueurs de
        # provenance existent précisément pour empêcher.
        if isinstance(bloc, dict):
            avant = bloc.get("_provenance", "")
            bloc["_provenance"] = f"gabarit {origine}"
            if avant and not avant.startswith("gabarit"):
                bloc["_provenance_origine"] = (
                    f"« {avant} » dans la config de {origine} — mesuré sur ce "
                    f"livre-là, pas sur celui-ci")
        conf[cle] = bloc
    for cle in DE_LA_MAISON:
        if cle in reference:
            conf[cle] = reference[cle]
    if public:
        conf["public"] = public

    if not e["signature"] and not e["exclut"]:
        avertissements.append(
            "cette écriture n'a ni signature ni exclusion : une leçon écrite "
            "dans une langue voisine ne serait pas détectée")
    if e["verification"] is None:
        avertissements.append(
            "aucun contrôle automatique de prononciation pour cette écriture : "
            "la file du professeur natif portera seule cette vérification")
    return conf, avertissements


def ecrire(conf, chemin):
    chemin.write_text(json.dumps(conf, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return chemin


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nom", required=True, help="nom anglais : Korean, Thai…")
    ap.add_argument("--code", required=True, help="code ISO : ko, th…")
    ap.add_argument("--ecriture", required=True,
                    choices=sorted(ECRITURES),
                    help="système d'écriture, voir pipeline/ecritures.py")
    ap.add_argument("--romanisation", default=None)
    ap.add_argument("--reference", default="chinese",
                    help="config dont on reprend le gabarit")
    ap.add_argument("--dossier", default=None,
                    help="où écrire ; par défaut config/ du dépôt. Le serveur y "
                         "met le disque persistant, sinon la langue disparaît "
                         "au déploiement suivant")
    ap.add_argument("--forcer", action="store_true",
                    help="écraser une config existante")
    a = ap.parse_args()

    source = CONFIGS / f"{a.reference}.json"
    if not source.exists():
        sys.exit(f"config de référence introuvable : {source}")
    reference = json.loads(source.read_text(encoding="utf-8"))

    conf, avertissements = construire(a.nom, a.code, a.ecriture, reference,
                                      a.romanisation)
    dossier = Path(a.dossier) if a.dossier else CONFIGS
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / f"{ardoise(a.nom)}.json"
    if cible.exists() and not a.forcer:
        sys.exit(f"{cible} existe déjà — passer --forcer pour l'écraser")
    ecrire(conf, cible)

    print(f"config écrite : {cible}")
    print(f"  écriture     : {conf['ecriture']['systeme']}")
    print(f"  romanisation : {conf['ecriture']['romanisation']}")
    print(f"  gabarit      : repris de {a.reference}")
    for a_dire in avertissements:
        print(f"  ⚠ {a_dire}")
    print("\n  Les blocs « éditorial » sont des hypothèses. Les confronter au "
          "professeur\n  natif avant de lancer un livre entier.")
    print(f"\n  Langues à alphabet latin ({LATINES}) :\n"
          "  non prises en charge — le moteur distingue l'écriture enseignée de "
          "la langue\n  d'explication, distinction qui n'existe pas pour elles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
