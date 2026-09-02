#!/usr/bin/env python3
"""Génère une leçon sous contrainte du plan, du glossaire et de la voix maison.

Le modèle ne produit **jamais de mise en page** : il rend des données
structurées, que ce script convertit en blocs, et que `templates/book.typ`
met en page. C'est ce qui rend les erreurs de formatage impossibles (invariant 1).

Il ne produit pas non plus les réponses séparément : chaque exercice porte les
siennes, et le corrigé en sera dérivé (invariant 2).

    export ANTHROPIC_API_KEY=…   (ou un .env à la racine)
    python3 pipeline/generate.py --lecon 12
    python3 pipeline/generate.py --lecon 12 --controler
"""
import argparse, json, os, re, subprocess, sys, time
from pathlib import Path

from env import charger
from lesson_profile import parcours, texte_cible
from pairs import RE_PAIR
import repetition

import langue as LANGUE
from langue import CONFIG as LANGUE_CONFIG, SCRIPT as HANZI

PLAN = "content/plan.json"
GLOSSAIRE = "content/glossary.json"
STYLE = "content/style.json"
# Le livre de référence change de nom en cours de projet : voir livre.py.
import livre
SORTIE = "content/generated"

MODELE = "claude-opus-5"

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["titre", "vocabulaire_nouveau", "sections", "exercices"],
    "properties": {
        "titre": {"type": "string"},
        "vocabulaire_nouveau": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["zh", "pinyin", "en"],
                "properties": {"zh": {"type": "string"},
                               "pinyin": {"type": "string"},
                               "en": {"type": "string"}},
            },
        },
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["titre", "paragraphes"],
                "properties": {
                    "titre": {"type": "string"},
                    "paragraphes": {"type": "array", "items": {"type": "string"}},
                    "tableaux": {
                        "type": "array",
                        "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["entetes", "lignes"],
                        "properties": {
                            "entetes": {"type": "array", "items": {"type": "string"}},
                            "lignes": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["zh", "pinyin", "en"],
                                    "properties": {"zh": {"type": "string"},
                                                   "pinyin": {"type": "string"},
                                                   "en": {"type": "string"}},
                                },
                            },
                        },
                        },
                    },
                    "dialogue": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["locuteur", "zh", "pinyin", "en"],
                            "properties": {"locuteur": {"type": "string"},
                                           "zh": {"type": "string"},
                                           "pinyin": {"type": "string"},
                                           "en": {"type": "string"}},
                        },
                    },
                },
            },
        },
        "exercices": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["type", "titre", "consigne", "items"],
                "properties": {
                    "type": {"type": "string"},
                    "titre": {"type": "string"},
                    "consigne": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["enonce", "reponse"],
                            "properties": {
                                "enonce": {"type": "string"},
                                "options": {"type": "array", "items": {"type": "string"}},
                                "reponse": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    },
}

SYSTEME = """Tu rédiges une leçon d'un manuel de {langue} publié par un éditeur,
destiné à des {public}. Tu écris en {explication} ; la langue enseignée s'écrit en
{ecriture}, et sa prononciation se note en {romanisation}.

Règles absolues :
- Tu rends des données structurées, jamais de mise en page. Pas de gras, d'astérisques,
  de titres markdown ni de numérotation manuelle : le maquettage est appliqué ailleurs.
- La leçon a pour objet d'enseigner du vocabulaire neuf : le quota de caractères
  nouveaux est une **cible à atteindre**, pas un plafond à éviter. Un livre dont les
  leçons enseignent moitié moins que prévu n'arrive jamais au bout de sa progression.
- Hors de ce quota, tu n'emploies que des caractères figurant dans le vocabulaire
  disponible fourni. Un caractère qui n'est ni dans la liste ni dans ton vocabulaire
  nouveau déclaré est une erreur, pas une liberté.
- Tu déclares dans « vocabulaire_nouveau » chaque mot que la leçon introduit, et tu
  l'enseignes réellement : présenté dans un tableau avec sa prononciation et son sens,
  puis réemployé dans la prose, un dialogue ou un exercice.
- Chaque exercice porte ses propres réponses. Elles doivent être exactes et cohérentes
  avec l'énoncé.
- La prononciation ({romanisation}) accompagne chaque phrase en {ecriture} et lui
  correspond exactement.
- Tu imites le ton des exemples fournis : direct, chaleureux, sans jargon pédagogique,
  sans formules d'encouragement creuses.
- **Privilégie les mots courants** : un mot fréquent se retient plus vite et sert dès
  la semaine suivante, ce qui rend la leçon simple et utile. Entre deux façons de dire
  la même chose, la plus ordinaire vaut mieux que la plus imagée — « je vais nager »
  plutôt que « je vais piquer une tête ». Ce n'est pas une interdiction : un mot moins
  courant se justifie s'il est vraiment utile au sujet de la leçon.
- **Écris pour ton lecteur** : un adulte anglophone (États-Unis, Canada, Royaume-Uni),
  débutant complet, qui a peu de temps libre et travaille par sessions courtes. Il doit
  pouvoir s'arrêter et reprendre sans se perdre."""


def consigne_systeme():
    """Le rôle, décliné pour la langue déclarée dans la config."""
    e = LANGUE_CONFIG.get("ecriture", {})
    return SYSTEME.format(
        langue=LANGUE_CONFIG.get("langue", "la langue cible"),
        public=LANGUE_CONFIG.get("public", "débutants"),
        explication=LANGUE_CONFIG.get("langue_d_explication", "anglais"),
        ecriture=e.get("systeme", "l'écriture cible"),
        romanisation=e.get("romanisation", "la romanisation"),
    )


def materiau(glossaire, style):
    """Écarte du prompt ce qui a été mesuré sur une autre langue.

    Le glossaire et les paragraphes types viennent du livre de référence. Quand
    la référence est dans une autre langue, ce matériau est le seul contenu
    concret du prompt : le modèle a écrit trente leçons de chinois pour un livre
    de japonais, parce qu'on lui donnait 260 mots chinois « déjà enseignés » et
    trois paragraphes chinois à imiter. `plan.py` avait ce garde-fou, pas ici.

    Le ton, lui, se transporte : on garde les paragraphes types, débarrassés de
    leurs mots étrangers, en disant d'où ils viennent.
    """
    if glossaire.get("langue") == LANGUE.CODE:
        return glossaire, style

    source = glossaire.get("langue") or "une autre langue"
    print(f"  matériau de référence écarté : mesuré en {source}, "
          f"la langue cible est {LANGUE.CODE} ({LANGUE.NOM})")
    sans_mots = {**glossaire, "mots": {}, "caracteres": {}}
    epure = {**style,
             "paragraphes_types": [{**p, "texte": sans_langue_etrangere(p["texte"])}
                                   for p in style.get("paragraphes_types", [])],
             "consignes": {t: [{**c, "consigne": sans_langue_etrangere(c["consigne"])}
                               for c in liste]
                           for t, liste in style.get("consignes", {}).items()},
             "_source_etrangere": source}
    return sans_mots, epure


def sans_langue_etrangere(texte):
    """Retire les mots de la langue de référence d'un exemple de style.

    Ils ne servent qu'à montrer le ton ; laissés en place, ils sont recopiés.
    """
    texte = RE_PAIR.sub("…", texte or "")
    return re.sub(r"[一-鿿぀-ゟ゠-ヿ가-힣]+", "…", texte)


def lecons_deja_ecrites(n):
    """Les leçons générées avant la n-ième, dans l'ordre : ce que le modèle
    doit éviter de répéter."""
    lecons = []
    for k in range(1, n):
        f = Path(SORTIE) / f"lecon_{k:02d}.json"
        if f.exists():
            try:
                lecons.append(json.loads(f.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
    return lecons


def brief(plan, glossaire, style, n):
    lecon = plan["lecons"][n - 1]
    q = lecon["quotas"]
    cible_car = q["caracteres_nouveaux"]["cible"]
    bas = max(1, int(cible_car * 0.8))
    haut = round(cible_car * 1.2)
    impose_liste = lecon.get("vocabulaire") or []
    n_impose = len(impose_liste)
    impose = ("\n".join(f"  {m['zh']}  ({m['pinyin']})" for m in impose_liste)
              or "  (aucune entrée imposée — choisis-les toi-même)")
    disponibles = [(zh, i["pinyin"]) for zh, i in glossaire["mots"].items() if i["lecon"] < n]
    consignes = []
    for typ in dict.fromkeys(lecon["exercices"]):
        for c in style["consignes"].get(typ, [])[:2]:
            consignes.append(f"  [{typ}] {c['titre']} — {c['consigne']}")
    paragraphes = "\n\n".join(f"  « {p['texte'][:400]} »"
                              for p in style["paragraphes_types"][:3])
    vocabulaire = ("\n".join(f"  {zh} ({py})" for zh, py in disponibles[-260:])
                   or "  (aucun — cette langue commence à zéro dans ce livre)")
    # Les exemples viennent parfois d'un livre écrit dans une autre langue : leurs
    # mots ont été retirés, mais il faut le dire, sinon le modèle croit devoir
    # les retrouver.
    etrangere = style.get("_source_etrangere")
    avertissement = ("" if not etrangere else
                     f"\n  Ces exemples viennent d'un livre de {etrangere} : leurs mots ont été\n"
                     f"  remplacés par « … ». Imite le ton, la longueur et la façon d'expliquer.\n"
                     f"  N'écris que du {LANGUE.NOM} : aucun mot d'une autre langue enseignée.")

    return f"""Leçon {n} : {lecon['titre']}

QUOTAS À RESPECTER (bornes du livre existant ; vise la cible)
  prose anglaise      {q['mots_prose']['cible']} mots (entre {q['mots_prose']['min']} et {q['mots_prose']['max']})
  sections            {q['sections']['cible']}
  tableaux            {q['tableaux']['cible']} au total sur la leçon, répartis entre les sections
                      (une section peut en porter plusieurs, ou aucune)
  lignes de tableau   {q['paires']['cible']} au total — c'est le volume de vocabulaire
                      présenté, la grandeur la plus importante après la prose
  dialogues           {q['dialogues']['cible']} ({q['repliques']['cible']} répliques au total)
  exercices           {len(lecon['exercices'])}, de ces types exactement : {', '.join(lecon['exercices'])}
  caractères nouveaux {q['caracteres_nouveaux']['cible']} visés (bande acceptable : {bas}–{haut})

VOCABULAIRE À ENSEIGNER DANS CETTE LEÇON — {n_impose} entrées imposées
  Ce n'est pas une suggestion, c'est la progression du livre. Enseigne **chacune**
  de ces entrées : présentée dans un tableau avec sa prononciation et son sens, puis
  réemployée dans la prose, un dialogue ou un exercice. Déclare-les toutes dans
  « vocabulaire_nouveau ». Tu peux en ajouter quelques-unes si la leçon l'exige,
  mais n'en omets aucune.
{impose}

VOCABULAIRE DÉJÀ ENSEIGNÉ (utilisable librement ; {len(disponibles)} entrées, les plus récentes)
{vocabulaire}

CONSIGNES D'EXERCICES DE LA MAISON (reprends ces tournures)
{chr(10).join(consignes)}

PARAGRAPHES TYPES DE LA MAISON (imite ce ton et cette longueur){avertissement}
{paragraphes}

{repetition.formuler(repetition.deja_employees(lecons_deja_ecrites(n)))}Rédige la leçon."""


def mots_cibles(lecon):
    """Tout ce que la leçon présente comme étant dans la langue enseignée."""
    mots = []
    for section in lecon.get("sections") or []:
        for tab in section.get("tableaux") or []:
            mots += [l["zh"] for l in tab.get("lignes") or []]
        for r in section.get("dialogue") or []:
            mots.append(r.get("zh", ""))
    for e in lecon.get("vocabulaire_nouveau") or []:
        mots.append(e.get("zh", ""))
    return [m for m in mots if m]


def refuser_si_autre_langue(lecon, n):
    """Une leçon écrite dans la mauvaise langue ne doit pas être écrite sur le
    disque : elle serait assemblée comme les autres et finirait imprimée.

    C'est arrivé : trente leçons de chinois dans un livre de japonais, chacune
    correcte de son point de vue, aucune vérification ne disant le contraire.
    """
    bon, motif = LANGUE.langue_plausible(mots_cibles(lecon))
    if not bon:
        raise RuntimeError(f"lesson {n} rejected — it is not written in "
                           f"{LANGUE.ANGLAIS}: {motif}")


def en_blocs(lecon, num, titre=None):
    """Convertit la sortie du modèle en blocs, au format de content/book.json.

    Le titre vient du **plan**, jamais du modèle : celui-ci le reformule d'un
    tirage à l'autre (« Lesson 3: … » ici, rien là), ce qui donnerait une table
    des matières incohérente.
    """
    blocs = []
    for section in lecon["sections"]:
        blocs.append({"type": "h2", "text": section["titre"]})
        for p in section.get("paragraphes", []):
            blocs.append({"type": "para", "text": p})
        for tab in section.get("tableaux") or []:
            # Convention du livre : deux colonnes, la paire écriture ↔ prononciation
            # dans la première, le sens anglais dans la seconde. Trois colonnes
            # décalaient le pinyin sous l'en-tête « English ».
            fournis = tab.get("entetes") or []
            # Le modèle propose souvent trois en-têtes (Chinese / Pinyin / English)
            # alors que la colonne de droite porte le sens : on garde la première
            # et la dernière, jamais celle du milieu.
            entetes = ([fournis[0], fournis[-1]] if len(fournis) >= 2
                       else [f"Useful Phrases in {LANGUE.ANGLAIS}", "What They Mean"])
            lignes = [entetes] + [[f"{{zh:{l['zh']}}} {{py:{l['pinyin']}}}", l["en"]]
                                  for l in tab["lignes"]]
            blocs.append({"type": "table", "ncols": 2, "rows": lignes})
        rep = section.get("dialogue")
        if rep:
            blocs.append({"type": "dialogue", "items": [
                {"kind": "line", "speaker": r["locuteur"], "zh": r["zh"],
                 "pinyin": r["pinyin"], "en": r["en"]} for r in rep]})
    for i, ex in enumerate(lecon["exercices"], 1):
        internes = [{"type": "para", "text": ex["consigne"]}]
        for item in ex["items"]:
            internes.append({"type": "para", "text": item["enonce"],
                             "list": {"ilvl": 0}})
            for opt in item.get("options") or []:
                internes.append({"type": "para", "text": opt, "list": {"ilvl": 1}})
        blocs.append({"type": "exercise", "num": i, "title": ex["titre"],
                      "ex_type": ex["type"], "blocks": internes,
                      "answers": [{"n": k, "text": it["reponse"]}
                                  for k, it in enumerate(ex["items"], 1)]})
    return {"kind": "chapter", "num": num,
            "title": titre or lecon["titre"], "blocks": blocs}


def ecrire_recu(n, usage):
    """Consigne ce qu'a coûté une leçon, pour que le serveur le lise sans
    analyser une sortie de terminal."""
    (Path(SORTIE) / f"lecon_{n:02d}_recu.json").write_text(
        json.dumps({"entree": usage.input_tokens, "sortie": usage.output_tokens},
                   ensure_ascii=False), encoding="utf-8")


def position_de_lecture(n):
    """Rang de la leçon n dans l'ordre de lecture, histoires comprises."""
    book = livre.charger()
    suite = [c for c in book["chapters"] if c["kind"] in ("chapter", "story")]
    rangs = [i + 1 for i, c in enumerate(suite) if c["kind"] == "chapter"]
    return rangs[n - 1]


def verifier_vocabulaire(brut, blocs, glossaire, plan, n):
    """Ce que le modèle dit introduire, contre ce qu'il introduit vraiment."""
    lu = position_de_lecture(n)
    apparition = glossaire["caracteres"]
    declares = set()
    for entree in brut.get("vocabulaire_nouveau") or []:
        declares |= set(HANZI.findall(entree["zh"]))
    employes = set()
    for bloc, _ in parcours(blocs["blocks"]):
        employes |= set(HANZI.findall(str(texte_cible(bloc))))
    reels = {c for c in employes if apparition.get(c, 10 ** 6) >= lu}
    cible = plan["lecons"][n - 1]["quotas"]["caracteres_nouveaux"]["cible"]

    print(f"  vocabulaire : {len(reels)} caractères réellement nouveaux "
          f"pour {cible} visés")
    non_declares = sorted(reels - declares)
    if non_declares:
        print(f"    {len(non_declares)} employés sans être déclarés : "
              f"{''.join(non_declares)}")
    fantomes = sorted(declares - employes)
    if fantomes:
        print(f"    {len(fantomes)} déclarés mais absents de la leçon : "
              f"{''.join(fantomes)}")


def produire(client, plan, glossaire, style, n, modele, max_tokens):
    """Génère une leçon et rend (blocs, usage). Lève en cas d'échec."""
    debut = time.monotonic()
    print(f"  leçon {n:>2} — lancée", flush=True)
    demande = brief(plan, glossaire, style, n)
    with client.messages.stream(
        model=modele, max_tokens=max_tokens,
        thinking={"type": "adaptive"}, system=consigne_systeme(),
        messages=[{"role": "user", "content": demande}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    ) as flux:
        reponse = flux.get_final_message()
    if reponse.stop_reason == "refusal":
        raise RuntimeError(f"refus : {reponse.stop_details}")
    if reponse.stop_reason == "max_tokens":
        raise RuntimeError(f"tronquée à {reponse.usage.output_tokens} jetons")
    texte = next(b.text for b in reponse.content if b.type == "text")
    lecon = json.loads(texte)
    refuser_si_autre_langue(lecon, n)

    os.makedirs(SORTIE, exist_ok=True)
    (Path(SORTIE) / f"lecon_{n:02d}_brut.json").write_text(
        json.dumps(lecon, ensure_ascii=False, indent=1), encoding="utf-8")
    blocs = en_blocs(lecon, n, plan["lecons"][n - 1]["titre"])
    (Path(SORTIE) / f"lecon_{n:02d}.json").write_text(
        json.dumps(blocs, ensure_ascii=False, indent=1), encoding="utf-8")
    ecrire_recu(n, reponse.usage)
    return lecon, blocs, reponse.usage, time.monotonic() - debut


def toutes(a, plan, glossaire, style):
    """Génère le livre entier. Reprenable : une leçon déjà produite est sautée."""
    import modele
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Une requête qui n'aboutit pas doit échouer vite et bruyamment : sans
    # délai explicite, la bibliothèque attend 10 minutes puis réessaie deux fois,
    # en silence. Une génération bloquée ressemblait alors à une génération lente.
    client = modele.client(timeout=float(a.delai), max_retries=1)
    restantes = [n for n in range(1, len(plan["lecons"]) + 1)
                 if a.refaire or not (Path(SORTIE) / f"lecon_{n:02d}.json").exists()]
    deja = len(plan["lecons"]) - len(restantes)
    print(f"{len(restantes)} leçons à produire"
          + (f", {deja} déjà présentes" if deja else "") + f", {a.parallele} en parallèle")

    entree = sortie = 0
    echecs = []
    with ThreadPoolExecutor(max_workers=a.parallele) as pool:
        travaux = {pool.submit(produire, client, plan, glossaire, style, n,
                               a.modele, a.max_tokens): n for n in restantes}
        for fini in as_completed(travaux):
            n = travaux[fini]
            try:
                lecon, blocs, usage, duree = fini.result()
            except Exception as e:
                echecs.append((n, str(e)[:120]))
                print(f"  leçon {n:>2} — ÉCHEC : {str(e)[:100]}", flush=True)
                continue
            entree += usage.input_tokens
            sortie += usage.output_tokens
            print(f"  leçon {n:>2} — {len(blocs['blocks']):>3} blocs, "
                  f"{usage.output_tokens:>6} jetons  {duree:>5.0f} s  "
                  f"{blocs['title'][:40]}", flush=True)

    cout = entree / 1e6 * 5 + sortie / 1e6 * 25
    print()
    print(f"{len(restantes) - len(echecs)}/{len(restantes)} leçons produites")
    print(f"jetons : {entree} en entrée, {sortie} en sortie  —  environ {cout:.2f} $")
    for n, message in echecs:
        print(f"  échec leçon {n} : {message}")
    return 1 if echecs else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lecon", type=int, default=None)
    ap.add_argument("--toutes", action="store_true", help="génère le livre entier")
    ap.add_argument("--parallele", type=int, default=2)
    ap.add_argument("--delai", type=int, default=420,
                    help="délai maximal d'une requête, en secondes")
    ap.add_argument("--refaire", action="store_true",
                    help="regénère même les leçons déjà produites")
    ap.add_argument("--controler", action="store_true",
                    help="passe la leçon générée au contrôle de conformité")
    ap.add_argument("--modele", default=MODELE)
    ap.add_argument("--max-tokens", type=int, default=32000,
                    dest="max_tokens", help="plafond de jetons en sortie")
    ap.add_argument("--reconvertir", action="store_true",
                    help="reconstruit les blocs depuis la sortie brute, sans régénérer")
    a = ap.parse_args()

    charger()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY absente — voir pipeline/check_key.py")
    import modele

    plan = json.load(open(PLAN))
    glossaire, style = materiau(json.load(open(GLOSSAIRE)), json.load(open(STYLE)))
    if a.toutes and a.reconvertir:
        # Reconvertit tout depuis les sorties brutes, sans un seul appel payant.
        faits, refusees = 0, []
        for brut in sorted(Path(SORTIE).glob("lecon_*_brut.json")):
            n = int(brut.name.split("_")[1])
            lecon = json.loads(brut.read_text(encoding="utf-8"))
            # Même contrôle qu'à la génération : reconvertir d'anciennes sorties
            # brutes ne doit pas réintroduire des leçons dans la mauvaise langue.
            try:
                refuser_si_autre_langue(lecon, n)
            except RuntimeError as e:
                refusees.append(str(e))
                continue
            (Path(SORTIE) / f"lecon_{n:02d}.json").write_text(
                json.dumps(en_blocs(lecon, n, plan["lecons"][n - 1]["titre"]),
                           ensure_ascii=False, indent=1), encoding="utf-8")
            faits += 1
        print(f"{faits} leçons reconverties (aucun appel au modèle)")
        for message in refusees:
            print(f"  {message}")
        return 1 if refusees else 0
    if a.toutes:
        return toutes(a, plan, glossaire, style)
    if a.lecon is None:
        sys.exit("préciser --lecon N ou --toutes")
    if not 1 <= a.lecon <= len(plan["lecons"]):
        sys.exit(f"leçon hors du plan (1–{len(plan['lecons'])})")

    brut = Path(SORTIE) / f"lecon_{a.lecon:02d}_brut.json"
    if a.reconvertir:
        if not brut.exists():
            sys.exit(f"pas de sortie brute pour la leçon {a.lecon}")
        lecon = json.loads(brut.read_text(encoding="utf-8"))
        try:
            refuser_si_autre_langue(lecon, a.lecon)
        except RuntimeError as e:
            sys.exit(str(e))
        chemin = Path(SORTIE) / f"lecon_{a.lecon:02d}.json"
        chemin.write_text(json.dumps(en_blocs(lecon, a.lecon,
                                              plan["lecons"][a.lecon - 1]["titre"]),
                                     ensure_ascii=False, indent=1),
                          encoding="utf-8")
        print(f"leçon {a.lecon} reconvertie depuis {brut} (aucun appel au modèle)")
        return 0

    demande = brief(plan, glossaire, style, a.lecon)
    client = modele.client(timeout=900.0, max_retries=1)
    # En streaming : une leçon complète dépasse largement les plafonds prudents,
    # et une réponse tronquée coûte le prix d'une génération pour rien.
    with client.messages.stream(
        model=a.modele,
        max_tokens=a.max_tokens,
        thinking={"type": "adaptive"},
        system=consigne_systeme(),
        messages=[{"role": "user", "content": demande}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    ) as flux:
        reponse = flux.get_final_message()

    if reponse.stop_reason == "refusal":
        sys.exit(f"génération refusée : {reponse.stop_details}")
    if reponse.stop_reason == "max_tokens":
        sys.exit(f"réponse tronquée à {reponse.usage.output_tokens} jetons : "
                 f"relancer avec --max-tokens supérieur à {a.max_tokens}")

    texte = next(b.text for b in reponse.content if b.type == "text")
    try:
        lecon = json.loads(texte)
    except json.JSONDecodeError as e:
        sys.exit(f"sortie du modèle illisible ({e}) — arrêt en {reponse.stop_reason}")

    os.makedirs(SORTIE, exist_ok=True)
    try:
        refuser_si_autre_langue(lecon, a.lecon)
    except RuntimeError as e:
        sys.exit(str(e))
    # La sortie brute du modèle est conservée : elle permet de reconvertir sans
    # régénérer quand le convertisseur change.
    (Path(SORTIE) / f"lecon_{a.lecon:02d}_brut.json").write_text(
        json.dumps(lecon, ensure_ascii=False, indent=1), encoding="utf-8")
    chemin = Path(SORTIE) / f"lecon_{a.lecon:02d}.json"
    chemin.write_text(json.dumps(en_blocs(lecon, a.lecon,
                                          plan["lecons"][a.lecon - 1]["titre"]),
                                 ensure_ascii=False, indent=1),
                      encoding="utf-8")
    u = reponse.usage
    ecrire_recu(a.lecon, u)
    print(f"leçon {a.lecon} générée → {chemin}")
    print(f"  jetons : {u.input_tokens} en entrée, {u.output_tokens} en sortie")
    verifier_vocabulaire(lecon, json.loads(chemin.read_text(encoding="utf-8")),
                         glossaire, plan, a.lecon)

    if a.controler:
        book = livre.charger()
        lecons = [i for i, c in enumerate(book["chapters"]) if c["kind"] == "chapter"]
        book["chapters"][lecons[a.lecon - 1]] = json.loads(chemin.read_text(encoding="utf-8"))
        temoin = Path("content/book_generated.json")
        temoin.write_text(json.dumps(book, ensure_ascii=False), encoding="utf-8")
        print("\n--- contrôle de conformité ---")
        subprocess.run([sys.executable, "pipeline/check_lesson.py",
                        "--lecon", str(a.lecon), "--livre", str(temoin)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
