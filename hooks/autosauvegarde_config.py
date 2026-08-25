"""Hook Stop : snapshot local de la config Claude Code des qu'elle change.

Incident du 21/08/2026 : un deploiement a ecrase deux hooks dont le travail n'etait
pas commite. Il a fallu les reconstituer a la main dans les transcripts. Ce hook est
le filet : a chaque fin de tour, tout fichier de config dont le contenu a change
depuis le dernier snapshot est COPIE dans ~/.claude/.sauvegardes/auto/<horodatage>/.

Ce n'est pas la correction a la cause racine - celle-la est dans deploy.ps1, qui
sauvegarde desormais toute cible avant de l'ecraser. Ce hook couvre le reste :
edition manuelle ecrasee, session parallele, outil tiers.

Design NON DESTRUCTIF, delibere. La suggestion d'origine (rapport d'usage du
24/08/2026) proposait `git stash push -u .claude/`. Deux defauts : `stash` RETIRE
les modifications du repertoire de travail - un hook de fin de tour ferait donc
disparaitre le travail en cours - et ~/.claude n'est pas un depot git, la commande
y echouerait de toute facon. On copie, on ne deplace jamais.

DEROGATION DECLAREE au principe 1 (fail-closed) : ce hook SAUVEGARDE, il ne verifie
rien et ne bloque rien. Il sort toujours en 0. Un filet casse ne doit jamais
interrompre une session.
"""
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

CIBLE = Path.home() / ".claude"

# Nombre de snapshots conserves. Au-dela, les plus anciens sont supprimes.
MAX_SNAPSHOTS = 30

# Config dont la perte coute une reconstitution a la main.
FICHIERS = ("CLAUDE.md", "settings.json", "settings.local.json")


def fichiers_surveilles(cible):
    vus = [cible / nom for nom in FICHIERS]
    vus = [c for c in vus if c.is_file()]
    dossier_hooks = cible / "hooks"
    if dossier_hooks.is_dir():
        vus.extend(sorted(dossier_hooks.glob("*.py")))
    return vus


def _empreinte(chemin):
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def _charge_etat(fichier_etat):
    try:
        return json.loads(fichier_etat.read_text(encoding="utf-8"))
    except Exception:
        # Etat absent ou corrompu : on repart de zero. Le premier passage
        # sauvegarde tout, ce qui est le comportement sur.
        return {}


def _rotation(dossier_auto):
    # Tri par date de modification, pas par nom : un nom de dossier hors format
    # (reprise a la main, restauration) ferait supprimer les mauvais snapshots.
    # Le nom departage les ex aequo, quand plusieurs snapshots tombent dans la
    # meme fraction de seconde.
    snapshots = sorted(
        (p for p in dossier_auto.iterdir() if p.is_dir()),
        key=lambda p: (p.stat().st_mtime, p.name),
    )
    for vieux in snapshots[:-MAX_SNAPSHOTS]:
        shutil.rmtree(vieux, ignore_errors=True)


def snapshot(cible, horodatage=None):
    """Copie tout fichier surveille dont le contenu a change. Rend la liste des cles.

    Ne deplace, ne supprime, ne modifie jamais un fichier surveille : le repertoire
    de travail reste intact, c'est tout l'interet par rapport a un `git stash`.
    """
    dossier_auto = cible / ".sauvegardes" / "auto"
    fichier_etat = cible / ".sauvegardes" / "empreintes.json"
    etat = _charge_etat(fichier_etat)

    a_copier = []
    for chemin in fichiers_surveilles(cible):
        try:
            actuelle = _empreinte(chemin)
        except Exception:
            continue
        cle = chemin.relative_to(cible).as_posix()
        if etat.get(cle) != actuelle:
            a_copier.append((cle, chemin, actuelle))

    if not a_copier:
        return []

    horodatage = horodatage or datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dossier = dossier_auto / horodatage
    for cle, chemin, actuelle in a_copier:
        destination = dossier / cle
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(chemin, destination)
        etat[cle] = actuelle

    fichier_etat.parent.mkdir(parents=True, exist_ok=True)
    fichier_etat.write_text(json.dumps(etat, indent=2, sort_keys=True), encoding="utf-8")
    _rotation(dossier_auto)
    return [cle for cle, _, _ in a_copier]


def main():
    # Le payload n'est pas utilise, mais on le consomme : un hook qui ne lit pas
    # stdin peut faire bloquer l'ecriture cote appelant.
    try:
        sys.stdin.read()
    except Exception:
        pass
    snapshot(CIBLE)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Un filet qui plante ne casse pas la session : il se tait.
        sys.exit(0)
