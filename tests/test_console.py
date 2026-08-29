#!/usr/bin/env python3
"""La console de relecture : ce qu'elle promet doit exister.

C'est l'outil que des professeurs externes utilisent sans formation et sans
compte. On ne peut pas y faire tourner un navigateur ici, mais trois choses se
vérifient sans : que le script est syntaxiquement valide, que les invariants
d'ergonomie tenus à la main y sont toujours, et surtout que **chaque action
proposée par la page est acceptée par le serveur**.

Ce dernier point n'est pas théorique : la console a déjà annoncé un raccourci
« Remove » que le serveur refusait, et une file dont le texte promettait une
action absente des boutons.

    python3 tests/test_console.py
"""
import re, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONSOLE = (REPO / "webapp" / "console.html").read_text(encoding="utf-8")
APP = (REPO / "server" / "app.py").read_text(encoding="utf-8")

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


def scripts(html):
    return "\n".join(re.findall(
        r"<script(?![^>]*application/json)[^>]*>(.*?)</script>", html, re.S))


# ---------------------------------------------------------------- le script tient
js = scripts(CONSOLE)
ok("la console contient bien du script", len(js) > 2000, str(len(js)))
node = shutil.which("node")
if node:
    tmp = Path(tempfile.mkdtemp()) / "console.js"
    tmp.write_text(js, encoding="utf-8")
    r = subprocess.run([node, "--check", str(tmp)], capture_output=True, text=True)
    ok("son script est syntaxiquement valide", r.returncode == 0, r.stderr[-400:])
    shutil.rmtree(tmp.parent, ignore_errors=True)
else:
    ok("node absent : syntaxe non vérifiée", True)

# ---------------------------------------------------------------- actions promises
# Ce que la page peut envoyer.
envoyees = set(re.findall(r"decide\([^,]+,\s*'([a-z]+)'", js))
ok("la page envoie plusieurs actions", len(envoyees) >= 3, str(sorted(envoyees)))

# Ce que le serveur accepte.
m = re.search(r"^ACTIONS\s*=\s*\{([^}]*)\}", APP, re.M)
acceptees = set(re.findall(r'"([a-z]+)"', m.group(1))) if m else set()
ok("le serveur déclare la liste des actions acceptées", bool(acceptees),
   str(sorted(acceptees)))
ok("toutes les actions de la page sont acceptées par le serveur",
   envoyees <= acceptees, f"refusées : {sorted(envoyees - acceptees)}")
ok("et le serveur n'accepte rien que la page n'utilise",
   acceptees <= envoyees, f"jamais envoyées : {sorted(acceptees - envoyees)}")

# ---------------------------------------------------------------- champ de correction
ouvertures = re.findall(r"classList\.add\('open'\)", js)
ok("le champ de correction s'ouvre à un seul endroit",
   len(ouvertures) == 1, f"{len(ouvertures)} endroits — ils divergeront")
ok("les deux entrées (clic et clavier) passent par la même fonction",
   js.count("ouvrirCorrection(") >= 3, str(js.count("ouvrirCorrection(")))
# Deux corrections mesurées dans un vrai navigateur : sans elles, le champ
# s'ouvrait sous la barre fixe du bas et le relecteur tapait à l'aveugle.
ok("le focus ne défile pas de lui-même", "preventScroll: true" in js)
ok("et la page amène le champ à l'écran",
   "scrollIntoView" in js and "block: 'center'" in js)
ok("le calcul de mise en page est forcé avant de mesurer",
   "void box.offsetHeight" in js,
   "sans reflow, on défile vers une position périmée")

# ---------------------------------------------------------------- raccourcis annoncés
legende = set(re.findall(r"<kbd>([A-Z])</kbd>", CONSOLE))
ok("la légende annonce les déplacements et les décisions",
   {"J", "K", "A", "C", "S"} <= legende, str(sorted(legende)))
ok("« X remove » n'est annoncé que là où il agit",
   'id="foot-remove" hidden' in CONSOLE
   and "foot-remove').hidden" in js, "la légende promettrait une touche inerte")
ok("et la touche x ne s'applique qu'au vocabulaire",
   re.search(r"e\.key === 'x'[\s\S]{0,220}kind === 'vocabulaire'", js) is not None)

# ---------------------------------------------------------------- servie par le serveur
ok("la page autonome porte l'emplacement du bundle", "__BUNDLE__" in CONSOLE)
ok("le serveur y met null pour que la page aille le chercher",
   'replace("__BUNDLE__", "null")' in APP)
ok("la console n'est pas indexable", "noindex" in CONSOLE)
ok("elle se déclare en anglais, comme son contenu",
   '<html lang="en">' in CONSOLE, "un lecteur d'écran lirait l'anglais en français")

rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
