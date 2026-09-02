#!/usr/bin/env python3
"""Compare deux modèles sur la même leçon, sans savoir lequel a écrit quoi.

La question posée : Sonnet écrit-il des leçons assez bonnes pour remplacer
Opus, qui coûte 2,5 fois plus cher ? On ne la tranche pas à l'œil sur une
impression — le projet a une règle (invariant 3) : ce qui se mesure de façon
déterministe ne se confie pas à un jugement.

Trois critères mécaniques, dans cet ordre :

  1. `check_lesson --serre` — la leçon tient-elle dans les bandes du livre
     humain (prose, sections, tableaux, dialogues, vocabulaire nouveau) ;
  2. la part de prose reprise aux leçons précédentes (`repetition.py`), la
     plainte n°1 des éditeurs ;
  3. le vocabulaire imposé par le plan est-il réellement enseigné.

Et un quatrième, humain, qui arrive en dernier et **à l'aveugle** : deux pages
`A.html` et `B.html`, la correspondance dans `cle.json`. Savoir quel modèle on
lit suffit à orienter le jugement.

    WB_LANGUE=chinese python3 pipeline/comparer.py --lecon 5 \\
        --modeles claude-opus-5,claude-sonnet-5 --tours 1

`--simuler` note ce qui est déjà dans content/generated sans appeler l'API :
de quoi vérifier l'outil, et re-noter après coup, sans dépenser un centime.
"""
import argparse, html, json, os, shutil, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import livre as livre_ref                                        # noqa: E402
import repetition                                                # noqa: E402
import tarifs                                                    # noqa: E402

GENERE = Path("content/generated")
SORTIE = Path("content/comparaison")
PLAN = "content/plan.json"


def slug(modele, tour):
    return f"{modele.replace('claude-', '')}-{tour}"


def produire(n, modele, tour, max_tokens):
    """Écrit la leçon n avec ce modèle et met ses fichiers de côté."""
    dossier = SORTIE / slug(modele, tour)
    dossier.mkdir(parents=True, exist_ok=True)
    for suffixe in (".json", "_brut.json", "_recu.json"):
        vieux = GENERE / f"lecon_{n:02d}{suffixe}"
        if vieux.exists():
            vieux.unlink()

    debut = time.monotonic()
    r = subprocess.run([sys.executable, "pipeline/generate.py", "--lecon", str(n),
                        "--modele", modele, "--max-tokens", str(max_tokens)],
                       capture_output=True, text=True)
    duree = time.monotonic() - debut
    for suffixe in (".json", "_brut.json", "_recu.json"):
        f = GENERE / f"lecon_{n:02d}{suffixe}"
        if f.exists():
            shutil.copy2(f, dossier / f"lecon{suffixe}")
    (dossier / "sortie.txt").write_text(r.stdout + r.stderr, encoding="utf-8")
    (dossier / "duree.json").write_text(json.dumps({"secondes": round(duree)}),
                                        encoding="utf-8")
    return r.returncode == 0, r.stdout + r.stderr


def livre_hybride(n, lecon, cible):
    """Le livre de référence dont la n-ième leçon est remplacée par celle-ci.

    C'est ce que `check_lesson` doit voir : une leçon ne se juge pas seule, ses
    quotas et sa répétition se mesurent par rapport à ce qui la précède.
    """
    book = livre_ref.charger()
    rang = 0
    chapitres = []
    for ch in book["chapters"]:
        if ch["kind"] == "chapter":
            rang += 1
            if rang == n:
                remplacee = dict(lecon)
                remplacee["num"] = ch.get("num", n)
                chapitres.append(remplacee)
                continue
        chapitres.append(ch)
    book["chapters"] = chapitres
    cible.write_text(json.dumps(book, ensure_ascii=False), encoding="utf-8")
    return cible


def noter(n, dossier):
    """Les trois mesures déterministes. Rend un dictionnaire."""
    fichier = dossier / "lecon.json"
    if not fichier.exists():
        return {"echec": "aucune leçon produite"}
    lecon = json.loads(fichier.read_text(encoding="utf-8"))

    hybride = livre_hybride(n, lecon, dossier / "livre.json")
    r = subprocess.run([sys.executable, "pipeline/check_lesson.py",
                        "--livre", str(hybride), "--lecon", str(n), "--serre"],
                       capture_output=True, text=True)
    remarques = [l.strip() for l in r.stdout.splitlines()
                 if l.strip().startswith("[")]

    reference = livre_ref.charger()
    precedentes = [c for c in reference["chapters"] if c["kind"] == "chapter"][:n - 1]
    part = repetition.part_reprise(lecon, precedentes)

    plan = json.loads(Path(PLAN).read_text(encoding="utf-8"))
    impose = plan["lecons"][n - 1].get("vocabulaire") or []
    texte = json.dumps(lecon, ensure_ascii=False)
    enseignes = sum(1 for m in impose if m["zh"] in texte)

    jetons = {}
    recu = dossier / "lecon_recu.json"
    if recu.exists():
        jetons = json.loads(recu.read_text(encoding="utf-8"))
    duree = 0
    if (dossier / "duree.json").exists():
        duree = json.loads((dossier / "duree.json").read_text())["secondes"]

    return {"remarques": remarques, "repetition": part,
            "vocabulaire": (enseignes, len(impose)),
            "entree": jetons.get("entree", 0), "sortie": jetons.get("sortie", 0),
            "duree": duree}


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="robots" content="noindex, nofollow"><title>Lesson {etiquette}</title>
<style>body{{margin:0;background:#EEF2F0;color:#12211E;
font:16px/1.6 Archivo,system-ui,sans-serif}}
main{{max-width:44rem;margin:0 auto;padding:40px 24px 80px}}
h1{{font:600 27px/1.25 'Source Serif 4',Georgia,serif;margin:0 0 22px}}
h2{{font:600 19px/1.3 'Source Serif 4',Georgia,serif;margin:30px 0 8px}}
p{{margin:0 0 12px}}
table{{border-collapse:collapse;width:100%;margin:12px 0;background:#fff;
border-radius:10px;overflow:hidden}}
td,th{{padding:9px 12px;border-bottom:1px solid #D8E0DC;text-align:left;font-size:15px}}
th{{background:#E4EFEB;font-size:12px;letter-spacing:.6px;text-transform:uppercase}}
.ex{{background:#fff;border-left:3px solid #E5A33C;border-radius:0 10px 10px 0;
padding:14px 16px;margin:16px 0}}
.dial{{background:#fff;border-radius:10px;padding:14px 16px;margin:12px 0}}
</style></head><body><main><h1>Lesson {etiquette}</h1>{corps}</main></body></html>"""


def rendre(lecon):
    """La leçon en HTML lisible, sans rien qui trahisse le modèle."""
    out = []

    def bloc(b):
        t = b.get("type")
        net = lambda x: html.escape(str(x or "")).replace("{zh:", "").replace("{py:", " ").replace("}", "")
        if t == "h2":
            out.append(f"<h2>{net(b.get('text'))}</h2>")
        elif t == "para":
            out.append(f"<p>{net(b.get('text'))}</p>")
        elif t == "table":
            lignes = b.get("rows") or []
            if lignes:
                tete = "".join(f"<th>{net(c)}</th>" for c in lignes[0])
                corps = "".join("<tr>" + "".join(f"<td>{net(c)}</td>" for c in l)
                                + "</tr>" for l in lignes[1:])
                out.append(f"<table><tr>{tete}</tr>{corps}</table>")
        elif t == "dialogue":
            lignes = "".join(f"<p><b>{net(i.get('speaker'))}</b> {net(i.get('zh'))} "
                             f"<i>{net(i.get('pinyin'))}</i><br>{net(i.get('en'))}</p>"
                             for i in b.get("items") or [])
            out.append(f"<div class='dial'>{lignes}</div>")
        elif t == "exercise":
            out.append(f"<div class='ex'><p><b>Exercise {b.get('num')} — "
                       f"{net(b.get('title'))}</b></p>")
            for interne in b.get("blocks") or []:
                bloc(interne)
            out.append("</div>")

    for b in lecon.get("blocks") or []:
        bloc(b)
    return "".join(out)


def a_laveugle(resultats, n):
    """Deux pages étiquetées A et B, la correspondance dans un fichier à part."""
    etiquettes = "ABCDEFGH"
    cle = {}
    for i, (nom, dossier) in enumerate(resultats):
        fichier = dossier / "lecon.json"
        if not fichier.exists():
            continue
        lecon = json.loads(fichier.read_text(encoding="utf-8"))
        etiquette = etiquettes[i]
        (SORTIE / f"{etiquette}.html").write_text(
            PAGE.format(etiquette=etiquette, corps=rendre(lecon)), encoding="utf-8")
        cle[etiquette] = nom
    (SORTIE / "cle.json").write_text(json.dumps(cle, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    return cle


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lecon", type=int, required=True)
    ap.add_argument("--modeles", default="claude-opus-5,claude-sonnet-5")
    ap.add_argument("--tours", type=int, default=1,
                    help="tirages par modèle : un seul ne dit rien de la variance")
    ap.add_argument("--max-tokens", type=int, default=32000)
    ap.add_argument("--simuler", action="store_true",
                    help="note ce qui est déjà là, sans appeler l'API")
    a = ap.parse_args()

    modeles = [m.strip() for m in a.modeles.split(",") if m.strip()]
    SORTIE.mkdir(parents=True, exist_ok=True)
    resultats = []

    for modele in modeles:
        for tour in range(1, a.tours + 1):
            nom = slug(modele, tour)
            dossier = SORTIE / nom
            if a.simuler:
                dossier.mkdir(parents=True, exist_ok=True)
                source = GENERE / f"lecon_{a.lecon:02d}.json"
                if source.exists() and not (dossier / "lecon.json").exists():
                    shutil.copy2(source, dossier / "lecon.json")
                print(f"  {nom} : noté sans appel au modèle")
            else:
                print(f"  {nom} : écriture de la leçon {a.lecon}…", flush=True)
                ok, journal = produire(a.lecon, modele, tour, a.max_tokens)
                if not ok:
                    print(f"    échec : {journal.strip().splitlines()[-1][:120]}")
            resultats.append((nom, dossier))

    cle = a_laveugle(resultats, a.lecon)

    print(f"\n  leçon {a.lecon} — {len(resultats)} versions\n")
    entete = (f"  {'version':18} {'jetons':>14} {'coût':>8} {'durée':>7} "
              f"{'écarts':>7} {'répét.':>7} {'vocab.':>8}")
    print(entete)
    print("  " + "-" * (len(entete) - 2))
    for nom, dossier in resultats:
        d = noter(a.lecon, dossier)
        if "echec" in d:
            print(f"  {nom:18} {d['echec']}")
            continue
        modele = "claude-" + nom.rsplit("-", 1)[0]
        dollars = tarifs.cout(d["entree"], d["sortie"], modele)
        enseignes, total = d["vocabulaire"]
        print(f"  {nom:18} {d['entree']:>6}/{d['sortie']:<7} {dollars:>7.3f}$ "
              f"{d['duree']:>6}s {len(d['remarques']):>7} {d['repetition']:>6.1%} "
              f"{enseignes:>4}/{total:<3}")
        for r in d["remarques"]:
            print(f"      {r}")

    print(f"\n  à lire à l'aveugle : {SORTIE}/A.html, {SORTIE}/B.html")
    print(f"  la correspondance n'est pas dedans : {SORTIE}/cle.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
