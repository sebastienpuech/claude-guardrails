"""Garde-fou git `pre-commit` : refuse un commit anormalement gros.

Regle : CLAUDE.md global, section Git — « `git add` scope au chantier, jamais `-A` ni `.` ».
Incident a l'origine : 4 545 lignes de suppression avalees par le commit d'une autre session.

Pourquoi ici et pas dans le hook Claude : le hook `block_git_add_all.py` lit le TEXTE
de la commande. Test adversarial du 2026-08-21 : 12 contournements sur 17 passent
(alias, variable, xargs, substitution, script .sh, guillemets). Deux causes racines
sont non colmatables par regex — il faudrait executer la commande pour savoir ce
qu'elle fait. Ce hook-ci lit l'ETAT REEL du staging : toutes les routes (alias,
script, staging manuel, autre session, git gui) convergent sur le commit.

Seuils calibres sur les 1 198 commits reels des 10 repos de ~/dev (2026-08-21) :
  fichiers    p50=2  p90=8   p95=12  p99=110  max=800
  suppressions p50=3 p90=35  p95=67  p99=563  max=91095
Le couple retenu se declenche sur 4,2 % des commits (~1 sur 24).

Sortie de secours assumee : `git commit --no-verify`. C'est la porte visible et
deliberee ; un garde-fou sans porte se contourne dans le dos.

Exit 1 = commit refuse.
"""
import subprocess
import sys

MAX_FICHIERS = 30
MAX_SUPPRESSIONS = 200


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True, encoding="utf-8", errors="replace"
    ).stdout


def mesurer() -> tuple[int, int, int]:
    """(nb fichiers touches, total lignes supprimees, nb fichiers entierement supprimes)."""
    fichiers = 0
    suppressions = 0
    for ligne in _git("diff", "--cached", "--numstat").splitlines():
        colonnes = ligne.split("\t")
        if len(colonnes) < 3:
            continue
        fichiers += 1
        if colonnes[1] != "-":  # "-" = fichier binaire, pas de compte de lignes
            suppressions += int(colonnes[1])
    supprimes = len(
        [f for f in _git("diff", "--cached", "--diff-filter=D", "--name-only").splitlines() if f]
    )
    return fichiers, suppressions, supprimes


def main() -> int:
    try:
        fichiers, suppressions, supprimes = mesurer()
    except Exception as exc:  # fail-closed (doctrine.md principe 1)
        print(
            f"REFUSE (garde-fou) : mesure du staging impossible ({exc}). Un verifieur qui ne "
            "peut pas mesurer refuse au lieu de laisser passer. Verifier pre_commit_taille.py, "
            "ou forcer avec `git commit --no-verify` si tu sais ce que tu fais.",
            file=sys.stderr,
        )
        return 1

    depassements = []
    if fichiers > MAX_FICHIERS:
        depassements.append(f"{fichiers} fichiers (seuil {MAX_FICHIERS})")
    if suppressions > MAX_SUPPRESSIONS:
        depassements.append(f"{suppressions} lignes supprimees (seuil {MAX_SUPPRESSIONS})")
    if not depassements:
        return 0

    print(f"REFUSE (garde-fou) : commit anormalement gros - {', '.join(depassements)}.", file=sys.stderr)
    if supprimes:
        print(f"  Dont {supprimes} fichier(s) entierement supprime(s) :", file=sys.stderr)
        for f in _git("diff", "--cached", "--diff-filter=D", "--name-only").splitlines()[:15]:
            if f:
                print(f"    - {f}", file=sys.stderr)
    print(
        "  Inspecter avec : git diff --cached --stat\n"
        "  Si le perimetre est bien voulu : git commit --no-verify\n"
        "  Incident a l'origine : 4 545 lignes avalees par le commit d'une autre session.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
