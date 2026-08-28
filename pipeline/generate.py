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
import argparse, copy, json, os, subprocess, sys
from pathlib import Path

from env import charger

PLAN = "content/plan.json"
GLOSSAIRE = "content/glossary.json"
STYLE = "content/style.json"
BOOK = "content/book_typed.json"
SORTIE = "content/generated"

MODELE = "claude-opus-5"

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["titre", "sections", "exercices"],
    "properties": {
        "titre": {"type": "string"},
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

SYSTEME = """Tu rédiges une leçon d'un manuel de chinois pour adultes anglophones débutants,
publié par un éditeur. Tu écris en anglais ; la langue enseignée est le chinois simplifié.

Règles absolues :
- Tu rends des données structurées, jamais de mise en page. Pas de gras, d'astérisques,
  de titres markdown ni de numérotation manuelle : le maquettage est appliqué ailleurs.
- Tu n'emploies que des caractères chinois figurant dans le vocabulaire disponible
  fourni, plus au maximum le nombre de caractères nouveaux autorisé. Un caractère hors
  de cette liste est une erreur, pas une liberté.
- Chaque exercice porte ses propres réponses. Elles doivent être exactes et cohérentes
  avec l'énoncé.
- Le pinyin accompagne chaque phrase chinoise, avec les tons, et correspond exactement
  aux caractères.
- Tu imites le ton des exemples fournis : direct, chaleureux, sans jargon pédagogique,
  sans formules d'encouragement creuses."""


def brief(plan, glossaire, style, n):
    lecon = plan["lecons"][n - 1]
    q = lecon["quotas"]
    disponibles = [(zh, i["pinyin"]) for zh, i in glossaire["mots"].items() if i["lecon"] < n]
    consignes = []
    for typ in dict.fromkeys(lecon["exercices"]):
        for c in style["consignes"].get(typ, [])[:2]:
            consignes.append(f"  [{typ}] {c['titre']} — {c['consigne']}")
    paragraphes = "\n\n".join(f"  « {p['texte'][:400]} »"
                              for p in style["paragraphes_types"][:3])
    vocabulaire = "\n".join(f"  {zh} ({py})" for zh, py in disponibles[-260:])

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
  caractères nouveaux {q['caracteres_nouveaux']['cible']} au maximum

VOCABULAIRE DÉJÀ ENSEIGNÉ (utilisable librement ; {len(disponibles)} entrées, les plus récentes)
{vocabulaire}

CONSIGNES D'EXERCICES DE LA MAISON (reprends ces tournures)
{chr(10).join(consignes)}

PARAGRAPHES TYPES DE LA MAISON (imite ce ton et cette longueur)
{paragraphes}

Rédige la leçon."""


def en_blocs(lecon, num):
    """Convertit la sortie du modèle en blocs, au format de content/book.json."""
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
                       else ["Useful Phrases in Chinese", "What They Mean"])
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
    return {"kind": "chapter", "num": num, "title": lecon["titre"], "blocks": blocs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lecon", type=int, required=True)
    ap.add_argument("--controler", action="store_true",
                    help="passe la leçon générée au contrôle de conformité")
    ap.add_argument("--modele", default=MODELE)
    ap.add_argument("--reconvertir", action="store_true",
                    help="reconstruit les blocs depuis la sortie brute, sans régénérer")
    a = ap.parse_args()

    charger()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY absente — voir pipeline/check_key.py")
    import anthropic

    plan = json.load(open(PLAN))
    glossaire = json.load(open(GLOSSAIRE))
    style = json.load(open(STYLE))
    if not 1 <= a.lecon <= len(plan["lecons"]):
        sys.exit(f"leçon hors du plan (1–{len(plan['lecons'])})")

    brut = Path(SORTIE) / f"lecon_{a.lecon:02d}_brut.json"
    if a.reconvertir:
        if not brut.exists():
            sys.exit(f"pas de sortie brute pour la leçon {a.lecon}")
        lecon = json.loads(brut.read_text(encoding="utf-8"))
        chemin = Path(SORTIE) / f"lecon_{a.lecon:02d}.json"
        chemin.write_text(json.dumps(en_blocs(lecon, a.lecon), ensure_ascii=False, indent=1),
                          encoding="utf-8")
        print(f"leçon {a.lecon} reconvertie depuis {brut} (aucun appel au modèle)")
        return 0

    demande = brief(plan, glossaire, style, a.lecon)
    client = anthropic.Anthropic()
    reponse = client.messages.create(
        model=a.modele,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=SYSTEME,
        messages=[{"role": "user", "content": demande}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )
    if reponse.stop_reason == "refusal":
        sys.exit(f"génération refusée : {reponse.stop_details}")

    texte = next(b.text for b in reponse.content if b.type == "text")
    lecon = json.loads(texte)

    os.makedirs(SORTIE, exist_ok=True)
    # La sortie brute du modèle est conservée : elle permet de reconvertir sans
    # régénérer quand le convertisseur change.
    (Path(SORTIE) / f"lecon_{a.lecon:02d}_brut.json").write_text(
        json.dumps(lecon, ensure_ascii=False, indent=1), encoding="utf-8")
    chemin = Path(SORTIE) / f"lecon_{a.lecon:02d}.json"
    chemin.write_text(json.dumps(en_blocs(lecon, a.lecon), ensure_ascii=False, indent=1),
                      encoding="utf-8")
    u = reponse.usage
    print(f"leçon {a.lecon} générée → {chemin}")
    print(f"  jetons : {u.input_tokens} en entrée, {u.output_tokens} en sortie")

    if a.controler:
        book = json.load(open(BOOK))
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
