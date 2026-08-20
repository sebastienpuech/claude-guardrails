"""Hook SessionStart : injecte l'etat courant du projet depuis journal.md.

Audit forfait du 2026-08-19 : sur le top-40 des sessions, 88 % du cache_write est du
RECHAUFFAGE (~24 % de la facture 60 jours). Mecanique du gaspillage : une session fraiche
demarre aveugle, Sebastien re-explique ou on en est, et cette re-explication EST le
rechauffage. La convention journal.md existait deja (un-autre-projet, un-second-projet,
un-projet) mais seul le cote ECRITURE etait tenu : le fichier n'etait relu que si
quelqu'un pensait a le demander. Ce hook automatise le cote LECTURE.

Ce qui est injecte : le seul bloc « Etat actuel (glissant) », plus les titres des 3
dernieres entrees du log. PAS le journal entier - celui de un-autre-projet fait 80 Ko
(~20 000 tokens) : l'injecter a chaque demarrage couterait plus cher que le probleme
qu'il resout. Le log complet reste sur disque, lisible a la demande.

DEROGATION DECLAREE au principe 1 (fail-closed) de doctrine.md, meme raison que
inject_lecons.py : ce hook INFORME, il ne garde rien. Un injecteur casse qui empecherait
une session de demarrer serait pire que le mal qu'il soigne. Il sort toujours en 0.

Parseur duplique depuis inject_lecons.py (doctrine #11, two-copy trap assume) : meme
repo, mais un import croise entre hooks rendrait chacun dependant de l'autre pour
demarrer - exactement ce qu'on ne veut pas d'un fail-open.
"""
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

PLAFOND_CAR = 8000   # au-dela, on tronque : un bloc d'etat qui enfle redevient le probleme
DERNIERES = 3        # titres d'entrees recentes cites en plus de l'etat
CANDIDATS = ("journal.md", "docs/journal.md")
TITRE_ETAT = re.compile(r"^##\s+(.*)$", re.M)
TITRE_ENTREE = re.compile(r"^###\s+(.+?)\s*$", re.M)


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


def _sans_accent(texte: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn"
    ).lower()


def trouver_journal(racine: Path):
    for rel in CANDIDATS:
        chemin = racine / rel
        if chemin.is_file():
            return chemin
    return None


def bloc_etat(texte: str) -> str:
    """Renvoie la section '## Etat actuel' (ou, a defaut, la premiere section '##')."""
    titres = list(TITRE_ETAT.finditer(texte))
    if not titres:
        return ""
    choisi = None
    for m in titres:
        if "etat actuel" in _sans_accent(m.group(1)):
            choisi = m
            break
    if choisi is None:
        choisi = titres[0]
    debut = choisi.start()
    suivants = [m.start() for m in titres if m.start() > debut]
    fin = suivants[0] if suivants else len(texte)
    return texte[debut:fin].strip()


def tronquer(bloc: str) -> str:
    if len(bloc) <= PLAFOND_CAR:
        return bloc
    coupe = bloc[:PLAFOND_CAR].rsplit("\n", 1)[0]
    return coupe + "\n[...] Bloc d'etat tronque ({} car au total) - lire le fichier en entier.".format(
        len(bloc)
    )


def contexte(racine: Path) -> str:
    chemin = trouver_journal(racine)
    if chemin is None:
        return ""
    try:
        texte = chemin.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    bloc = bloc_etat(texte)
    if not bloc:
        return ""
    rel = chemin.relative_to(racine).as_posix()
    lignes = [
        "Etat du projet repris de `{}` (memoire fichier-residente : elle survit a une "
        "compaction, pas le contexte). A jour a la derniere session ecrite ; verifier "
        "`git log` avant d'en tirer un constat d'etat.".format(rel),
        "",
        tronquer(bloc),
    ]
    recentes = TITRE_ENTREE.findall(texte)[:DERNIERES]
    if recentes:
        lignes += ["", "Dernieres entrees du log ({}) :".format(rel)]
        lignes += ["- " + t for t in recentes]
    lignes.append("")
    lignes.append(
        "En fin de session : mettre a jour le bloc « Etat actuel » et ajouter une entree "
        "datee en tete du log. Ce qui n'est pas ecrit la sera re-explique a la main "
        "demain - c'est ce rechauffage qui coute."
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
