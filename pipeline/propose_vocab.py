#!/usr/bin/env python3
"""Propose la progression de vocabulaire d'un livre, à faire valider.

Pour une langue nouvelle il n'existe pas de livre validé d'où tirer le
curriculum. Le modèle en propose un — **toute la progression en un seul appel**,
parce que la cohérence d'une leçon à l'autre est précisément ce qu'on veut
obtenir : pas de doublon, difficulté croissante, rien qui serve avant d'être
enseigné.

Le professeur natif ne relit pas un livre : il tranche une liste, dans la
console de relecture. C'est ce qui rend une nouvelle langue possible avec un
professeur qui change à chaque titre.

    WB_LANGUE=japanese python3 pipeline/propose_vocab.py
"""
import json, os, sys
from pathlib import Path

from env import charger
from langue import CONFIG as LANGUE, NOM

PLAN = "content/plan.json"
OUT = "content/vocabulaire_propose.json"
RAPPORT = "vocabulaire_propose.txt"
MODELE = "claude-opus-5"

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["lecons"],
    "properties": {
        "lecons": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["n", "titre", "entrees"],
                "properties": {
                    "n": {"type": "integer"},
                    "titre": {"type": "string"},
                    "entrees": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["ecriture", "prononciation", "sens"],
                            "properties": {
                                "ecriture": {"type": "string"},
                                "prononciation": {"type": "string"},
                                "sens": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }
    },
}


def consigne():
    e = LANGUE.get("ecriture", {})
    axes = ", ".join(LANGUE.get("axes_pedagogiques", {}).get("axes", []))
    prog = LANGUE.get("progression", {})
    return f"""Tu établis la progression de vocabulaire d'un manuel de {NOM} pour
{LANGUE.get('public', 'adultes débutants')}, écrit en {LANGUE.get('langue_d_explication', 'anglais')}.

L'écriture enseignée est {e.get('systeme', '?')}, la prononciation se note en
{e.get('romanisation', '?')}. Progression de référence : {prog.get('reference', '—')},
niveaux visés {prog.get('niveaux_vises', '—')}.
Axes pédagogiques du livre : {axes}.

Règles :
- **Privilégie les mots courants** : un mot fréquent se retient plus vite et sert dès
  la semaine suivante, ce qui rend la leçon simple et utile. Entre deux façons de dire
  la même chose, la plus ordinaire vaut mieux que la plus imagée — « je vais nager »
  plutôt que « je vais piquer une tête ». Ce n'est pas une interdiction : un mot moins
  courant se justifie s'il est vraiment utile au sujet de la leçon.
- **Écris pour ton lecteur** : un adulte anglophone (États-Unis, Canada, Royaume-Uni),
  débutant complet, qui a peu de temps libre et travaille par sessions courtes. Il doit
  pouvoir s'arrêter et reprendre sans se perdre.
- **Difficulté croissante.** Le début du livre enseigne beaucoup, la fin consolide :
  les premières leçons portent nettement plus d'entrées neuves que les dernières.
- **Aucun doublon** d'une leçon à l'autre : une entrée n'est introduite qu'une fois.
- **Rien ne s'emploie avant d'être enseigné** : une leçon ne peut s'appuyer que sur le
  vocabulaire des leçons précédentes et sur le sien.
- Chaque entrée porte son écriture, sa prononciation exacte, et son sens en anglais.
- Tu proposes ; c'est un professeur natif qui valide. Reste sobre et justifiable."""


def demande(plan):
    lignes = []
    for l in plan["lecons"]:
        cible = l["quotas"]["caracteres_nouveaux"]["cible"]
        lignes.append(f"  {l['n']:>2}. {l['titre']}  — environ {max(3, round(cible * 0.7))} entrées")
    return ("Voici le plan du livre : un titre par leçon, et le volume de vocabulaire\n"
            "neuf attendu (issu de la courbe mesurée sur un livre validé).\n\n"
            + "\n".join(lignes)
            + "\n\nProduis la progression complète, leçon par leçon.")


def main():
    charger()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY absente — voir pipeline/check_key.py")
    import anthropic

    plan = json.load(open(PLAN))
    client = anthropic.Anthropic(timeout=900.0, max_retries=1)
    with client.messages.stream(
        model=MODELE, max_tokens=64000,
        thinking={"type": "adaptive"},
        system=consigne(),
        messages=[{"role": "user", "content": demande(plan)}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    ) as flux:
        reponse = flux.get_final_message()
    if reponse.stop_reason == "max_tokens":
        sys.exit(f"réponse tronquée à {reponse.usage.output_tokens} jetons")
    if reponse.stop_reason == "refusal":
        sys.exit(f"refus : {reponse.stop_details}")

    propose = json.loads(next(b.text for b in reponse.content if b.type == "text"))
    propose["langue"] = LANGUE.get("code")
    os.makedirs("content", exist_ok=True)
    json.dump(propose, open(OUT, "w"), ensure_ascii=False, indent=1)

    # Contrôles déterministes avant de déranger un humain (invariant 3).
    vues, doublons = {}, []
    total = 0
    for l in propose["lecons"]:
        for e in l["entrees"]:
            total += 1
            if e["ecriture"] in vues:
                doublons.append((e["ecriture"], vues[e["ecriture"]], l["n"]))
            else:
                vues[e["ecriture"]] = l["n"]
    tiers = max(1, len(propose["lecons"]) // 3)
    debut = sum(len(l["entrees"]) for l in propose["lecons"][:tiers])
    fin = sum(len(l["entrees"]) for l in propose["lecons"][-tiers:])

    lignes = [f"PROGRESSION PROPOSÉE — {NOM}", "=" * 62,
              f"  {len(propose['lecons'])} leçons, {total} entrées, {len(vues)} distinctes",
              f"  doublons entre leçons : {len(doublons)}",
              f"  densité : {debut} entrées sur le premier tiers, {fin} sur le dernier", ""]
    for d in doublons[:10]:
        lignes.append(f"    doublon {d[0]} — leçons {d[1]} et {d[2]}")
    lignes.append("")
    for l in propose["lecons"]:
        lignes.append(f"  {l['n']:>2}. {l['titre']}  ({len(l['entrees'])} entrées)")
        for e in l["entrees"][:6]:
            lignes.append(f"        {e['ecriture']}  {e['prononciation']}  — {e['sens']}")
    open(RAPPORT, "w").write("\n".join(lignes) + "\n")

    u = reponse.usage
    print(f"progression : {total} entrées, {len(doublons)} doublon(s)  → {OUT} + {RAPPORT}")
    print(f"  densité : {debut} au premier tiers, {fin} au dernier")
    print(f"  jetons : {u.input_tokens} en entrée, {u.output_tokens} en sortie")
    return 0


if __name__ == "__main__":
    sys.exit(main())
