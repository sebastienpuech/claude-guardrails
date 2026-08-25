"""Hook PreToolUse : interdit tout `git add` non scope au chantier.

Regle : CLAUDE.md global, section Git — « `git add` scope au chantier, jamais `-A` ni `.` ».
Incident a l'origine : 4 545 lignes de suppression avalees par le commit d'une autre session.

v3 (2026-08-21) — test adversarial : 10 trous sur 12 cas. `.split()` coupait aux espaces
sans deguillemeter : le token gardait ses guillemets, ne commencait donc pas par `-`,
et passait. `shlex.split()` decoupe comme le shell le ferait. Ferme les formes citees
entre guillemets, apostrophes, echappees par antislash, et la variante PowerShell.
Effet de bord : supprime aussi un faux positif (un nom de fichier contenant un tiret
suivi de A etait lu comme l'option courte).
Les 6 autres trous (alias, variable shell, xargs, substitution de commande, script .sh)
sont NON colmatables ici : la commande ne contient jamais les deux mots cote a cote.
Ils sont couverts un etage plus bas, par le garde-fou `pre-commit`
(~/.claude/githooks/pre-commit), qui lit l'etat reel du staging au lieu du texte.

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
import shlex
import sys

# Formes de pathspec qui designent « tout » plutot qu'un fichier precis.
PATHSPECS_GLOBAUX = {".", "./", "*", "./*", ":", ":/", ":/.", ":(top)"}

# Options longues dont TOUT prefixe non ambigu est accepte par git (parse-options).
# git exige au moins `--a` / `--u` pour lever l'ambiguite ; on borne a 3 caracteres.
LONGUES_INTERDITES = ("--all", "--update", "--no-ignore-removal")

# Prefixe des options globales de git qui peuvent preceder la sous-commande `add`.
#
# v4 (2026-08-25) — red team : la liste nominative laissait passer 6 variantes, parce
# qu'une option globale absente de la liste faisait echouer le motif ENTIER : le hook ne
# regardait alors meme plus les arguments. `git -P add -A` staggeait tout sans un mot.
# Mesure : 6 trous sur 8 variantes essayees, chacune verifiee efficace sur un depot reel.
# Corrige en acceptant N'IMPORTE QUELLE option entre `git` et `add` — a cet endroit
# precis de la ligne de commande, seule une option globale de git peut apparaitre, donc
# un motif generique n'elargit pas la surface. Enumerer etait le defaut : toute option
# oubliee, presente ou future, devenait une porte.
_GLOBALES = r"(?:\s+(?:-[cC]\s+\S+|--[a-z][\w-]*(?:=\S+)?|-[a-zA-Z]))*"
_MOTIF = re.compile(r"\bgit\b" + _GLOBALES + r"\s+add\b([^|;&><\n]*)")

# v4 (2026-08-25) — red team : `--pathspec-from-file=liste.txt` lit les chemins AILLEURS
# que sur la ligne de commande. Aucune analyse de texte ne peut savoir ce qu'il y a dans
# le fichier — donc on refuse la forme elle-meme, seule reponse honnete.
_HORS_LIGNE = ("--pathspec-from-file", "--pathspec-file-nul")

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


def _pathspec_non_borne(arg: str) -> str | None:
    """Un pathspec qui ne designe pas un ensemble fini de fichiers nommes.

    v4 (2026-08-25) — red team : la liste fermee PATHSPECS_GLOBAUX ratait 6 formes
    (`:/*`, `:(glob)**`, `:(top,glob)**`, `:!zzz`, `:(exclude)zzz`, `**`), toutes
    verifiees efficaces sur un depot reel. Enumerer les formes de « tout » est perdu
    d'avance : la syntaxe des pathspecs magiques en fabrique a volonte, et `:!zzz`
    (« tout sauf zzz ») en est un rappel — une exclusion est une inclusion de tout
    le reste. On inverse donc la charge : un `git add` scope nomme ses fichiers.

    Deux formes refusees, sans exception :
      - tout argument commencant par `:`  → pathspec magique (Windows n'autorise pas
        `:` dans un nom de fichier, donc aucun faux positif possible) ;
      - tout argument contenant `*`       → glob, donc ensemble non borne (idem, `*`
        est un caractere interdit dans un nom de fichier Windows).
    """
    if arg.startswith(":"):
        return f"pathspec magique `{arg}` (designe un ensemble, pas des fichiers nommes)"
    if "*" in arg:
        return f"glob `{arg}` (ensemble non borne : lister les fichiers explicitement)"
    return None


def raison_de_bloquer(cmd: str) -> str | None:
    """Retourne la raison du blocage, ou None si la commande est scopee."""
    cmd = _MESSAGE.sub(" ", cmd)  # le texte d'un message n'est pas une commande
    for match in _MOTIF.finditer(cmd):
        try:
            args = shlex.split(match.group(1), posix=True)
        except ValueError:  # guillemet non ferme : fail-closed
            return "commande non analysable (guillemet non ferme)"
        for arg in args:
            if arg.split("=", 1)[0] in _HORS_LIGNE:
                return (
                    f"option `{arg}` (les chemins sont lus dans un fichier : "
                    "impossible de verifier ce qui sera stage)"
                )
            if _est_long_interdit(arg):
                return f"option `{arg}` (prefixe de --all/--update : git accepte les abreviations)"
            if _est_court_interdit(arg):
                return f"option `{arg}` (-A stage tout, -u stage toutes les suppressions suivies)"
            if arg in PATHSPECS_GLOBAUX:
                return f"pathspec `{arg}` (designe tout le repo, pas le chantier)"
            raison = _pathspec_non_borne(arg)
            if raison:
                return raison
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
