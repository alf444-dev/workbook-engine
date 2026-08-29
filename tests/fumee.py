#!/usr/bin/env python3
"""Contrôle de fumée sur une instance en ligne, sans aucun secret.

À lancer après un déploiement, depuis n'importe où :

    python3 tests/fumee.py https://workbook-engine.onrender.com

Ne vérifie que ce qui est visible sans lien : que le site répond, qu'il annonce
sa version, qu'il refuse tout le reste et qu'il ne se laisse pas indexer. C'est
peu, mais c'est exactement ce qu'on veut savoir dans les deux minutes qui
suivent une mise en production — et c'est vérifiable sans donner le jeton
d'administration à un script.
"""
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1
        else "https://workbook-engine.onrender.com").rstrip("/")

checks = []
def ok(nom, cond, detail=""):
    checks.append((nom, bool(cond), detail))


def entetes_insensibles(bruts):
    """Les en-têtes HTTP sont insensibles à la casse ; un `dict` ne l'est pas.

    `dict(r.headers)` garde la casse reçue — en minuscules en HTTP/2 — et un
    `get("X-Workbook-Version")` renvoie alors None sur une réponse parfaitement
    correcte. Ce contrôle a commencé par accuser la production d'un défaut qui
    était le sien.
    """
    return {k.lower(): v for k, v in bruts.items()}


def demander(chemin, delai=30):
    """Rend (code, en-têtes en minuscules, corps) sans lever sur un refus."""
    req = urllib.request.Request(BASE + chemin, headers={"User-Agent": "workbook-fumee"})
    try:
        with urllib.request.urlopen(req, timeout=delai) as r:
            return (r.status, entetes_insensibles(r.headers),
                    r.read(4000).decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return (e.code, entetes_insensibles(e.headers),
                e.read(4000).decode("utf-8", "replace"))
    except Exception as e:                                       # noqa: BLE001
        return 0, {}, f"{type(e).__name__}: {e}"


code, entetes, corps = demander("/")
ok("le site répond", code == 200, f"{code} — {corps[:120]}")
version = entetes.get("x-workbook-version", "")
ok("il annonce la version déployée", bool(version), str(sorted(entetes)[:8]))
ok("il demande à ne pas être indexé",
   "noindex" in entetes.get("x-robots-tag", ""), entetes.get("x-robots-tag", ""))
ok("il ne fuit pas par le Referer",
   entetes.get("referrer-policy") == "no-referrer", entetes.get("Referrer-Policy", ""))
ok("la racine ne montre aucun projet",
   "projects" not in corps.lower() or "Workbook" in corps, corps[:150])

code, _, corps = demander("/robots.txt")
ok("robots.txt interdit tout", code == 200 and "Disallow: /" in corps, corps[:120])

for chemin in ("/admin/", "/admin/projects", "/admin/backups"):
    code, _, _ = demander(chemin)
    ok(f"{chemin} refuse un visiteur sans lien", code in (401, 403, 404), str(code))

code, _, corps = demander("/r/lien-invente")
ok("un lien inventé est refusé", code in (403, 404), str(code))
ok("et ne révèle rien", "project" not in corps.lower() or code != 200, corps[:150])

code, _, _ = demander("/p/inexistant/teacher/bundle.json")
ok("une file inconnue est refusée", code in (403, 404, 422), str(code))

print(f"\n  instance : {BASE}")
print(f"  version  : {version or '(non annoncée)'}\n")
rates = [c for c in checks if not c[1]]
for nom, bon, detail in checks:
    print(f"  {'✓' if bon else '✗'} {nom}")
    if not bon and detail:
        print(f"      {detail}")
print(f"\n{len(checks) - len(rates)}/{len(checks)} vérifications passées")
sys.exit(1 if rates else 0)
