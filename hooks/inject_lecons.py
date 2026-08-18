"""Hook SessionStart : injecte les lecons du repo courant dans le contexte.

Moitie "relire" du skill `lecon-de-repo` (un depot de skills). Sans ce hook, les
fiches de docs/lecons/ existent mais ne sont lues que si Sebastien pense a demander
- c'est-a-dire au moment ou il se souvient deja de la lecon. Ici, la session demarre
en les connaissant.

DEROGATION DECLAREE au principe 1 (fail-closed) de doctrine.md : ce hook INFORME, il
ne verifie rien. Un injecteur casse qui bloquerait le demarrage d'une session serait
pire que le mal qu'il soigne. Il sort donc toujours en 0, silencieux en cas de doute.
Le fail-closed reste la regle pour les hooks qui gardent (block_*.py).

Parseur de frontmatter duplique depuis lecon.py (doctrine #11, two-copy trap assume) :
les deux fichiers vivent dans des repos differents, aucun import possible. 10 lignes,
re-testees des deux cotes.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

PLAFOND = 15  # au-dela, on cite le nombre restant plutot que d'inonder le contexte


def racine_git(depart: Path):
    try:
        p = subprocess.run(
            ["git", "-C", str(depart), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
        )
    except Exception:
        return None
    out = (p.stdout or "").strip()
    return Path(out) if p.returncode == 0 and out else None


def dossier_lecons(racine: Path) -> Path:
    return racine / "docs" / "lecons" if (racine / "docs").is_dir() else racine / "lecons"


def lire_frontmatter(path: Path) -> dict:
    fm = {}
    try:
        lignes = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return fm
    if not lignes or lignes[0].strip() != "---":
        return fm
    for ligne in lignes[1:]:
        if ligne.strip() == "---":
            break
        if ":" not in ligne:
            continue
        cle, _, val = ligne.partition(":")
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            fm[cle.strip()] = [v.strip() for v in val[1:-1].split(",") if v.strip()]
        else:
            fm[cle.strip()] = val
    return fm


def contexte(racine: Path) -> str:
    dossier = dossier_lecons(racine)
    if not dossier.is_dir():
        return ""
    actives = []
    for path in sorted(dossier.glob("*.md"), reverse=True):
        fm = lire_frontmatter(path)
        if not fm or str(fm.get("statut", "")).startswith("supersede-par:"):
            continue
        tags = fm.get("tags") or []
        actives.append(
            "- {titre} [{type}{tags}] - {fichier}".format(
                titre=fm.get("titre", path.stem),
                type=fm.get("type", "?"),
                tags=(" : " + ", ".join(tags)) if tags else "",
                fichier=path.name,
            )
        )
    if not actives:
        return ""
    tete, reste = actives[:PLAFOND], len(actives) - PLAFOND
    lignes = [
        f"Lecons deja payees dans ce repo ({len(actives)}), a lire AVANT de proposer une "
        f"architecture, un plan ou un correctif. Fiches completes dans {dossier.name}/ :",
        *tete,
    ]
    if reste > 0:
        lignes.append(f"- (+{reste} autres - `lecon.py liste` pour tout voir)")
    lignes.append(
        "Une fiche qui contredit ce que tu t'appretes a proposer se cite explicitement, "
        "elle ne se contourne pas en silence."
    )
    return "\n".join(lignes)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    depart = Path(data.get("cwd") or os.getcwd())
    racine = racine_git(depart)
    if racine is None:
        return 0
    texte = contexte(racine)
    if not texte:
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": texte,
        }
    }, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # un injecteur ne fait jamais tomber une session
        sys.exit(0)
