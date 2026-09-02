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
import json, re
from collections import defaultdict

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
        "remarques": {
            "type": "array",
            "maxItems": QUOTA,
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
                paires = RE_PAIR.findall(ligne[0])
                if paires:
                    ajouter("phrase", paires[0][0],
                            {"path": chemin + ["rows", k], "field": 0,
                             "occurrence": 0}, prononciation=paires[0][1])
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


def relire(paquet_, modele, max_tokens=8000, effort="medium"):
    """Un relecteur. Le seul endroit de ce fichier qui appelle l'API."""
    import modele as fabrique
    client = fabrique.client(timeout=300.0, max_retries=1)
    with client.messages.stream(
        model=modele, max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": paquet_}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA},
                       "effort": effort},
    ) as flux:
        reponse = flux.get_final_message()
    if reponse.stop_reason == "max_tokens":
        raise RuntimeError(f"relecteur {modele} tronqué à {max_tokens} jetons")
    texte = next(b.text for b in reponse.content if b.type == "text")
    return json.loads(texte).get("remarques", []), reponse.usage
