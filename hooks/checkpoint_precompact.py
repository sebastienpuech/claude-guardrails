"""Hook PreCompact : ecrit un point d'etape sur disque AVANT chaque compaction.

Probleme mesure (audit forfait 2026-08-19) : la compaction resume 120-200k tokens en
~4k. Elle garde l'essentiel, mais ce qui n'existait QUE dans la conversation (une
decision orale, un chiffre, un arbitrage) peut disparaitre. Seul remede : que ca vive
dans un fichier. Ce hook le fait tout seul, sans rien demander a personne.

Purement mecanique — extraction, pas resume (CLAUDE.md global : « le mecanique va dans
un script deterministe, pas dans un appel LLM »). Il recopie :
  - toutes les demandes utilisateur (verbatim) = l'intention, ce qu'un resume delave ;
  - les fichiers touches (Edit/Write) et les commandes shell ;
  - de quoi retrouver la session complete (chemin du transcript .jsonl).

Sortie : ~/.claude/checkpoints/AAAA-MM-JJ_HHMM_<session>.md

DEROGATION ASSUMEE a doctrine.md principe 1 (fail-closed) : ce hook n'est pas un
verifieur, c'est un scribe. S'il plante, il ne doit PAS bloquer la compaction — sinon
une session longue devient impossible a compacter. Donc fail-open, exit 0 toujours,
l'erreur est ecrite dans le fichier d'echec pour etre vue.

Confidentialite : le fichier contient les messages verbatim. Il reste local dans
~/.claude/checkpoints/, jamais versionne, jamais recopie ailleurs.
"""
import datetime
import json
import os
import sys
from pathlib import Path

DOSSIER = Path.home() / ".claude" / "checkpoints"
MAX_MESSAGES = 40        # les 40 dernieres demandes suffisent a rebrancher un fil
MAX_CAR_MESSAGE = 1200   # au-dela, une demande est tronquee (elle reste dans le .jsonl)
MAX_FICHIERS = 60
MAX_LIGNES_LUES = 200000  # garde-fou : un transcript peut peser 47 Mo


def _texte_utilisateur(message) -> str | None:
    """Extrait le texte d'un tour utilisateur, en jetant les tool_result et rappels systeme."""
    contenu = message.get("content")
    if isinstance(contenu, str):
        texte = contenu
    elif isinstance(contenu, list):
        morceaux = [
            b.get("text", "")
            for b in contenu
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        texte = "\n".join(morceaux)
    else:
        return None
    texte = texte.strip()
    if not texte or texte.startswith("<system-reminder>"):
        return None
    # Un retour d'outil injecte comme tour utilisateur n'est pas une demande.
    if texte.startswith("<local-command") or texte.startswith("Caveat:"):
        return None
    return texte


def _depouiller(chemin: Path):
    """Parcourt le transcript .jsonl en streaming et en tire demandes / fichiers / commandes."""
    demandes, fichiers, commandes = [], [], []
    with chemin.open(encoding="utf-8", errors="replace") as flux:
        for numero, ligne in enumerate(flux):
            if numero > MAX_LIGNES_LUES:
                break
            try:
                evenement = json.loads(ligne)
            except Exception:
                continue
            message = evenement.get("message") or {}
            if evenement.get("type") == "user" and not evenement.get("isMeta"):
                texte = _texte_utilisateur(message)
                if texte:
                    demandes.append(texte)
            elif evenement.get("type") == "assistant":
                for bloc in message.get("content") or []:
                    if not isinstance(bloc, dict) or bloc.get("type") != "tool_use":
                        continue
                    entree = bloc.get("input") or {}
                    if bloc.get("name") in ("Edit", "Write", "NotebookEdit"):
                        chemin_fichier = entree.get("file_path")
                        if chemin_fichier and chemin_fichier not in fichiers:
                            fichiers.append(chemin_fichier)
                    elif bloc.get("name") in ("Bash", "PowerShell"):
                        commandes.append((entree.get("command") or "").strip())
    return demandes, fichiers, commandes


def _rediger(entree: dict) -> Path:
    transcript = Path(entree.get("transcript_path") or "")
    session = (entree.get("session_id") or "inconnue")[:8]
    horodatage = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    DOSSIER.mkdir(parents=True, exist_ok=True)
    sortie = DOSSIER / f"{horodatage}_{session}.md"

    demandes, fichiers, commandes = ([], [], [])
    if transcript.is_file():
        demandes, fichiers, commandes = _depouiller(transcript)

    lignes = [
        f"# Point d'etape avant compaction — {horodatage}",
        "",
        f"- Session : `{entree.get('session_id', '?')}`",
        f"- Declencheur : {entree.get('trigger', '?')} (auto = seuil de contexte, manual = /compact)",
        f"- Dossier de travail : `{entree.get('cwd', '?')}`",
        f"- Transcript complet : `{transcript}`",
        f"- Volume : {len(demandes)} demandes, {len(fichiers)} fichiers ecrits, {len(commandes)} commandes",
        "",
        f"## Demandes (verbatim, {min(len(demandes), MAX_MESSAGES)} dernieres)",
        "",
    ]
    for texte in demandes[-MAX_MESSAGES:]:
        if len(texte) > MAX_CAR_MESSAGE:
            texte = texte[:MAX_CAR_MESSAGE] + " […tronque, voir le transcript]"
        lignes.append("- " + texte.replace("\n", "\n  "))

    lignes += ["", f"## Fichiers ecrits ({len(fichiers)})", ""]
    lignes += [f"- `{f}`" for f in fichiers[:MAX_FICHIERS]] or ["- aucun"]
    if len(fichiers) > MAX_FICHIERS:
        lignes.append(f"- … {len(fichiers) - MAX_FICHIERS} autres")

    lignes += ["", "## Dernieres commandes", "", "```"]
    lignes += [c.split("\n")[0][:200] for c in commandes[-15:]] or ["(aucune)"]
    lignes += ["```", ""]

    sortie.write_text("\n".join(lignes), encoding="utf-8")
    return sortie


def main() -> int:
    try:
        entree = json.load(sys.stdin)
        sortie = _rediger(entree)
        print(f"Point d'etape ecrit : {sortie}")
    except Exception as exc:  # fail-open assume : ne jamais bloquer une compaction
        try:
            DOSSIER.mkdir(parents=True, exist_ok=True)
            (DOSSIER / "ECHEC.log").open("a", encoding="utf-8").write(
                f"{datetime.datetime.now().isoformat()} {type(exc).__name__}: {exc}\n"
            )
        except Exception:
            pass
        print(f"checkpoint_precompact : echec ignore ({type(exc).__name__})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
