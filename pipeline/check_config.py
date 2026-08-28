#!/usr/bin/env python3
"""Confronte la config d'une langue au livre sur lequel elle a été mesurée.

Une config qui prétend décrire les livres validés mais ne correspond plus à
aucun d'eux est pire qu'absente : elle contraindrait la génération avec des
quotas inventés. Chaque bloc marqué « mesuré » est donc revérifié ici.

    python3 pipeline/lesson_profile.py && python3 pipeline/check_config.py [config/chinese.json]
"""
import json, sys

PROFIL = "content/profile.json"


def comparer(ecarts, chemin, attendu, obtenu):
    if attendu != obtenu:
        ecarts.append(f"  {chemin:<48} config {attendu!r:>10}   livre {obtenu!r:>10}")


def main():
    chemin = sys.argv[1] if len(sys.argv) > 1 else "config/chinese.json"
    config = json.load(open(chemin))
    profil = json.load(open(PROFIL))
    ecarts = []

    # Une valeur reprise du gabarit d'un autre livre n'est pas vérifiable : il
    # n'existe pas encore de livre validé dans cette langue à quoi la comparer.
    # La dire « mesurée » serait faux ; on la signale telle quelle.
    gabarit = [nom for nom in ("structure_du_livre", "quotas_lecon",
                               "courbe_du_vocabulaire", "types_exercices")
               if config.get(nom, {}).get("_provenance", "").startswith("gabarit")]
    if gabarit:
        print(f"config {chemin} : {len(gabarit)} bloc(s) repris d'un gabarit, "
              f"non vérifiables ici — {', '.join(gabarit)}")
        for nom in gabarit:
            config = {k: v for k, v in config.items() if k != nom}
        if not any(k in config for k in ("structure_du_livre", "quotas_lecon",
                                         "courbe_du_vocabulaire", "types_exercices")):
            return 0

    if "structure_du_livre" in config:
        s = config["structure_du_livre"]
        comparer(ecarts, "structure_du_livre.lecons", s["lecons"], profil["lecons"])
        comparer(ecarts, "structure_du_livre.histoires", s["histoires"], profil["histoires"])
        comparer(ecarts, "structure_du_livre.caracteres_distincts",
                 s["caracteres_distincts"], profil["caracteres_distincts"])

    equivalences = {"mots_prose": "mots_prose", "mots_total": "mots"}
    for champ, quota in config.get("quotas_lecon", {}).items():
        if champ.startswith("_"):
            continue
        mesure = profil["quotas"][equivalences.get(champ, champ)]
        comparer(ecarts, f"quotas_lecon.{champ}.min", quota["min"], mesure["min"])
        comparer(ecarts, f"quotas_lecon.{champ}.cible", quota["cible"], mesure["median"])
        comparer(ecarts, f"quotas_lecon.{champ}.max", quota["max"], mesure["max"])

    for champ, valeur in config.get("courbe_du_vocabulaire", {}).items():
        if champ.startswith("_"):
            continue
        comparer(ecarts, f"courbe_du_vocabulaire.{champ}", valeur, profil["courbe"][champ])

    actifs = config.get("types_exercices", {}).get("actifs", {})
    total = sum(actifs[t]["observes"] for t in actifs) or 1
    for typ, bloc in actifs.items():
        comparer(ecarts, f"types_exercices.{typ}.observes", bloc["observes"],
                 profil["types_exercices"].get(typ, 0))
        comparer(ecarts, f"types_exercices.{typ}.part", bloc["part"],
                 round(profil["types_exercices"].get(typ, 0) / total, 2))
    manquants = (set(profil["types_exercices"]) - set(actifs)) if actifs else set()
    if manquants:
        ecarts.append(f"  types présents dans le livre et absents de la config : {sorted(manquants)}")

    if ecarts:
        print(f"config {chemin} — {len(ecarts)} écart(s) avec le livre mesuré :")
        print("\n".join(ecarts))
        return 1
    print(f"config {chemin} : toutes les valeurs mesurées correspondent au livre")
    return 0


if __name__ == "__main__":
    sys.exit(main())
