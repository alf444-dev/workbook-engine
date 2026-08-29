#!/usr/bin/env python3
"""Tout ce qui se vérifie avant de payer une génération.

Un livre entier a été écrit dans la mauvaise langue pour quinze dollars, alors
que chacun des signes avant-coureurs était visible sans lancer un seul appel :
le plan n'imposait aucun mot, le glossaire était dans une autre langue, et le
prompt de la première leçon contenait 260 mots chinois pour un livre japonais.

Ce script relit tout cela, gratuitement, et rend compte ligne par ligne.

    WB_LANGUE=japanese python3 pipeline/check_generation.py
"""
import json, os, re, sys
from pathlib import Path

import langue as LANGUE

PLAN = "content/plan.json"
GLOSSAIRE = "content/glossary.json"
STYLE = "content/style.json"

# Toutes les écritures que ce moteur peut enseigner. On ne peut pas se contenter
# de « hors de l'écriture cible » : les kanji japonais et les sinogrammes chinois
# partagent leur bloc Unicode, donc du chinois passerait pour du japonais. La
# règle est plus stricte et plus simple — dans le prompt, tout caractère d'une
# écriture enseignée doit venir du vocabulaire que le plan impose.
ECRITURES = re.compile("[一-鿿぀-ゟ゠-ヿ가-힣]")

lignes = []


def dire(bon, texte, detail=""):
    lignes.append((bon, texte, detail))
    return bon


def charger(chemin):
    return json.loads(Path(chemin).read_text(encoding="utf-8")) if Path(chemin).exists() else None


def main():
    dire(True, f"target language: {LANGUE.ANGLAIS} ({LANGUE.CODE})")
    dire(bool(LANGUE.SIGNATURE or LANGUE.EXCLUT),
         "the config can tell this writing system from its neighbours",
         "no signature declared: a lesson in a related language would pass")

    plan = charger(PLAN)
    if not dire(plan is not None, "the book plan exists", f"{PLAN} is missing"):
        return rendre()

    lecons = plan["lecons"]
    dire(len(lecons) > 0, f"the plan covers {len(lecons)} lessons")

    impose = [m for l in lecons for m in (l.get("vocabulaire") or [])]
    dire(bool(impose),
         f"the plan imposes {len(impose)} vocabulary entries",
         "none: the model would pick what it teaches, with nothing anchoring it "
         "to the target language — this is what produced a whole book in the "
         "wrong one")

    if impose:
        bon, motif = LANGUE.langue_plausible([m["zh"] for m in impose])
        dire(bon, f"the imposed vocabulary really is {LANGUE.ANGLAIS}", motif)

    vides = [l["n"] for l in lecons if not (l.get("vocabulaire") or [])]
    dire(not vides, "every lesson has vocabulary to teach",
         f"lessons with none: {vides[:12]}{'…' if len(vides) > 12 else ''}")

    glossaire = charger(GLOSSAIRE) or {}
    if glossaire:
        meme = glossaire.get("langue") == LANGUE.CODE
        dire(True,
             f"reference glossary is {glossaire.get('langue')} — "
             + ("reused" if meme else "kept out of the prompt, different language"))

    style = charger(STYLE)
    dire(style is not None, "the style examples exist", f"{STYLE} is missing")

    # Le contrôle qui compte : le prompt réel, tel qu'il partira.
    if plan and style is not None:
        import generate
        g, s = generate.materiau(glossaire or {"mots": {}, "caracteres": {}}, style)
        n = 1
        prompt = generate.brief(plan, g, s, n)
        attendus = {c for m in impose for c in m["zh"]}
        attendus |= {c for zh in (g.get("mots") or {}) for c in zh}
        vus = [c for c in prompt if ECRITURES.match(c)]
        etrangers = [c for c in vus if c not in attendus]
        dire(not etrangers,
             f"the lesson {n} prompt holds only the planned vocabulary",
             f"{len(etrangers)} characters from elsewhere: "
             f"{''.join(dict.fromkeys(etrangers))[:40]}")
        dire(True, f"lesson {n} prompt: {len(prompt)} characters, "
                   f"{len(vus)} in the taught writing system")

        actifs = set(LANGUE.CONFIG.get("types_exercices", {}).get("actifs", []))
        demandes = {t for l in lecons for t in l.get("exercices", [])}
        inconnus = sorted(demandes - actifs) if actifs else []
        dire(not inconnus, "every exercise type in the plan is enabled",
             f"unknown types: {inconnus}")

    dire(bool((os.environ.get("ANTHROPIC_API_KEY") or "").strip()),
         "an API key is in place",
         "ANTHROPIC_API_KEY is missing: generation would fail on the first call")
    return rendre()


def rendre():
    for bon, texte, detail in lignes:
        print(f"  {'✓' if bon else '✗'} {texte}")
        if not bon and detail:
            print(f"      {detail}")
    rates = [l for l in lignes if not l[0]]
    print(f"\n{len(lignes) - len(rates)}/{len(lignes)} checks passed")
    return 1 if rates else 0


if __name__ == "__main__":
    sys.exit(main())
