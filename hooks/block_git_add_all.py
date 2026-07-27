"""Hook PreToolUse : interdit tout `git add` non scope au chantier.

Regle : CLAUDE.md global, section Git — « `git add` scope au chantier, jamais `-A` ni `.` ».
Incident a l'origine : 4 545 lignes de suppression avalees par le commit d'une autre session.

v2 (2026-07-27) — durci apres test de contournement (5 trous sur 13 cas) :
  - `--al`, `--upd`… : git accepte les abreviations non ambigues d'options longues
    (verifie en live : `git add --al` stage bien tout le repo).
  - `-u` / `--update` : stage TOUTES les suppressions suivies = exactement l'incident d'origine.
  - `git add *` : le glob est expanse par le shell, l'ancien hook ne voyait qu'un `*`.
  - `git add :/` : pathspec « racine du repo », equivalent a `-A` depuis n'importe quel sous-dossier.
  - fail-open sur JSON illisible (contre le principe 1 de doctrine.md : fail-closed).

`git commit -a` n'est PAS traite ici : il est deja tenu par la permission `ask` sur
`Bash(git commit:*)` dans settings.json. Une regle vit a un seul etage.

Exit 2 = blocage, message stderr renvoye au modele.
"""
import json
import re
import sys

# Formes de pathspec qui designent « tout » plutot qu'un fichier precis.
PATHSPECS_GLOBAUX = {".", "./", "*", "./*", ":", ":/", ":/.", ":(top)"}

# Options longues dont TOUT prefixe non ambigu est accepte par git (parse-options).
# git exige au moins `--a` / `--u` pour lever l'ambiguite ; on borne a 3 caracteres.
LONGUES_INTERDITES = ("--all", "--update", "--no-ignore-removal")

# Prefixe des options globales de git qui peuvent preceder le sous-commande `add`.
_GLOBALES = r"(?:\s+(?:-C\s+\S+|-c\s+\S+|--git-dir=\S+|--work-tree=\S+|--exec-path=\S+|-p|--paginate|--no-pager))*"
_MOTIF = re.compile(r"\bgit\b" + _GLOBALES + r"\s+add\b([^|;&><\n]*)")

# Faux positif du 2026-07-27 : un message de commit qui DOCUMENTE l'incident
# (« git add --al passait ») etait lu comme une commande. Le contenu d'un -m/-F
# est du texte, jamais une commande — on le retire avant d'analyser.
_MESSAGE = re.compile(
    r"(?:-m|--message|-F|--file)(?:\s+|=)"
    r"(\"(?:[^\"\\]|\\.)*\"|'[^']*'|\S+)",
)


def _est_long_interdit(arg: str) -> bool:
    """`--al`, `--all`, `--upd`… — tout prefixe d'au moins 3 caracteres d'une option interdite."""
    if not arg.startswith("--") or len(arg) < 3:
        return False
    nom = arg.split("=", 1)[0]
    return any(longue.startswith(nom) for longue in LONGUES_INTERDITES)


def _est_court_interdit(arg: str) -> bool:
    """`-A`, `-u`, et les groupes courts type `-vA` / `-uA`."""
    if not arg.startswith("-") or arg.startswith("--"):
        return False
    return any(c in ("A", "u") for c in arg[1:])


def raison_de_bloquer(cmd: str) -> str | None:
    """Retourne la raison du blocage, ou None si la commande est scopee."""
    cmd = _MESSAGE.sub(" ", cmd)  # le texte d'un message n'est pas une commande
    for match in _MOTIF.finditer(cmd):
        for arg in match.group(1).split():
            if _est_long_interdit(arg):
                return f"option `{arg}` (prefixe de --all/--update : git accepte les abreviations)"
            if _est_court_interdit(arg):
                return f"option `{arg}` (-A stage tout, -u stage toutes les suppressions suivies)"
            if arg in PATHSPECS_GLOBAUX:
                return f"pathspec `{arg}` (designe tout le repo, pas le chantier)"
    return None


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception as exc:  # fail-closed (doctrine.md principe 1)
        print(
            f"BLOQUE (hook) : entree du hook illisible ({exc}). Un verifieur qui ne peut pas "
            "mesurer refuse au lieu de laisser passer. Verifier block_git_add_all.py.",
            file=sys.stderr,
        )
        return 2

    cmd = (data.get("tool_input") or {}).get("command") or ""
    raison = raison_de_bloquer(cmd)
    if raison:
        print(
            f"BLOQUE (hook) : {raison}. `git add` doit etre scope au chantier — lister les "
            "fichiers explicitement. Incident a l'origine de la regle : 4 545 lignes avalees "
            "par le commit d'une autre session.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
