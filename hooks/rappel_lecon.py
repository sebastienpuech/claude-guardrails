"""Hook PostToolUse : apres un commit de correctif, rappelle d'ecrire la lecon.

Moitie "ecrire" du skill `lecon-de-repo` (un depot de skills). Le moment ou la lecon
est la moins chere a ecrire est celui ou le fix vient d'etre commite ; c'est aussi celui
ou on passe a autre chose. Ce hook ne fait que poser la question, une fois par repo et
par jour.

Pas de cle `if` dans settings.json - le filtrage se fait ICI. Incident du 2026-07-27 :
une cle non documentee dans une entree de hook desactive le hook en SILENCE, JSON
valide, aucun message. Seules `type`, `command`, `timeout` sont admises.

DEROGATION DECLAREE au principe 1 (fail-closed) : ce hook SUGGERE, il ne verifie rien.
Il sort toujours en 0. Un rappel casse ne doit jamais interrompre un commit reussi.
"""
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ETAT = Path.home() / ".claude" / "lecon-rappels.json"

_GLOBALES = (
    r"(?:\s+(?:-C\s+\S+|-c\s+\S+|--git-dir=\S+|--work-tree=\S+"
    r"|--exec-path=\S+|-p|--paginate|--no-pager))*"
)
_COMMIT = re.compile(r"\bgit\b" + _GLOBALES + r"\s+commit\b")
_MESSAGE = re.compile(
    r"(?:-m|--message)(?:\s+|=)(\"(?:[^\"\\]|\\.)*\"|'[^']*'|\S+)"
)
# Convention de commit : "[zone] fix : description". On n'accepte le mot qu'en TETE
# de message : "feat : ... corrige aussi X" n'est pas un commit de correctif.
_CORRECTIF = re.compile(
    r"^\s*(?:\[[^\]]*\]\s*)?(fix|hotfix|bugfix|corrige|correctif)\b", re.I
)


def message_de_correctif(cmd: str):
    """Retourne le message du commit si c'en est un et qu'il corrige, sinon None."""
    if not _COMMIT.search(cmd):
        return None
    for brut in _MESSAGE.findall(cmd):
        msg = brut[1:-1] if brut[:1] in ("\"", "'") and brut[-1:] == brut[:1] else brut
        if _CORRECTIF.match(msg):
            return msg
    return None


_CD = re.compile(r"^\s*cd\s+(\"[^\"]*\"|'[^']*'|\S+)")
_DASH_C = re.compile(r"\bgit\b[^|;&\n]*?-C\s+(\"[^\"]*\"|'[^']*'|\S+)")
_POSIX_WIN = re.compile(r"^/([a-zA-Z])/")


def _denude(chemin: str) -> str:
    """Retire les quotes, et traduit un chemin git-bash (/c/Users) en chemin Windows."""
    if chemin[:1] in ("\"", "'") and chemin[-1:] == chemin[:1]:
        chemin = chemin[1:-1]
    return _POSIX_WIN.sub(lambda m: m.group(1).upper() + ":/", chemin)


def repertoire_cible(cmd: str, cwd: Path) -> Path:
    """Ou la commande s'est REELLEMENT executee.

    Defaut trouve au tir reel du 2026-08-18 : le hook recevait le cwd de la SESSION,
    donc un `cd autre-repo && git commit` etait attribue au mauvais repo — la lecon
    aurait ete proposee au mauvais endroit, et l'anti-spam indexe sur la mauvaise cle.
    """
    for motif in (_DASH_C, _CD):
        trouve = motif.search(cmd)
        if trouve:
            chemin = Path(_denude(trouve.group(1)))
            if chemin.is_dir():
                return chemin
    return cwd


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


def deja_rappele_aujourdhui(racine: str) -> bool:
    """Anti-spam : un rappel par repo et par jour. Illisible -> on rappelle quand meme."""
    aujourdhui = date.today().isoformat()
    try:
        etat = json.loads(ETAT.read_text(encoding="utf-8")) if ETAT.exists() else {}
    except Exception:
        etat = {}
    if etat.get(racine) == aujourdhui:
        return True
    etat[racine] = aujourdhui
    try:
        ETAT.parent.mkdir(parents=True, exist_ok=True)
        ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass  # mieux vaut un rappel de trop qu'un hook muet
    return False


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    reponse = data.get("tool_response")
    if isinstance(reponse, dict) and reponse.get("success") is False:
        return 0

    cmd = (data.get("tool_input") or {}).get("command") or ""
    msg = message_de_correctif(cmd)
    if msg is None:
        return 0

    cwd = Path(data.get("cwd") or os.getcwd())
    racine = racine_git(repertoire_cible(cmd, cwd))
    if racine is None or deja_rappele_aujourdhui(str(racine)):
        return 0

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"Correctif commite dans {racine.name} : '{msg[:120]}'. Si ce bug a coute "
                "une recherche, proposer a Sebastien d'en garder la lecon (skill "
                "`lecon-de-repo`) - ancrage = les fichiers touches ou le sha du commit. "
                "Si le fix etait trivial, ne rien proposer et ne pas en reparler."
            ),
        }
    }, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # un rappel ne fait jamais tomber un commit reussi
        sys.exit(0)
