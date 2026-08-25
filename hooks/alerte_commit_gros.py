"""Hook git `post-commit` : signale un commit anormalement gros DEJA cree.

Pourquoi ce hook existe, et pourquoi il n'est pas bloquant (red team du 2026-08-25).

Trois routes font entrer un commit dans l'historique sans declencher le moindre hook
« pre- » : `git revert`, `git cherry-pick`, `git rebase`. Mesure sur depot jetable, avec
les 13 hooks candidats installes en sonde : sur ces trois routes, seul `prepare-commit-msg`
passe avant la creation du commit.

`prepare-commit-msg` a ete essaye comme point de blocage, puis ECARTE sur mesure :
  - il n'est PAS neutralise par `--no-verify` (verifie) : y mettre le controle de taille
    fermerait la porte de secours documentee de `pre_commit_taille.py`. Un garde-fou sans
    porte se contourne dans le dos — c'est le principe pose le 21/08, on ne le casse pas ;
  - il recoit `$2 == "message"` aussi bien pour un commit ordinaire que pour un revert ou
    un cherry-pick (verifie) : impossible de restreindre le controle aux seules routes du
    sequenceur.

Et bloquer ces trois routes serait de toute facon un faux positif par construction : le
revert d'un commit qui supprimait 4 000 lignes en rajoute 4 000. C'est gros, et c'est
exactement ce qu'on a demande. Ces routes rejouent un commit NOMME, deja existant — elles
ne peuvent pas avaler par accident le travail d'une autre session, qui est l'incident
d'origine de la regle.

D'ou ce hook : il ne refuse rien, il rend visible. Il se declenche apres coup, et signale
tout commit au-dessus des seuils. En pratique il ne parle que dans les cas ou aucun
garde-fou n'a pu parler avant : les trois routes du sequenceur, et les commits passes
deliberement en `--no-verify`. Un commit ordinaire trop gros, lui, a deja ete refuse.

Exit 0 toujours : un hook post-commit qui echoue ne peut rien annuler, il ne ferait
qu'ajouter du bruit a une operation deja terminee.
"""
import subprocess
import sys

MAX_FICHIERS = 30
MAX_SUPPRESSIONS = 200


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True,
        encoding="utf-8", errors="replace",
    ).stdout


def mesurer_head() -> tuple[int, int]:
    """(fichiers touches, lignes supprimees) du commit qui vient d'etre cree."""
    fichiers = suppressions = 0
    # HEAD^! = le commit HEAD compare a son premier parent ; fonctionne aussi sur une
    # fusion (on y mesure l'apport reel par rapport a la branche d'accueil).
    for ligne in _git("diff", "--numstat", "HEAD^!").splitlines():
        colonnes = ligne.split("\t")
        if len(colonnes) < 3:
            continue
        fichiers += 1
        if colonnes[1] != "-":  # "-" = binaire, pas de compte de lignes
            suppressions += int(colonnes[1])
    return fichiers, suppressions


def main() -> int:
    try:
        fichiers, suppressions = mesurer_head()
        sha = _git("rev-parse", "--short", "HEAD").strip()
        sujet = _git("log", "-1", "--format=%s").strip()
    except Exception:
        # Premier commit du depot (pas de HEAD^), depot en cours de bascule, etc.
        # Un hook d'alerte qui plante ne doit jamais gener une operation deja finie.
        return 0

    depassements = []
    if fichiers > MAX_FICHIERS:
        depassements.append(f"{fichiers} fichiers (seuil {MAX_FICHIERS})")
    if suppressions > MAX_SUPPRESSIONS:
        depassements.append(f"{suppressions} lignes supprimees (seuil {MAX_SUPPRESSIONS})")
    if not depassements:
        return 0

    print(
        f"\nATTENTION : le commit {sha} est anormalement gros - {', '.join(depassements)}.\n"
        f"  Sujet   : {sujet}\n"
        "  Il est DEJA cree. Ce message n'est pas un refus : aucune barriere ne pouvait\n"
        "  s'interposer sur cette route (revert / cherry-pick / rebase), ou elle a ete\n"
        "  levee volontairement (--no-verify).\n"
        "  Inspecter : git show --stat HEAD\n"
        "  Defaire en gardant le travail : git reset --soft HEAD~1\n",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
