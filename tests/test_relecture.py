#!/usr/bin/env python3
"""La relecture multi-agents, sans appeler un seul agent.

Tout ce qui décide du volume qui remonte aux humains — le découpage, le quota,
le vote, le routage — est du code, et se vérifie sans dépenser un centime.
Ne reste au modèle que le jugement qu'aucun programme ne sait porter.

    python3 tests/test_relecture.py
"""
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import relecture                                                 # noqa: E402
from pairs import conteneur                                      # noqa: E402
from fixture_book import BOOK                                    # noqa: E402

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


CHAPITRE = [c for c in BOOK["chapters"] if c["kind"] == "chapter"][0]
BASE = ["chapters", 1]
U = relecture.unites(CHAPITRE, BASE)

# ---------------------------------------------------------------- découpage
ok("la leçon se découpe en unités relisibles", len(U) >= 4, str(len(U)))
genres = {u["genre"] for u in U}
ok("prose, phrases et exercices sont distingués",
   {"prose", "phrase", "exercice"} <= genres, str(genres))
ok("aucune unité vide", all(u["texte"].strip() for u in U))
ok("les identifiants sont uniques", len({u["id"] for u in U}) == len(U))
ok("et stables d'une exécution à l'autre",
   [u["id"] for u in relecture.unites(CHAPITRE, BASE)] == [u["id"] for u in U],
   "sinon une remarque désignerait autre chose au tirage suivant")

# Une remarque doit pouvoir devenir une correction : l'adresse doit retrouver
# son bloc dans le livre, exactement comme le font les décisions.
resolues = 0
for u in U:
    try:
        conteneur(BOOK, u["target"])
        resolues += 1
    except Exception:                                            # noqa: BLE001
        pass
ok("chaque adresse retrouve son emplacement dans le livre",
   resolues == len(U), f"{resolues}/{len(U)}")

# Une cellule de tableau contient souvent plusieurs paires. N'en soumettre
# qu'une montrait au relecteur une phrase amputée — les 483 cellules du CN10
# l'étaient, dont une de quinze entrées réduite à un caractère.
MULTIPLE = {"kind": "chapter", "num": 9, "title": "T", "blocks": [
    {"type": "table", "ncols": 2, "rows": [
        ["Phrase", "Meaning"],
        ["{zh:那个人是你}……{zh:吗？} {py:Nà ge rén shì nǐ … ma?}", "Is that person your…?"],
        ["{zh:我} {py:wǒ} {zh:你} {py:nǐ} {zh:他} {py:tā}", "I / you / he"]]}]}
cellules = relecture.unites(MULTIPLE, ["chapters", 0])
ok("une cellule à plusieurs paires est soumise entière",
   all("……" in c["texte"] or c["texte"].count(" ") >= 3 for c in cellules),
   str([c["texte"] for c in cellules]))
ok("rien n'est amputé du début de la cellule",
   any(c["texte"].startswith("那个人是你") for c in cellules),
   str([c["texte"] for c in cellules]))
ok("la traduction accompagne la phrase, pour juger sur pièce",
   any((c.get("prononciation") or "").startswith("Is that person") for c in cellules),
   str([c.get("prononciation") for c in cellules]))

entetes = [u for u in U if u["texte"].strip() in ("teacher", "student")]
ok("les en-têtes de tableau ne sont pas soumis à relecture", not entetes,
   "la voix maison se répète exprès")

# ---------------------------------------------------------------- le paquet
p = relecture.paquet(U, "chinois", "adultes débutants anglophones")
ok("le paquet énonce le quota", str(relecture.QUOTA) in p)
ok("il dit ce que le code vérifie déjà, pour ne pas le redemander",
   "prononciation" in p and "déjà" in p)
ok("il liste les unités avec leur identifiant", all(u["id"] in p for u in U))
for trace in ("opus", "sonnet", "claude", "généré", "genere", "modèle",
              "humain", "book_typed", "content/"):
    ok(f"le paquet ne trahit pas la provenance ({trace})", trace not in p.lower(),
       "un relecteur qui sait qu'il lit une machine cherche des fautes de machine")
ok("il interdit la réécriture", "ne récris pas" in p.lower())

# ---------------------------------------------------------------- le vote
u1, u2, u3 = U[0]["id"], U[1]["id"], U[2]["id"]
rendus = {
    "A": [{"unite": u1, "categorie": "langue", "gravite": "bloquant",
           "constat": "personne ne dit ça"},
          {"unite": u2, "categorie": "clarte", "gravite": "mineur",
           "constat": "ambigu"}],
    "B": [{"unite": u1, "categorie": "langue", "gravite": "genant",
           "constat": "tournure improbable", "suggestion": "dire autrement"},
          {"unite": u3, "categorie": "exemple", "gravite": "mineur",
           "constat": "inutile"}],
    "C": [{"unite": u1, "categorie": "langue", "gravite": "mineur",
           "constat": "bizarre"},
          {"unite": u1, "categorie": "langue", "gravite": "bloquant",
           "constat": "je le redis"}],
}
retenues, reserve = relecture.accord(rendus)
ok("ce que trois relecteurs voient ensemble est retenu",
   retenues and retenues[0]["unite"] == u1 and retenues[0]["voix"] == 3,
   str(retenues[:1]))
ok("un relecteur qui se répète ne vote qu'une fois",
   retenues[0]["relecteurs"] == ["A", "B", "C"], str(retenues[0]["relecteurs"]))
ok("la gravité retenue est la plus sévère des trois",
   retenues[0]["gravite"] == "bloquant", retenues[0]["gravite"])
ok("ce qu'un seul relecteur voit reste en réserve",
   {e["unite"] for e in reserve} == {u2, u3},
   str([e["unite"] for e in reserve]))
ok("la réserve ne remonte pas aux humains", all(e["voix"] == 1 for e in reserve))
ok("les suggestions sont conservées",
   retenues[0]["suggestions"] == ["dire autrement"], str(retenues[0]["suggestions"]))

seul, _ = relecture.accord({"A": rendus["A"]})
ok("avec un seul relecteur, rien n'est retenu — il n'y a pas d'accord", not seul,
   "un avis unique n'est pas un vote")

# ---------------------------------------------------------------- le routage
items = relecture.en_items(retenues, U, "GREETINGS")
ok("les remarques retenues deviennent des items de file", len(items) == 1)
it = items[0]
ok("une remarque de langue va au professeur natif", it["queue"] == "teacher",
   it["queue"])
ok("l'item porte l'adresse, donc la correction pourra s'appliquer",
   it["target"] == U[0]["target"])
ok("il dit combien de relecteurs l'ont vue", it["voix"] == 3)
ok("il a la forme des items existants",
   {"id", "kind", "queue", "lesson", "title", "detail", "target"} <= set(it))

clarte = relecture.en_items(
    [{"unite": u2, "categorie": "clarte", "voix": 2, "relecteurs": ["A", "B"],
      "gravite": "genant", "constats": ["ambigu"], "suggestions": []}], U, "T")
ok("une remarque de clarté va à l'éditeur", clarte[0]["queue"] == "editor")

fantome = relecture.en_items(
    [{"unite": "inconnu", "categorie": "langue", "voix": 2, "relecteurs": ["A", "B"],
      "gravite": "mineur", "constats": ["x"], "suggestions": []}], U, "T")
ok("une remarque sur une unité inventée est écartée", not fantome,
   "un modèle qui invente une adresse ne doit pas créer un item")

# ------------------------------------------------- évaluation à défauts semés
# La feuille de route demande : « le système retrouve les erreurs déjà
# identifiées ». Personne n'a encore relu de livre à la main, alors on sème des
# défauts connus et on mesure ce que la chaîne en fait — avec un panel simulé,
# pour vérifier la mécanique avant de la payer.
DEFAUTS = {U[0]["id"]: "langue", U[2]["id"]: "clarte"}


def panel_simule(unites_, defauts, trouve=(True, True, False), bruit=None):
    """Trois relecteurs : les deux premiers voient les défauts, le troisième
    invente une remarque à lui. C'est le cas que le vote doit trancher."""
    rendus = {}
    for i, (nom, voit) in enumerate(zip("ABC", trouve)):
        remarques = []
        if voit:
            remarques += [{"unite": u, "categorie": c, "gravite": "genant",
                           "constat": f"{nom} : problème"} for u, c in defauts.items()]
        if bruit and nom == bruit:
            remarques.append({"unite": unites_[-1]["id"], "categorie": "exemple",
                              "gravite": "mineur", "constat": "avis isolé"})
        rendus[nom] = remarques
    return rendus


retenues2, reserve2 = relecture.accord(panel_simule(U, DEFAUTS, bruit="C"))
trouves = {e["unite"] for e in retenues2}
ok("les défauts semés sont retrouvés par le vote", trouves == set(DEFAUTS),
   str(trouves))
ok("l'avis isolé ne remonte pas", len(reserve2) == 1 and reserve2[0]["voix"] == 1)
ok("le volume qui remonte est celui des défauts réels, pas plus",
   len(retenues2) == len(DEFAUTS), f"{len(retenues2)} pour {len(DEFAUTS)} semés")

# Un relecteur qui rate tout : le vote doit encore tenir avec les deux autres.
retenues3, _ = relecture.accord(panel_simule(U, DEFAUTS, trouve=(True, True, False)))
ok("un relecteur défaillant ne fait pas perdre les défauts",
   {e["unite"] for e in retenues3} == set(DEFAUTS))

# Deux relecteurs sur trois qui ratent : plus d'accord, rien ne remonte. C'est
# le sens sûr de l'erreur — on préfère taire que noyer.
retenues4, reserve4 = relecture.accord(panel_simule(U, DEFAUTS, trouve=(True, False, False)))
ok("un seul relecteur clairvoyant ne suffit pas à faire remonter",
   not retenues4 and len(reserve4) == len(DEFAUTS),
   "le quota et le vote protègent la crédibilité de la file")

# ---------------------------------------------------------------- le schéma
# L'API refuse `maxItems` dans un schéma de sortie structurée, et c'est tant
# mieux : un quota demandé à un modèle est un quota espéré.
ok("le schéma ne compte pas sur le modèle pour tenir le quota",
   "maxItems" not in relecture.SCHEMA["properties"]["remarques"],
   "l'API le refuse, et il ne faudrait pas s'y fier de toute façon")


class FauxFlux:
    def __init__(self, n): self.n = n
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def get_final_message(self):
        class R: pass
        r = R(); r.stop_reason = "end_turn"
        class B: pass
        b = B(); b.type = "text"
        b.text = json.dumps({"remarques": [
            {"unite": f"u{i}", "categorie": "langue", "gravite": "mineur",
             "constat": f"remarque {i}"} for i in range(self.n)]})
        r.content = [b]
        class U: pass
        u = U(); u.input_tokens = 100; u.output_tokens = 200
        r.usage = u
        return r


class FauxClient:
    def __init__(self, n): self.messages = self
    stream = None


import types                                                     # noqa: E402
faux = types.SimpleNamespace(
    client=lambda **k: types.SimpleNamespace(
        messages=types.SimpleNamespace(stream=lambda **kw: FauxFlux(20))))
sys.modules["modele"] = faux
remarques, _ = relecture.relire("paquet", "modele-essai", quota=8)
ok("un relecteur bavard est coupé au quota", len(remarques) == 8,
   f"{len(remarques)} remarques laissées passer")
ok("et ce sont les premières, censées être les plus graves",
   remarques[0]["constat"] == "remarque 0")
del sys.modules["modele"]
cats = relecture.SCHEMA["properties"]["remarques"]["items"]["properties"]["categorie"]["enum"]
ok("toute catégorie du schéma sait vers quelle file aller",
   all(c in relecture.FILES for c in cats), str(cats))
ok("le schéma n'accepte rien d'autre que ce qui est prévu",
   relecture.SCHEMA["additionalProperties"] is False)

rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
