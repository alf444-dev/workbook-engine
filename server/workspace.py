#!/usr/bin/env python3
"""Workbook Engine — un espace de travail isolé par projet.

`run.sh` écrit dans des chemins relatifs fixes (`content/`, `output/`, les
rapports à la racine). Deux projets compilés en même temps s'écraseraient. On
lui donne donc son propre répertoire courant par projet.

Le code est **copié**, pas lié : `typst compile --root .` refuse un fichier
source qui sort de la racine (« source file must be contained in project root »),
donc un templates/ en lien symbolique fait échouer la compilation. Les polices,
elles, passent par `--font-path`, qui n'est pas soumis à cette contrainte : on
les lie, ce qui évite de dupliquer 18 Mo par projet.

`run.sh` n'est pas modifié : il est simplement lancé depuis cet espace.
"""
import json, os, shutil, subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CODE = ("pipeline", "templates", "webapp", "config")   # copiés à chaque exécution
DATA = Path(os.environ.get("WB_DATA") or REPO / "data")

# Rapports produits à la racine de l'espace de travail par le pipeline.
REPORTS = ("validation_report.txt", "exercise_report.txt", "answerkey_diff.txt",
           "decisions_report.txt")


def workspace(pid):
    return DATA / "projects" / pid


def prepare(pid):
    """Reconstruit l'espace de travail avec la version courante du code."""
    ws = workspace(pid)
    (ws / "input").mkdir(parents=True, exist_ok=True)
    for d in CODE:
        dst = ws / d
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(REPO / d, dst,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(REPO / "run.sh", ws / "run.sh")
    os.chmod(ws / "run.sh", 0o755)
    fonts = ws / "fonts"
    if not fonts.exists():
        fonts.symlink_to(REPO / "fonts")
    return ws


def environment():
    """PATH complété des binaires locaux quand ils existent (poste de dev).
    En production, python3 et typst sont déjà sur le PATH de l'image."""
    env = dict(os.environ)
    extra = [p for p in (REPO / ".bin", REPO / ".venv" / "bin") if p.exists()]
    if extra:
        env["PATH"] = os.pathsep.join([str(p) for p in extra] + [env.get("PATH", "")])
    return env


def run(pid, docx, project_name, on_step=None, decisions=None):
    """Lance ./run.sh sur le manuscrit. Rend (succès, journal).

    `on_step` reçoit chaque ligne « n/7 … » pour la progression.
    `decisions` est déposé en content/decisions.json et rejoué par le pipeline
    juste après la conversion.
    """
    ws = prepare(pid)
    if decisions is not None:
        (ws / "content").mkdir(parents=True, exist_ok=True)
        (ws / "content" / "decisions.json").write_text(
            json.dumps(decisions, ensure_ascii=False, indent=1), encoding="utf-8")
    src = ws / "input" / Path(docx).name
    if Path(docx).resolve() != src.resolve():
        shutil.copy2(docx, src)

    env = environment()
    env["WB_PROJECT"] = project_name
    lines = []
    proc = subprocess.Popen(
        ["./run.sh", f"input/{src.name}"], cwd=ws, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in proc.stdout:
        lines.append(line.rstrip())
        if on_step and len(line) > 3 and line[1] == "/":
            on_step(line.strip())
    code = proc.wait()
    return code == 0, "\n".join(lines)


MESURES = ("profile.json", "glossary.json", "style.json")


def transposer_titres(titres, source, cible):
    """« How Chinese actually works » → « How Japanese actually works ».

    Les sujets d'un manuel de langue se transportent : seul le nom de la langue
    change dans les titres. Le reste — se présenter, les nombres, l'heure,
    commander — vaut pour n'importe quelle langue.
    """
    import re
    if not source or not cible:
        return list(titres)

    def rempl(m):
        mot = m.group(0)
        return cible.upper() if mot.isupper() else cible

    return [re.sub(rf"\b{re.escape(source)}\b", rempl, t, flags=re.I) for t in titres]


def preparer_generation(pid, reference_pid, langue):
    """Espace de travail d'un livre généré : le code, la config, et le livre de
    référence dont on tirera profil, glossaire et style."""
    ws = prepare(pid)
    (ws / "content").mkdir(parents=True, exist_ok=True)
    source = workspace(reference_pid) / "content" / "book_typed.json"
    if not source.exists():
        raise FileNotFoundError(
            "le projet de référence n'a pas de livre analysé : le compiler d'abord")
    shutil.copy2(source, ws / "content" / "book_typed.json")
    return ws


def mesurer_et_planifier(pid, langue, langue_reference, on_step=None):
    """Mesure le livre de référence, puis planifie dans la langue cible.

    Aucun appel à un modèle : tout est déterministe, donc gratuit et instantané.
    """
    ws = workspace(pid)
    env = environment()
    env["WB_LANGUE"] = langue_reference        # on mesure le livre tel qu'il est
    journal = []
    for libelle, script in (("mesure du profil", "lesson_profile.py"),
                            ("glossaire de référence", "glossary.py"),
                            ("voix maison", "style.py")):
        if on_step:
            on_step(libelle)
        r = subprocess.run(["python3", f"pipeline/{script}"], cwd=ws, env=env,
                           capture_output=True, text=True)
        journal.append(f"$ {script}\n{r.stdout}{r.stderr}")
        if r.returncode:
            return False, "\n".join(journal)

    # Les titres passent dans la langue cible avant la planification.
    import json as _json
    profil = _json.loads((ws / "content" / "profile.json").read_text(encoding="utf-8"))
    titres = [l["titre"] for l in profil["detail"] if l["genre"] == "chapter"]
    conf_source = _json.loads((ws / "config" / f"{langue_reference}.json").read_text(encoding="utf-8"))
    conf_cible = _json.loads((ws / "config" / f"{langue}.json").read_text(encoding="utf-8"))
    titres = transposer_titres(titres, conf_source.get("nom_anglais"),
                               conf_cible.get("nom_anglais"))
    fichier = ws / "content" / "titres.txt"
    fichier.write_text("\n".join(titres) + "\n", encoding="utf-8")

    if on_step:
        on_step("plan du livre")
    env["WB_LANGUE"] = langue
    r = subprocess.run(["python3", "pipeline/plan.py",
                        "--config", f"config/{langue}.json",
                        "--titres", "content/titres.txt"],
                       cwd=ws, env=env, capture_output=True, text=True)
    journal.append(f"$ plan.py\n{r.stdout}{r.stderr}")

    # Le livre de référence a livré ses mesures ; on l'écarte pour que les files
    # de relecture du nouveau projet ne montrent pas les items de l'ancien.
    livre = ws / "content" / "book_typed.json"
    if livre.exists():
        livre.rename(ws / "content" / "reference_typed.json")
    return r.returncode == 0, "\n".join(journal)


def lancer(pid, args, langue=None, projet=None):
    """Lance un script du pipeline dans l'espace du projet."""
    env = environment()
    if langue:
        env["WB_LANGUE"] = langue
    if projet:
        env["WB_PROJECT"] = projet
    r = subprocess.run(["python3"] + args, cwd=workspace(pid), env=env,
                       capture_output=True, text=True)
    return r.returncode == 0, f"$ {' '.join(args)}\n{r.stdout}{r.stderr}"


def proposer_vocabulaire(pid, langue, projet):
    """Fait proposer la progression, puis reconstruit les files de relecture
    pour que le professeur ait quelque chose à ouvrir."""
    ok, journal = lancer(pid, ["pipeline/propose_vocab.py"], langue, projet)
    if not ok:
        return False, journal
    ok2, j2 = lancer(pid, ["pipeline/bundle.py"], langue, projet)
    return ok2, journal + "\n" + j2


def compter_vocabulaire(pid):
    """Combien d'entrées attendent le professeur, et combien il en a tranché."""
    import json as _json
    chemin = workspace(pid) / "content" / "vocabulaire_propose.json"
    if not chemin.exists():
        return 0
    v = _json.loads(chemin.read_text(encoding="utf-8"))
    return sum(len(l.get("entrees", [])) for l in v.get("lecons", []))


def est_docx(chemin):
    """Un .docx est un zip qui contient word/document.xml. On ne se fie ni au
    nom du fichier ni au type déclaré par le navigateur."""
    import zipfile
    try:
        with zipfile.ZipFile(chemin) as z:
            return "word/document.xml" in z.namelist()
    except (zipfile.BadZipFile, OSError):
        return False


def artifact(pid, name):
    """Chemin d'un livrable, ou None. Refuse tout ce qui sort de l'espace."""
    ws = workspace(pid).resolve()
    known = {"book.pdf": ws / "output" / "book.pdf",
             "review.json": ws / "output" / "review.json",
             "console.html": ws / "output" / "console.html"}
    known.update({r: ws / r for r in REPORTS})
    p = known.get(name)
    return p if p and p.exists() else None
