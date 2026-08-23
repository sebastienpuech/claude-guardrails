"""Hook UserPromptSubmit : alerte quand le contexte de la session franchit un palier.

Probleme mesure (session du 2026-08-23) : la variable CLAUDE_CODE_AUTO_COMPACT_WINDOW
a vecu 36 h (posee le 19/08 13:01, retiree le 20/08 21:15). A 120000 elle declenchait
un compactage a peine au-dessus du plancher de contexte (~69k) : 167 compactages en
deux jours, dont 27 dans une seule session. La retirer a corrige la boucle, mais le
seuil par defaut mesure sur les transcripts se situe entre 922k et 998k tokens : plus
rien ne previent avant. Ce hook comble le trou SANS forcer de compactage.

Choix assume : il ALERTE, il ne compacte pas. Le compactage subi perd le contexte de
travail sans rendre la fenetre ; la decision (fork, /compact, continuer) reste humaine.
CLAUDE.md global : « session > 150 k tokens -> /compact ou fork ».

Sortie : systemMessage JSON (affiche a l'utilisateur, PAS injecte dans le contexte).
Un hook UserPromptSubmit qui ecrit sur stdout voit son texte ajoute au contexte —
ce serait absurde pour une alerte qui dit justement que le contexte est plein. D'ou
suppressOutput.

DEROGATION ASSUMEE a doctrine.md principe 1 (fail-closed) : ce hook n'est pas un
verifieur, c'est une jauge. S'il plante, il ne doit PAS bloquer une demande. Fail-open,
exit 0 toujours, l'erreur part dans le fichier d'echec pour etre vue.

Confidentialite : ne lit que les compteurs de tokens, jamais le texte des messages.
"""
import datetime
import json
import os
import sys
from pathlib import Path

DOSSIER = Path(os.environ.get("CLAUDE_ALERTE_CONTEXTE_DOSSIER")
               or Path.home() / ".claude" / "alertes-contexte")
SEUIL = int(os.environ.get("CLAUDE_ALERTE_CONTEXTE_SEUIL", "150000"))
QUEUE_OCTETS = 2_000_000  # on ne lit que la fin du transcript : il peut peser 47 Mo


def _total_contexte(transcript: Path) -> int:
    """Taille de la derniere requete envoyee au modele, en tokens.

    Somme input_tokens + cache_read + cache_creation : c'est ce qui occupe reellement
    la fenetre, pas seulement les tokens factures comme neufs.
    """
    taille = transcript.stat().st_size
    with transcript.open("rb") as f:
        f.seek(max(0, taille - QUEUE_OCTETS))
        brut = f.read().decode("utf-8", errors="ignore")
    lignes = brut.split("\n")
    if taille > QUEUE_OCTETS and lignes:
        lignes.pop(0)  # la premiere ligne lue est tronquee au milieu
    for ligne in reversed(lignes):
        if '"usage"' not in ligne:
            continue
        try:
            usage = (json.loads(ligne).get("message") or {}).get("usage") or {}
        except Exception:
            continue
        if usage:
            return sum(
                usage.get(cle, 0) or 0
                for cle in ("input_tokens", "cache_read_input_tokens",
                            "cache_creation_input_tokens")
            )
    return 0


def _palier_deja_signale(session: str, palier: int) -> bool:
    """Vrai si ce palier a deja declenche une alerte dans cette session.

    Un fichier par session, contenant le plus haut palier signale. Sans cet etat
    l'alerte se repeterait a chaque prompt une fois le seuil franchi.
    """
    marqueur = DOSSIER / f"{session}.txt"
    try:
        vu = int(marqueur.read_text(encoding="utf-8").strip())
    except Exception:
        vu = 0
    if palier <= vu:
        return True
    DOSSIER.mkdir(parents=True, exist_ok=True)
    marqueur.write_text(str(palier), encoding="utf-8")
    return False


def main() -> int:
    try:
        entree = json.load(sys.stdin)
        transcript = Path(entree.get("transcript_path") or "")
        if not transcript.is_file():
            return 0
        total = _total_contexte(transcript)
        palier = total // SEUIL
        if palier < 1:
            return 0
        session = str(entree.get("session_id") or "inconnue")[:8]
        if _palier_deja_signale(session, palier):
            return 0
        alerte = (
            f"Contexte : ~{total // 1000}k tokens (palier {palier} x {SEUIL // 1000}k). "
            "CLAUDE.md : au-dela de 150k, /compact ou fork. Ecris l'avancement AVANT "
            "(acquis / ecarte et pourquoi / prochaine action) — le compactage ne rend "
            "pas la fenetre, le plancher survit."
        )
        print(json.dumps({"systemMessage": alerte, "suppressOutput": True}))
    except Exception as exc:  # fail-open assume : ne jamais bloquer une demande
        try:
            DOSSIER.mkdir(parents=True, exist_ok=True)
            (DOSSIER / "ECHEC.log").open("a", encoding="utf-8").write(
                f"{datetime.datetime.now().isoformat()} {type(exc).__name__}: {exc}\n"
            )
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
