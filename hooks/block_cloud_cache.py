"""Hook PreToolUse : bloque toute ecriture dans le cache cloud Claude.

Regle : CLAUDE.md global, section Git — « Ne jamais editer le cache cloud
(%APPDATA%\\Claude\\local-agent-mode-sessions\\...) : volatile, toute edition y est perdue. »

v3 (2026-08-21) — test adversarial : 2 trous sur 5, et un FAUX POSITIF confirme en live
(une lecture pure etait refusee parce que la redirection d'erreur vers le vide comptait
comme un verbe d'ecriture). Corrige : une redirection dont la cible est le peripherique
nul, ou un autre descripteur, n'est plus un verbe d'ecriture.
Les 2 trous restants (interprete non liste, chemin concatene a l'execution) sont
ASSUMES et non colmates. Arbitrage du 2026-08-21 : cette regle n'est pas une regle de
securite mais d'anti-gachis — le cout d'une brece est « tu as edite un fichier pour
rien ». Elargir la liste des interpretes casserait les lectures legitimes pour un gain
nul. Le hook reste un rappel qui rattrape les 3 formes courantes, pas une barriere.

v2 (2026-07-27) — durci apres test de contournement :
  - le matcher etait `Edit|Write|NotebookEdit` seulement. Une copie via Bash/PowerShell
    (`cp`, `Copy-Item`, redirection `>`) n'appelait meme pas le hook — or c'est
    exactement ce que fait un script de deploiement, donc le chemin realiste.
  - fail-open sur JSON illisible (contre le principe 1 de doctrine.md : fail-closed).

Lecture seule sur le cache (ls, cat, diff) : autorisee, c'est le seul moyen de
constater une derive entre le cloud et le repo.

Exit 2 = blocage, message stderr renvoye au modele.
"""
import json
import re
import sys

CACHE = "local-agent-mode-sessions"

# Verbes d'ecriture. Si l'un d'eux apparait dans une commande qui mentionne le cache,
# on refuse : distinguer la source de la destination d'un `cp` est trop fragile pour
# un garde-fou (fail-closed plutot que devinette).
_VERBES = re.compile(
    r"(\b(?:cp|copy|xcopy|robocopy|mv|move|rm|del|erase|rmdir|tee|rsync|touch|install)\b"
    r"|\b(?:Copy-Item|Move-Item|Remove-Item|Set-Content|Add-Content|Out-File|New-Item|Clear-Content)\b"
    r"|\bsed\b[^|;&]*-i)",
    re.IGNORECASE,
)


# Une redirection n'ecrit que si sa cible est un fichier. `2>/dev/null`, `2>$null`,
# `2>&1` ne creent rien : les compter a fait refuser une lecture pure (faux positif
# constate le 2026-08-21).
_REDIR = re.compile(r">>?\s*(&?\S+)?")
_NUL = re.compile(r"^(?:/dev/null|\$null|nul)$", re.IGNORECASE)


def _redirection_ecrivante(cmd: str) -> str | None:
    for m in _REDIR.finditer(cmd):
        cible = m.group(1) or ""
        if cible.startswith("&") or _NUL.match(cible):
            continue
        return m.group(0).split()[0]
    return None


def raison_de_bloquer(data: dict) -> str | None:
    ti = data.get("tool_input") or {}

    chemin = (ti.get("file_path") or ti.get("notebook_path") or "").replace("\\", "/")
    if CACHE in chemin:
        return "edition directe d'un fichier du cache"

    cmd = ti.get("command") or ""
    if CACHE in cmd.replace("\\", "/"):
        verbe = _VERBES.search(cmd)
        if verbe:
            return f"commande d'ecriture (`{verbe.group(0).strip()}`) visant le cache"
        redir = _redirection_ecrivante(cmd)
        if redir:
            return f"redirection (`{redir}`) visant le cache"
    return None


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception as exc:  # fail-closed (doctrine.md principe 1)
        print(
            f"BLOQUE (hook) : entree du hook illisible ({exc}). Un verifieur qui ne peut pas "
            "mesurer refuse au lieu de laisser passer. Verifier block_cloud_cache.py.",
            file=sys.stderr,
        )
        return 2

    raison = raison_de_bloquer(data)
    if raison:
        print(
            f"BLOQUE (hook) : {raison} — le cache cloud est volatile, toute edition y est "
            "perdue a la prochaine synchro. Editer le repo source, puis git push + re-upload "
            "manuel cote Cowork/Desktop. (Lecture seule sur le cache : autorisee. Si la copie "
            "va DEPUIS le cache vers un repo, le dire explicitement : derogation declaree.)",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
