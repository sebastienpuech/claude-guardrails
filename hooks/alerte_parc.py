"""Hook SessionStart : remonte les anomalies du parc de taches planifiees.

Pourquoi ce hook existe (2026-08-26). `check-parc.ps1` tourne tous les matins a 8h30,
compare 30 taches a leur cadence attendue, et sait parfaitement dire lesquelles sont
tombees. Il n'avait qu'UNE sortie : un message Telegram. Le fichier de config portant le
token n'a jamais ete cree, donc depuis le 13/08 le scan voyait tout et ne disait rien —
13 jours d'anomalies calculees chaque matin et lues par personne. Le veilleur etait muet,
et un veilleur muet est pire qu'aucun veilleur : tout a l'air calme.

Le correctif tient en deux morceaux. `check-parc.ps1` ecrit desormais son rapport dans
`~/.infra/check-parc.rapport.txt`, sortie qui ne depend d'aucun secret ni d'aucun reseau.
Ce hook le lit a l'ouverture de session. Aucun token, rien a installer sur une autre
machine, rien qui puisse fuir.

Pourquoi LIRE et ne jamais relancer le scan : mesure du 26/08, `check-parc.ps1` prend
3 a 6 s (Get-ScheduledTask sur 30 taches). Payer ca a chaque ouverture de session pour une
information qui change une fois par jour serait un mauvais marche.

Trois etats, trois comportements :
  - rapport frais, 0 anomalie   -> SILENCE. Le silence est le signal de normalite, c'est
                                   deja la regle de check-parc.ps1 ; un hook qui parle a
                                   chaque session cesse d'etre lu.
  - rapport frais, N anomalies  -> les N anomalies, plafonnees.
  - rapport vieux ou absent     -> on le dit. C'est l'alarme meta, et la plus importante :
                                   elle veut dire que le controle quotidien lui-meme est
                                   tombe. Sans elle, un scan mort ressemblerait a un parc
                                   sain — exactement le piege qu'on vient de corriger.

Fail-open : derogation declaree au principe 1 de doctrine.md, meme motif que les autres
hooks informatifs. Un injecteur casse qui empecherait une session de demarrer serait pire
que le mal qu'il signale.
"""
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

RAPPORT = Path.home() / ".infra" / "check-parc.rapport.txt"

# Au-dela, le rapport ne decrit plus le present. La tache tourne tous les jours a 8h30 :
# 36 h laissent passer un PC eteint une nuit et un week-end de reveil tardif, sans laisser
# passer une tache reellement tombee.
AGE_MAX = timedelta(hours=36)

# Le parc compte 30 taches ; une session qui demarre n'a pas besoin d'un mur de texte.
# Au-dela, on renvoie vers le fichier — la regle des ~50 lignes du CLAUDE.md global.
MAX_LIGNES = 15


def lire():
    """(horodatage, corps) du rapport, ou (None, None) s'il est illisible ou vide."""
    if not RAPPORT.exists():
        return None, None
    # utf-8-sig : Set-Content -Encoding UTF8 de Windows PowerShell 5.1 ecrit un BOM.
    # Sans ca, la premiere ligne commence par ﻿ et la date ne se parse pas.
    texte = RAPPORT.read_text(encoding="utf-8-sig", errors="replace").strip()
    if not texte:
        return None, None
    lignes = texte.splitlines()
    try:
        horodatage = datetime.fromisoformat(lignes[0].strip())
    except ValueError:
        return None, None
    return horodatage, "\n".join(lignes[1:]).strip()


def _compte(corps):
    """Nombre d'anomalies annonce par le rapport. -1 si la ligne d'entete est absente.

    TROU attrape par son propre test, le 26/08 : la premiere version testait
    `"0 anomalie" in corps`, ce qui matche aussi « 40 anomalie(s) » — et donc 10, 20, 30.
    Un parc avec exactement dix anomalies aurait ete declare sain, EN SILENCE. C'est le
    pire mode de defaillance possible pour un veilleur, et c'est exactement celui qu'on
    etait en train de corriger. On lit donc le nombre, on ne cherche plus un morceau de
    texte. `-1` (entete illisible) est traite comme « il se passe quelque chose » par
    l'appelant : face a un rapport qu'on ne comprend pas, on parle plutot que se taire.
    """
    if re.search(r"\[PARC\]\s+OK\b", corps):
        return 0
    trouve = re.search(r"\[PARC\]\s+(\d+)\s+anomalie", corps)
    return int(trouve.group(1)) if trouve else -1


def _age_lisible(age):
    if age.days >= 1:
        return f"{age.days} j"
    return f"{int(age.total_seconds() // 3600)} h"


def message():
    """Le texte a injecter, ou None s'il n'y a rien a dire."""
    horodatage, corps = lire()

    if horodatage is None:
        return (
            "PARC — aucun rapport de controle lisible dans ~/.infra/check-parc.rapport.txt. "
            "La tache quotidienne `CheckParc` n'a peut-etre pas tourne. "
            "Verifier : le script qui alimente ce rapport"
        )

    age = datetime.now() - horodatage
    if age > AGE_MAX:
        return (
            f"PARC — le controle quotidien des taches planifiees n'a pas tourne depuis "
            f"{_age_lisible(age)} (dernier rapport : {horodatage:%d/%m %H:%M}). "
            "Le surveillant lui-meme est peut-etre tombe. "
            "Verifier : le script qui alimente ce rapport"
        )

    if not corps or _compte(corps) == 0:
        return None  # silence = tout va bien

    lignes = corps.splitlines()
    if len(lignes) > MAX_LIGNES:
        reste = len(lignes) - MAX_LIGNES
        lignes = lignes[:MAX_LIGNES] + [f"  ... et {reste} de plus — voir {RAPPORT}"]
    return "\n".join(lignes)


def main():
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    texte = message()
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
