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
import json, os, re, shutil, subprocess, threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CODE = ("pipeline", "templates", "webapp", "config")   # copiés à chaque exécution
DATA = Path(os.environ.get("WB_DATA") or REPO / "data")

# Rapports produits à la racine de l'espace de travail par le pipeline.
REPORTS = ("validation_report.txt", "exercise_report.txt", "answerkey_diff.txt",
           "decisions_report.txt")


# Un identifiant de projet est un jeton hexadécimal (`secrets.token_hex`). Le
# vérifier ici plutôt qu'à chaque appelant : `DATA / "projects" / "../.."` sort
# du disque de données, et il suffirait d'un futur point d'entrée qui oublie de
# valider. Les manuscrits sont privés ; cette porte-là reste fermée.
RE_PID = re.compile(r"\A[0-9a-f]{4,64}\Z")


def workspace(pid):
    if not RE_PID.match(str(pid or "")):
        raise ValueError(f"identifiant de projet invalide : {pid!r}")
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


# Un `.docx` pathologique, ou une compilation Typst qui ne converge pas, ne
# doivent pas laisser un projet « running » pour toujours : la tâche de fond
# n'a aucun autre moyen de s'arrêter. Le CN10 complet prend 20 s ; quinze
# minutes couvrent un manuscrit dix fois plus gros. Une génération de leçon
# dure 3 min ; le délai d'un script est plus large.
DELAI_RUN = int(os.environ.get("WB_TIMEOUT_RUN", "900"))
DELAI_SCRIPT = int(os.environ.get("WB_TIMEOUT_SCRIPT", "1800"))


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
    # On lit la sortie ligne à ligne pour la progression : un blocage se
    # manifesterait par une lecture qui n'aboutit jamais. Le chien de garde
    # tue le processus, ce qui ferme le tube et libère la lecture.
    expire = {"oui": False}
    def tuer():
        expire["oui"] = True
        proc.kill()
    garde = threading.Timer(DELAI_RUN, tuer)
    garde.start()
    try:
        for line in proc.stdout:
            lines.append(line.rstrip())
            if on_step and len(line) > 3 and line[1] == "/":
                on_step(line.strip())
        code = proc.wait()
    finally:
        garde.cancel()
    if expire["oui"]:
        lines.append(f"[stopped after {DELAI_RUN} s — the manuscript or its typesetting"
                     f" did not finish in time]")
        return False, "\n".join(lines)
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
    try:
        r = subprocess.run(["python3"] + args, cwd=workspace(pid), env=env,
                           capture_output=True, text=True, timeout=DELAI_SCRIPT)
    except subprocess.TimeoutExpired as e:
        sortie = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        return False, (f"$ {' '.join(args)}\n{sortie}\n[stopped after {DELAI_SCRIPT} s"
                       f" — the step did not finish in time]")
    return r.returncode == 0, f"$ {' '.join(args)}\n{r.stdout}{r.stderr}"


def proposer_vocabulaire(pid, langue, projet):
    """Fait proposer la progression, puis reconstruit les files de relecture
    pour que le professeur ait quelque chose à ouvrir."""
    ok, journal = lancer(pid, ["pipeline/propose_vocab.py"], langue, projet)
    if not ok:
        return False, journal
    ok2, j2 = lancer(pid, ["pipeline/bundle.py"], langue, projet)
    return ok2, journal + "\n" + j2


def valider_vocabulaire(pid, langue, projet, decisions):
    """Décisions du professeur → curriculum validé → plan mis à jour.

    Ce maillon manquait : `apply_vocab.py` était écrit, testé et documenté, mais
    aucun endroit ne l'appelait, et `plan.py` ne tournait qu'une fois, avant même
    que le vocabulaire soit proposé. La validation du professeur n'atteignait
    donc jamais la génération — un livre entier a été écrit sans elle.
    """
    ws = workspace(pid)
    (ws / "content").mkdir(parents=True, exist_ok=True)
    (ws / "content" / "decisions.json").write_text(
        json.dumps(decisions, ensure_ascii=False, indent=1), encoding="utf-8")

    ok, journal = lancer(pid, ["pipeline/apply_vocab.py"], langue, projet)
    if not ok:
        return False, journal
    # Le plan est refait : c'est lui que lit la génération, pas le curriculum.
    ok2, j2 = lancer(pid, ["pipeline/plan.py",
                           "--config", f"config/{langue}.json",
                           "--titres", "content/titres.txt"], langue, projet)
    return ok2, journal + "\n" + j2


def vocabulaire_du_plan(pid):
    """Combien d'entrées le plan impose, toutes leçons confondues.

    Zéro signifie que le modèle choisira lui-même ce qu'il enseigne — et, quand
    la référence est dans une autre langue, qu'il n'a aucun ancrage dans la
    langue cible. C'est ce qui a donné trente leçons de chinois dans un livre
    de japonais.
    """
    import json as _json
    chemin = workspace(pid) / "content" / "plan.json"
    if not chemin.exists():
        return 0
    plan = _json.loads(chemin.read_text(encoding="utf-8"))
    return sum(len(l.get("vocabulaire") or []) for l in plan["lecons"])


def controler_generation(pid, langue, projet):
    """Tous les contrôles qui ne coûtent rien, avant d'en lancer un qui coûte."""
    ok, journal = lancer(pid, ["pipeline/check_generation.py"], langue, projet)
    lignes = [l.rstrip() for l in journal.splitlines()
              if l.strip().startswith(("✓", "✗")) or l.startswith("      ")]
    # Un contrôle qui ne rend rien du tout est un contrôle qui a planté : montrer
    # la fin du journal plutôt qu'une liste vide, qui se lirait « tout va bien ».
    if not lignes:
        fin = [l for l in journal.strip().splitlines() if l.strip()][-4:]
        lignes = ["✗ the checks could not be run"] + [f"      {l}" for l in fin]
        return False, lignes
    return ok, lignes


def oublier_lecon(pid, n):
    """Efface une leçon produite pour qu'elle soit réécrite.

    La sortie brute est conservée : elle permet de revenir en arrière si la
    nouvelle version est moins bonne que celle qu'on remplace.
    """
    genere = workspace(pid) / "content" / "generated"
    fichier = genere / f"lecon_{n:02d}.json"
    if fichier.exists():
        garde = genere / f"lecon_{n:02d}_precedente.json"
        fichier.replace(garde)
        return True
    return False


def titres_du_plan(pid):
    import json as _json
    chemin = workspace(pid) / "content" / "plan.json"
    if not chemin.exists():
        return []
    return [l["titre"] for l in _json.loads(chemin.read_text(encoding="utf-8"))["lecons"]]


# Des erreurs qui ne dépendent pas de la leçon : crédit épuisé, clé refusée,
# droits manquants. Les rejouer trente et une fois ne change rien et fait perdre
# une heure — c'est exactement ce qui s'est passé le 28 août 2026.
FATALES = ("credit balance is too low", "authentication_error", "permission_error",
           "invalid_x_api_key", "authenticationerror", "permissiondeniederror")

ECHECS_DE_SUITE = 3      # au-delà, le problème n'est plus la leçon


def cause_fatale(journal):
    bas = (journal or "").lower()
    return next((m for m in FATALES if m in bas), None)


def generer_lecons(pid, langue, projet, a_faire, sur_lecon):
    """Génère les leçons une par une, en rendant compte après chacune.

    Une leçon à la fois : la parallélisation a fait tomber la génération dans
    les limites de débit, et un livre qui met une heure de plus est préférable à
    un livre qui s'arrête sans rien dire. L'état vit en base, donc un
    redéploiement n'annule que la leçon en cours.

    S'arrête tôt quand l'erreur ne vient pas de la leçon. Renvoie la raison de
    l'arrêt, ou une chaîne vide si la série est allée jusqu'au bout ; les leçons
    non tentées restent à faire, donc « Resume » les reprendra.
    """
    import json as _json
    ws = workspace(pid)
    de_suite = 0
    for n in a_faire:
        sur_lecon(n, "en_cours", 0, 0, "")
        ok, journal = lancer(pid, ["pipeline/generate.py", "--lecon", str(n)],
                             langue, projet)
        recu = ws / "content" / "generated" / f"lecon_{n:02d}_recu.json"
        jetons = _json.loads(recu.read_text(encoding="utf-8")) if recu.exists() else {}
        if ok and (ws / "content" / "generated" / f"lecon_{n:02d}.json").exists():
            sur_lecon(n, "faite", jetons.get("entree", 0), jetons.get("sortie", 0), "")
            de_suite = 0
            continue

        derniere = [l for l in journal.strip().splitlines() if l.strip()]
        motif = derniere[-1] if derniere else "échec inconnu"
        sur_lecon(n, "echec", 0, 0, motif)
        if cause_fatale(journal):
            return motif
        de_suite += 1
        if de_suite >= ECHECS_DE_SUITE:
            return f"{de_suite} lessons failed in a row — {motif}"
    return ""


def assembler(pid, langue, projet):
    """Assemble les leçons générées, compile le livre et refait les files."""
    return lancer(pid, ["pipeline/assemble.py", "--rendre"], langue, projet)


def compter_vocabulaire(pid):
    """Combien d'entrées attendent le professeur, et combien il en a tranché."""
    import json as _json
    chemin = workspace(pid) / "content" / "vocabulaire_propose.json"
    if not chemin.exists():
        return 0
    v = _json.loads(chemin.read_text(encoding="utf-8"))
    return sum(len(l.get("entrees", [])) for l in v.get("lecons", []))


# Taille décompressée admise. Le plafond de 40 Mo porte sur le fichier reçu ;
# un zip peut se déplier mille fois plus gros et python-docx charge
# `document.xml` entier en mémoire. Un manuscrit de 240 pages fait 3 Mo
# décompressé ; 300 Mo laissent de la place aux images sans laisser rentrer
# une bombe.
DECOMPRESSE_MAX = 300 * 1024 * 1024


def est_docx(chemin):
    """Un .docx est un zip qui contient word/document.xml. On ne se fie ni au
    nom du fichier ni au type déclaré par le navigateur — ni à la taille du
    fichier : c'est la taille décompressée qu'on borne."""
    import zipfile
    try:
        with zipfile.ZipFile(chemin) as z:
            noms = z.namelist()
            if "word/document.xml" not in noms:
                return False
            if sum(i.file_size for i in z.infolist()) > DECOMPRESSE_MAX:
                return False
            return True
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
