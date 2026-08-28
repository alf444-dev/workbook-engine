#!/usr/bin/env python3
"""Plan d'un livre : les quotas de chaque leçon, avant toute génération.

Le plan est ce qui contraint la génération leçon par leçon. Il est dérivé de la
config de la langue et de la **courbe d'un livre déjà validé** : on ne devine
pas la pente de difficulté, on reprend celle qui a fonctionné.

Mesuré sur le CN10 : seul le vocabulaire nouveau dépend de la position dans le
livre (r = -0,74 avec le rang de la leçon). Le volume, les tableaux, les
dialogues et les exercices ne montrent pas de tendance (|r| < 0,4). Le plan
suit donc une courbe pour le vocabulaire, et une cible constante ailleurs —
c'est tout ce que la mesure autorise à affirmer.

    python3 pipeline/plan.py --lecons 31            → content/plan.json
    python3 pipeline/plan.py --titres sujets.txt
"""
import argparse, json, os

CONFIG = "config/chinese.json"
PROFIL = "content/profile.json"
GLOSSAIRE = "content/glossary.json"
OUT = "content/plan.json"
RAPPORT = "plan_report.txt"

def lisser(valeurs, fenetre=3):
    """Moyenne glissante : la courbe d'un livre réel est bruitée, sa pente non."""
    n = len(valeurs)
    out = []
    for i in range(n):
        debut, fin = max(0, i - fenetre // 2), min(n, i + fenetre // 2 + 1)
        out.append(sum(valeurs[debut:fin]) / (fin - debut))
    return out


def reechantillonner(poids, cible):
    """Ramène une courbe de m points à n points, par interpolation linéaire."""
    m = len(poids)
    if cible == m:
        return list(poids)
    out = []
    for i in range(cible):
        pos = i * (m - 1) / max(1, cible - 1)
        bas = int(pos)
        haut = min(m - 1, bas + 1)
        f = pos - bas
        out.append(poids[bas] * (1 - f) + poids[haut] * f)
    return out


def repartir(total, poids):
    """Répartit un entier selon des poids, sans perte (plus forts restes)."""
    somme = sum(poids) or 1
    exacts = [total * p / somme for p in poids]
    parts = [int(x) for x in exacts]
    reste = total - sum(parts)
    ordre = sorted(range(len(poids)), key=lambda i: exacts[i] - parts[i], reverse=True)
    for i in ordre[:reste]:
        parts[i] += 1
    return parts


def melange_exercices(config, n_lecons, par_lecon):
    """Répartit les types d'exercices selon les parts observées, étalés sur tout
    le livre.

    Méthode proportionnelle (Sainte-Laguë) : à chaque place, le type retenu est
    celui qui est le plus en retard sur sa part. Un type qui ne représente que
    2 % des exercices apparaît ainsi deux fois, à intervalle régulier, au lieu
    d'être groupé au début. Déterministe : deux exécutions donnent le même plan.
    """
    actifs = config["types_exercices"]["actifs"]
    types = sorted(actifs, key=lambda t: -actifs[t]["observes"])
    total = n_lecons * par_lecon
    parts = dict(zip(types, repartir(total, [actifs[t]["observes"] for t in types])))
    poses = {t: 0 for t in types}

    lecons = []
    for _ in range(n_lecons):
        choix = []
        for _ in range(par_lecon):
            restants = [t for t in types if poses[t] < parts[t]]
            if not restants:
                restants = types
            # on évite de répéter un type dans la même leçon quand c'est possible
            frais = [t for t in restants if t not in choix] or restants
            t = max(frais, key=lambda t: parts[t] / (2 * poses[t] + 1))
            poses[t] += 1
            choix.append(t)
        lecons.append(choix)
    return lecons


def vocabulaire_par_lecon(profil, glossaire, n_lecons):
    """Le vocabulaire que le livre de référence introduit à chaque leçon.

    Sans cette liste, le modèle choisit lui-même les caractères qu'il enseigne
    et en retient systématiquement moins que prévu : 465 caractères au lieu de
    584 sur un livre entier. Le curriculum d'un livre validé n'est pas à
    réinventer, il est à transmettre.
    """
    if not glossaire:
        return [[] for _ in range(n_lecons)]
    # position de lecture (histoires comprises) du rang de chaque leçon
    positions = [i + 1 for i, l in enumerate(profil["detail"]) if l["genre"] == "chapter"]
    par_position = {}
    for zh, info in glossaire["mots"].items():
        par_position.setdefault(info["lecon"], []).append(
            {"zh": zh, "pinyin": info["pinyin"]})
    return [par_position.get(positions[i], []) if i < len(positions) else []
            for i in range(n_lecons)]


def construire(config, profil, titres, glossaire=None):
    n = len(titres)
    vocabulaire = vocabulaire_par_lecon(profil, glossaire, n)
    quotas = config["quotas_lecon"]
    ref = [l["caracteres_nouveaux"] for l in profil["detail"] if l["genre"] == "chapter"]
    courbe = reechantillonner(lisser(ref), n)

    total_caracteres = round(profil["caracteres_distincts"] * n / max(1, len(ref)))
    par_lecon = repartir(total_caracteres, courbe)

    n_ex = quotas["exercices"]["cible"]
    total_exercices = n_ex * n
    melange = melange_exercices(config, n, n_ex)

    lecons = []
    for i, titre in enumerate(titres):
        lecon = {"n": i + 1, "titre": titre, "exercices": melange[i],
                 "vocabulaire": vocabulaire[i], "quotas": {}}
        for champ, q in quotas.items():
            if champ.startswith("_"):
                continue
            cible = par_lecon[i] if champ == "caracteres_nouveaux" else q["cible"]
            # La bande est l'étendue réellement observée dans le livre validé,
            # pas une tolérance inventée autour de la cible. Un contrôle plus
            # étroit que ce que les auteurs se permettent recale ses auteurs :
            # 71 % des leçons du CN10 étaient signalées avec ±50 % de la médiane.
            lecon["quotas"][champ] = {"cible": cible, "min": q["min"], "max": q["max"]}
        lecons.append(lecon)

    return {
        "langue": config["code"],
        "reference": profil.get("_source", "livre validé mesuré"),
        "lecons": lecons,
        "totaux": {"lecons": n, "caracteres_nouveaux": total_caracteres,
                   "exercices": total_exercices},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=CONFIG)
    ap.add_argument("--lecons", type=int, default=None,
                    help="nombre de leçons ; par défaut celui du livre de référence")
    ap.add_argument("--titres", default=None,
                    help="fichier de sujets, un par ligne")
    a = ap.parse_args()

    config = json.load(open(a.config))
    profil = json.load(open(PROFIL))
    reference = [l["titre"] for l in profil["detail"] if l["genre"] == "chapter"]

    if a.titres:
        titres = [t.strip() for t in open(a.titres) if t.strip()]
    else:
        n = a.lecons or len(reference)
        titres = (reference[:n] if n <= len(reference)
                  else reference + [f"LEÇON {i}" for i in range(len(reference) + 1, n + 1)])

    # Le curriculum d'une langue n'a rien à faire dans le plan d'une autre :
    # sans ce garde-fou, un plan japonais héritait du vocabulaire chinois.
    glossaire = json.load(open(GLOSSAIRE)) if os.path.exists(GLOSSAIRE) else None
    if glossaire and glossaire.get("langue") != config.get("code"):
        print(f"  glossaire ignoré : il est en {glossaire.get('langue')}, "
              f"la config est en {config.get('code')}")
        glossaire = None
    plan = construire(config, profil, titres, glossaire)
    os.makedirs("content", exist_ok=True)
    json.dump(plan, open(OUT, "w"), ensure_ascii=False, indent=1)

    lignes = ["PLAN DU LIVRE", "=" * 68,
              f"  {plan['totaux']['lecons']} leçons · "
              f"{plan['totaux']['caracteres_nouveaux']} caractères à enseigner · "
              f"{plan['totaux']['exercices']} exercices", "",
              f"  {'n':>3}  {'car.':>5}  {'bande':>9}  exercices"]
    for l in plan["lecons"]:
        q = l["quotas"]["caracteres_nouveaux"]
        lignes.append(f"  {l['n']:>3}  {q['cible']:>5}  {q['min']:>4}–{q['max']:<4}  "
                      f"{', '.join(l['exercices'])}")
    open(RAPPORT, "w").write("\n".join(lignes) + "\n")
    print(f"plan : {plan['totaux']['lecons']} leçons  → {OUT} + {RAPPORT}")


if __name__ == "__main__":
    main()
