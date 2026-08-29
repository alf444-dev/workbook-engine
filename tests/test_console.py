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

# ---------------------------------------------------------------- ce qu'on voit en attendant
# Trois situations très différentes pour un professeur à qui on envoie le lien
# trop tôt, ou dont le livre a échoué, ou dont le lien a été renouvelé.
ok("les trois situations ont chacune leur message",
   "This link no longer works" in js and "could not be built" in js
   and "still being built" in js, "un livre en échec s'annonçait « en cours »")
ok("seule une compilation en cours se recharge toute seule",
   re.search(r"if \(!perime && !rate\)[\s\S]{0,80}location\.reload", js) is not None,
   "un livre en échec rechargerait indéfiniment")
ok("le nom d'étape en français n'est pas montré au relecteur",
   "j.step" in js and "Step ${etape[1]} of ${etape[2]}" in js,
   "les libellés du pipeline sont relayés tels quels")

RUN = (REPO / "run.sh").read_text(encoding="utf-8")
etapes = re.findall(r'echo "(\d)/7\s+([^"]+)"', RUN)
ok("les étapes affichées sur le site sont en anglais", len(etapes) == 7, str(etapes))
FRANCAIS = ("é", "è", "ê", "à", "ç", "ô", "û", "î")
fautives = [t for _, t in etapes if any(c in t for c in FRANCAIS)]
ok("aucune ne contient d'accent français", not fautives, str(fautives))

# ---------------------------------------------------------------- vitesse et défilement
ok("une décision ne reconstruit pas la file entière",
   "carte.outerHTML = cardHTML(it)" in js,
   "reconstruire 465 cartes coûtait 75 ms par touche")
ok("les compteurs se mettent à jour séparément de la liste",
   "function majCompteurs(" in js and js.count("majCompteurs()") >= 2)
ok("aucun défilement animé ne subsiste",
   "behavior:'smooth'" not in js and "behavior: 'smooth'" not in js,
   "des défilements lisses successifs s'annulent entre eux")

# ---------------------------------------------------------------- schéma périmé
ok("la console sait annoncer un livre au numérotage périmé",
   'id="ids-perimes"' in CONSOLE and "DATA.ids_perimes" in js,
   "le marqueur id_scheme n'était lu par personne")

# ---------------------------------------------------------------- palette cohérente
# Un `var(--x)` non défini ne casse rien de visible dans les outils : le bloc
# s'affiche simplement sans fond. C'est arrivé avec une variable empruntée à
# l'autre page.
for page in ("console.html", "admin.html"):
    html = (REPO / "webapp" / page).read_text(encoding="utf-8")
    definies = set(re.findall(r"(--[a-z0-9-]+)\s*:", html))
    utilisees = set(re.findall(r"var\((--[a-z0-9-]+)", html))
    manquantes = sorted(utilisees - definies)
    ok(f"{page} n'utilise aucune variable CSS non définie", not manquantes,
       str(manquantes))

# ---------------------------------------------------------------- servie par le serveur
ok("la page autonome porte l'emplacement du bundle", "__BUNDLE__" in CONSOLE)
ok("le serveur y met null pour que la page aille le chercher",
   'replace("__BUNDLE__", "null")' in APP)
ok("les raccourcis ne sont pas annoncés sur un écran tactile",
   "(hover: none) and (pointer: coarse)" in CONSOLE,
   "un téléphone n'a pas de clavier")
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
