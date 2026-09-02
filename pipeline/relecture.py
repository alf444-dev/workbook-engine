#!/usr/bin/env python3
"""Relecture par plusieurs modèles, à l'aveugle, avec quota et vote.

Phase 3bis de la feuille de route. Le principe qui commande tout le reste est
l'invariant 3 : **le code passe avant les agents**. Ce qui se vérifie de façon
déterministe — prononciation contre écriture, quotas, bijection des réponses,
caractères non encore enseignés, répétition d'une leçon à l'autre — n'est pas
soumis à un modèle. Les relecteurs ne sont donc interrogés que sur ce qu'aucun
programme ne sait faire : est-ce que ça se dit, est-ce que c'est clair, est-ce
que l'exemple sert à un adulte qui a peu de temps.

Quatre décisions structurantes :

1. **À l'aveugle.** Le paquet ne dit ni d'où vient le texte, ni s'il a été écrit
   par un humain ou par un modèle, ni lequel. Un relecteur qui sait qu'il lit une
   sortie de machine cherche des fautes de machine.
2. **Sous quota.** Chaque relecteur rend au plus N remarques, classées. Sans
   quota, un modèle en trouve toujours plus, et une file qui déborde ne se vide
   pas — c'est l'invariant 4 sous une autre forme.
3. **Au vote.** Une remarque qu'un seul relecteur soulève reste en réserve ;
   il en faut deux, indépendants et sur des modèles différents, pour qu'elle
   remonte à un humain. C'est ce qui fait baisser le volume sans perdre les
   vraies erreurs.
4. **Sans réécriture.** Un relecteur constate et localise ; il ne récrit pas.
   La réécriture est une étape séparée, et c'est un humain qui la déclenche.

Rien ici n'appelle l'API : `paquet()`, `accord()` et `en_items()` sont purement
déterministes et testés comme tels. Seul `relire()` parle à un modèle.
"""
import json, os, re
from collections import defaultdict
from pathlib import Path

from ids import Numeroteur
from pairs import RE_PAIR, plain, tc

# Combien de remarques au maximum par relecteur et par leçon. Mesuré sur rien
# pour l'instant : c'est une borne de départ, à confronter au volume réel.
QUOTA = 8

# Combien de relecteurs indépendants doivent soulever la même chose pour qu'elle
# remonte à un humain.
ACCORD_MINIMAL = 2

# Ce que chaque catégorie de remarque implique comme file humaine. La langue
# revient au professeur natif (invariant 5), le reste à l'éditeur.
FILES = {"langue": "teacher", "registre": "teacher",
         "clarte": "editor", "exemple": "editor"}

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["remarques"],
    "properties": {
        # Pas de `maxItems` : l'API le refuse dans un schéma de sortie
        # structurée — et c'est tant mieux. Un quota demandé à un modèle est un
        # quota espéré ; celui-ci est appliqué par `relire()`, qui coupe.
        "remarques": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["unite", "categorie", "gravite", "constat"],
                "properties": {
                    "unite": {"type": "string"},
                    "categorie": {"type": "string",
                                  "enum": sorted(FILES)},
                    "gravite": {"type": "string",
                                "enum": ["bloquant", "genant", "mineur"]},
                    "constat": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
            },
        }
    },
}


def unites(chapitre, base):
    """Les morceaux relisibles d'une leçon, chacun avec son adresse.

    L'adresse est celle qu'utilisent déjà les décisions (`pipeline/pairs.py`) :
    une remarque doit pouvoir devenir une correction appliquée au bon endroit,
    sinon elle ne sert qu'à faire du bruit.
    """
    sortie = []
    numero = Numeroteur()

    def ajouter(genre, texte, cible, prononciation=None):
        if not (texte or "").strip():
            return
        sortie.append({
            "id": numero(genre, "", plain(texte)[:80], ""),
            "genre": genre, "texte": plain(texte),
            "prononciation": prononciation, "target": cible})

    for j, b in enumerate(chapitre.get("blocks") or []):
        chemin = base + ["blocks", j]
        t = b.get("type")
        if t in ("para", "h2", "h3", "minihead"):
            ajouter("prose", b.get("text"), {"path": chemin, "field": "text",
                                             "occurrence": 0})
        elif t == "table":
            for k, ligne in enumerate(b.get("rows") or []):
                if not ligne or not RE_PAIR.search(str(ligne[0])):
                    continue          # en-tête : la voix maison, pas à relire
                # La cellule entière, pas sa première paire. Une cellule en
                # contient souvent plusieurs, séparées par du texte ou des
                # sauts : n'en soumettre qu'une revient à montrer au relecteur
                # une phrase amputée, qu'il signale — à juste titre — comme
                # amputée. Les 483 cellules du CN10 l'étaient toutes.
                traduction = plain(ligne[1]) if len(ligne) > 1 else ""
                ajouter("phrase", ligne[0],
                        {"path": chemin + ["rows", k], "field": 0,
                         "occurrence": 0}, prononciation=traduction or None)
        elif t == "dialogue":
            for k, it in enumerate(b.get("items") or []):
                if it.get("kind") == "line":
                    ajouter("phrase", it.get("zh"),
                            {"path": chemin + ["items", k], "field": "pinyin",
                             "occurrence": 0}, prononciation=it.get("pinyin"))
        elif t == "exercise":
            for k, interne in enumerate(b.get("blocks") or []):
                if interne.get("type") == "para":
                    ajouter("exercice", interne.get("text"),
                            {"path": chemin + ["blocks", k], "field": "text",
                             "occurrence": 0})
    return sortie


CONSIGNE = """Tu relis une page d'un manuel de {langue} destiné à des {public}.

Tu ne sais pas d'où vient ce texte, et tu n'as pas à le deviner : juge-le pour
ce qu'il est.

**Ce que des programmes vérifient déjà, et sur quoi tu ne dis rien** : la
correspondance entre l'écriture et la prononciation, le nombre d'exercices et de
tableaux, la longueur de la prose, les caractères introduits trop tôt, les
réponses qui ne correspondent pas aux questions. Une remarque sur l'un de ces
points est une remarque perdue.

**Ce qu'on te demande**, et que rien ne sait vérifier à ta place :

- `langue` — la phrase ne se dit pas, ou pas comme ça ; elle est correcte mais
  personne ne la dirait ; le mot existe mais n'est pas celui qu'on emploie.
- `registre` — le niveau de langue ne convient pas à la situation décrite.
- `clarte` — l'explication en anglais est fausse, ambiguë, ou suppose quelque
  chose que le lecteur n'a pas encore vu.
- `exemple` — la phrase est juste mais ne sert à rien : un adulte qui a peu de
  temps ne s'en servira pas cette semaine.

**Au plus {quota} remarques.** Si tu en vois davantage, garde les plus graves :
une liste qu'on ne peut pas traiter ne sera pas traitée. Si tu n'en vois aucune,
rends une liste vide — c'est une réponse, pas un échec.

Chaque remarque cite l'identifiant de l'unité concernée, dit ce qui ne va pas,
et propose éventuellement mieux. Tu ne récris pas la leçon."""


def paquet(unites_, langue, public, quota=QUOTA):
    """Le texte soumis au relecteur. Aucune trace de provenance."""
    lignes = []
    for u in unites_:
        marque = {"prose": "TEXTE", "phrase": "PHRASE", "exercice": "EXERCICE"}
        detail = f"  [{u['id']}] {marque[u['genre']]} : {u['texte']}"
        if u.get("prononciation"):
            detail += f"  ({u['prononciation']})"
        lignes.append(detail)
    return (CONSIGNE.format(langue=langue, public=public, quota=quota)
            + "\n\nLa page :\n\n" + "\n".join(lignes))


def accord(rendus, minimum=ACCORD_MINIMAL):
    """Regroupe les remarques de plusieurs relecteurs et compte les voix.

    Deux remarques comptent pour la même quand elles visent la même unité et la
    même catégorie. On ne compare pas les phrases : deux relecteurs qui disent
    la même chose ne l'écrivent jamais pareil.

    Rend (retenues, en_reserve), la première liste triée par nombre de voix puis
    par gravité.
    """
    groupes = defaultdict(list)
    for relecteur, remarques in rendus.items():
        vus = set()
        for r in remarques or []:
            cle = (r.get("unite"), r.get("categorie"))
            if cle in vus:
                continue              # un relecteur ne vote qu'une fois
            vus.add(cle)
            groupes[cle].append({**r, "relecteur": relecteur})

    poids = {"bloquant": 0, "genant": 1, "mineur": 2}
    retenues, reserve = [], []
    for (unite, categorie), votes in groupes.items():
        entree = {
            "unite": unite, "categorie": categorie,
            "voix": len(votes),
            "relecteurs": sorted(v["relecteur"] for v in votes),
            "gravite": min((v.get("gravite", "mineur") for v in votes),
                           key=lambda g: poids.get(g, 3)),
            "constats": [v.get("constat", "") for v in votes],
            "suggestions": [v["suggestion"] for v in votes if v.get("suggestion")],
        }
        (retenues if len(votes) >= minimum else reserve).append(entree)

    retenues.sort(key=lambda e: (-e["voix"], poids.get(e["gravite"], 3)))
    reserve.sort(key=lambda e: poids.get(e["gravite"], 3))
    return retenues, reserve


def en_items(retenues, unites_, lecon_titre):
    """Traduit les remarques retenues en items de file, format du bundle.

    C'est la raison d'être de la phase : les agents alimentent les files
    humaines existantes, ils n'en créent pas de nouvelles.
    """
    par_id = {u["id"]: u for u in unites_}
    numero = Numeroteur()
    items = []
    for e in retenues:
        u = par_id.get(e["unite"])
        if not u:
            continue                  # une remarque sur une unité inventée
        constat = max(e["constats"], key=len) if e["constats"] else ""
        items.append({
            "id": numero("relecture", tc(lecon_titre), u["texte"][:60], constat[:60]),
            "kind": "relecture", "queue": FILES.get(e["categorie"], "editor"),
            "lesson": lecon_titre, "title": u["texte"][:120],
            "detail": constat, "target": u["target"],
            "categorie": e["categorie"], "gravite": e["gravite"],
            "voix": e["voix"], "relecteurs": e["relecteurs"],
            "suggestion": e["suggestions"][0] if e["suggestions"] else "",
            "zh": u["texte"] if u["genre"] == "phrase" else "",
            "pinyin": u.get("prononciation") or "",
        })
    return items


def relire(paquet_, modele, max_tokens=8000, effort="medium", quota=QUOTA):
    """Un relecteur. Le seul endroit de ce fichier qui appelle l'API.

    Le quota est appliqué ici, en coupant : le prompt le demande, mais un
    modèle qui en rend douze ne doit pas pouvoir noyer la file. Les remarques
    sont censées être classées par importance ; on garde les premières.
    """
    import modele as fabrique
    client = fabrique.client(timeout=300.0, max_retries=1)
    format_ = {"type": "json_schema", "schema": SCHEMA}
    base = {"model": modele, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": paquet_}]}

    # Tous les modèles ne prennent pas la réflexion adaptative ni le paramètre
    # d'effort : Haiku 4.5 refuse les deux. C'est justement le relecteur bon
    # marché qui donne au vote une troisième voix — le perdre transformerait
    # l'accord en unanimité à deux. On dégrade l'appel plutôt que d'entretenir
    # une table de modèles, qui dériverait à la sortie suivante.
    tentatives = [
        {**base, "thinking": {"type": "adaptive"},
         "output_config": {"format": format_, "effort": effort}},
        {**base, "output_config": {"format": format_, "effort": effort}},
        {**base, "output_config": {"format": format_}},
    ]
    derniere = None
    for essai in tentatives:
        try:
            with client.messages.stream(**essai) as flux:
                reponse = flux.get_final_message()
            break
        except Exception as e:                                   # noqa: BLE001
            derniere = e
            if "does not support" not in str(e) and "not supported" not in str(e):
                raise
    else:
        raise derniere
    if reponse.stop_reason == "max_tokens":
        raise RuntimeError(f"relecteur {modele} tronqué à {max_tokens} jetons")
    texte = next(b.text for b in reponse.content if b.type == "text")
    remarques = json.loads(texte).get("remarques", []) or []
    return remarques[:quota], reponse.usage


PANEL = ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5-20251001"]


def relire_une(numero, chapitre, base, modeles, langue_nom, public, quota,
               effort, executeur):
    """Une leçon passée au panel. Rend le dossier de résultats, sans écrire."""
    u = unites(chapitre, base)
    demande = paquet(u, langue_nom, public, quota)
    rendus, jetons, echecs = {}, {}, {}
    with executeur(max_workers=len(modeles)) as pool:
        travaux = {pool.submit(relire, demande, m, 8000, effort, quota): m
                   for m in modeles}
        for fini in travaux:
            m = travaux[fini]
            try:
                remarques, usage = fini.result()
            except Exception as e:                               # noqa: BLE001
                echecs[m] = str(e)[:160]
                continue
            rendus[m] = remarques
            jetons[m] = (usage.input_tokens, usage.output_tokens)
    retenues, reserve = accord(rendus)
    return {"lecon": numero, "titre": chapitre.get("title"), "unites": len(u),
            "rendus": rendus, "echecs": echecs, "jetons": jetons,
            "retenues": retenues, "reserve": reserve,
            "items": en_items(retenues, u, chapitre.get("title", ""))}


def tout_le_livre(a, chapitres, modeles, langue_nom, config, tarifs, executeur):
    """Le livre entier, reprenable. Une leçon déjà relue n'est pas repayée."""
    dossier = Path("output/relecture")
    dossier.mkdir(parents=True, exist_ok=True)
    public = config.get("public", "débutants")

    a_faire = [n for n in range(1, len(chapitres) + 1)
               if a.refaire or not (dossier / f"lecon_{n:02d}.json").exists()]
    deja = len(chapitres) - len(a_faire)
    print(f"  {len(chapitres)} leçons, {len(a_faire)} à relire"
          + (f", {deja} déjà faites" if deja else "")
          + f", {len(modeles)} relecteurs, {a.parallele} leçons de front")

    def une(n):
        i, chapitre = chapitres[n - 1]
        d = relire_une(n, chapitre, ["chapters", i], modeles, langue_nom, public,
                       a.quota, a.effort, executeur)
        (dossier / f"lecon_{n:02d}.json").write_text(
            json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        return d

    cout_total = 0.0
    with executeur(max_workers=a.parallele) as pool:
        for d in pool.map(une, a_faire):
            c = sum(tarifs.cout(e, s, m) for m, (e, s) in d["jetons"].items())
            cout_total += c
            rendues = sum(len(r or []) for r in d["rendus"].values())
            alerte = f"  ✗ {', '.join(d['echecs'])}" if d["echecs"] else ""
            print(f"  leçon {d['lecon']:>2}  {d['unites']:>3} unités  "
                  f"{rendues:>3} rendues → {len(d['retenues']):>2} retenues  "
                  f"{c:.3f}${alerte}", flush=True)

    # Le livre entier, rassemblé : c'est ce qui alimentera les files humaines.
    tout = [json.loads((dossier / f"lecon_{n:02d}.json").read_text(encoding="utf-8"))
            for n in range(1, len(chapitres) + 1)
            if (dossier / f"lecon_{n:02d}.json").exists()]
    items = [it for d in tout for it in d["items"]]
    rendues = sum(len(r or []) for d in tout for r in d["rendus"].values())
    retenues = sum(len(d["retenues"]) for d in tout)
    reserve = sum(len(d["reserve"]) for d in tout)
    (dossier / "tout.json").write_text(json.dumps(
        {"lecons": len(tout), "rendues": rendues, "retenues": retenues,
         "reserve": reserve, "items": items}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    par_file = defaultdict(int)
    par_categorie = defaultdict(int)
    for it in items:
        par_file[it["queue"]] += 1
        par_categorie[it["categorie"]] += 1
    print(f"\n  {len(tout)} leçons relues, {cout_total:.2f}$ dépensés ce passage")
    print(f"  {rendues} remarques rendues → {retenues} retenues, {reserve} en réserve")
    print(f"  par file      : {dict(par_file)}")
    print(f"  par catégorie : {dict(par_categorie)}")
    print(f"  → {dossier}/tout.json")
    return 0


def main():
    """Lance le panel sur une leçon et rend ce qui remonterait aux humains."""
    import argparse
    from env import charger                  # la clé vit dans .env, pas ici
    import livre as livre_ref
    import tarifs
    from langue import CONFIG as LANGUE_CONFIG, NOM as LANGUE_NOM
    from concurrent.futures import ThreadPoolExecutor

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--lecon", type=int, default=None)
    ap.add_argument("--toutes", action="store_true",
                    help="tout le livre, reprenable : une leçon déjà relue est sautée")
    ap.add_argument("--parallele", type=int, default=2,
                    help="leçons menées de front ; chacune occupe déjà le panel")
    ap.add_argument("--refaire", action="store_true",
                    help="relire même ce qui l'a déjà été")
    ap.add_argument("--panel", default=",".join(PANEL))
    ap.add_argument("--quota", type=int, default=QUOTA)
    ap.add_argument("--effort", default="medium",
                    choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--sortie", default="output/relecture.json")
    a = ap.parse_args()
    charger()
    if not (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
        raise SystemExit("ANTHROPIC_API_KEY absente — voir pipeline/check_key.py")

    book = livre_ref.charger()
    chapitres = [(i, ch) for i, ch in enumerate(book["chapters"])
                 if ch["kind"] == "chapter"]
    modeles = [m.strip() for m in a.panel.split(",") if m.strip()]

    if a.toutes:
        return tout_le_livre(a, chapitres, modeles, LANGUE_NOM, LANGUE_CONFIG,
                             tarifs, ThreadPoolExecutor)
    if a.lecon is None:
        raise SystemExit("préciser --lecon N ou --toutes")
    if not 1 <= a.lecon <= len(chapitres):
        raise SystemExit(f"pas de leçon {a.lecon} dans ce livre "
                         f"(1–{len(chapitres)})")
    i, chapitre = chapitres[a.lecon - 1]
    base = ["chapters", i]

    u = unites(chapitre, base)
    demande = paquet(u, LANGUE_NOM, LANGUE_CONFIG.get("public", "débutants"),
                     a.quota)
    print(f"  leçon {a.lecon} — {len(u)} unités, {len(modeles)} relecteurs, "
          f"quota {a.quota}, effort {a.effort}")

    rendus, couts, echecs = {}, {}, {}
    with ThreadPoolExecutor(max_workers=len(modeles)) as pool:
        travaux = {pool.submit(relire, demande, m, 8000, a.effort, a.quota): m
                   for m in modeles}
        for fini in travaux:
            m = travaux[fini]
            try:
                remarques, usage = fini.result()
            except Exception as e:                               # noqa: BLE001
                echecs[m] = str(e)[:120]
                continue
            rendus[m] = remarques
            couts[m] = tarifs.cout(usage.input_tokens, usage.output_tokens, m)

    for m, motif in echecs.items():
        print(f"  ✗ {m} : {motif}")
    for m in rendus:
        print(f"  {m:28} {len(rendus[m]):>2} remarques   {couts[m]:.3f}$")

    retenues, reserve = accord(rendus)
    items = en_items(retenues, u, chapitre.get("title", ""))
    Path(a.sortie).parent.mkdir(parents=True, exist_ok=True)
    Path(a.sortie).write_text(json.dumps(
        {"lecon": a.lecon, "titre": chapitre.get("title"), "unites": len(u),
         "rendus": rendus, "retenues": retenues, "reserve": reserve,
         "items": items, "cout": round(sum(couts.values()), 4)},
        ensure_ascii=False, indent=1), encoding="utf-8")

    total = sum(len(r or []) for r in rendus.values())
    print(f"\n  {total} remarques rendues → {len(retenues)} retenues "
          f"({len(reserve)} en réserve, une seule voix)")
    for e in retenues:
        texte = next((x["texte"] for x in u if x["id"] == e["unite"]), "?")
        print(f"    [{e['voix']} voix, {e['gravite']}, {e['categorie']}] "
              f"{texte[:60]}")
        print(f"       {max(e['constats'], key=len)[:110]}")
    print(f"\n  coût : {sum(couts.values()):.3f}$  →  {a.sortie}")
    return 0


if __name__ == "__main__":
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
