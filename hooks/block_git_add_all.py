"""Hook PreToolUse : bloque `git add -A`, `git add --all` et `git add .`.

git add doit rester scope au chantier (CLAUDE.md global, section Git).
Incident a l'origine de la regle : 4 545 lignes de suppression avalees par
le commit d'une autre session.
Exit 2 = blocage, message stderr renvoye au modele.
"""
import json
import re
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

cmd = (data.get("tool_input") or {}).get("command") or ""

for match in re.finditer(r"\bgit\b((?:\s+-C\s+\S+)*)\s+add\s+([^|;&><]*)", cmd):
    args = match.group(2).split()
    if any(a in ("-A", "--all", ".", "./") for a in args):
        print(
            "BLOQUE (hook) : `git add -A` / `git add .` interdit — git add scope au "
            "chantier uniquement (lister les fichiers explicitement). Incident a "
            "l'origine de la regle : 4 545 lignes avalees par le commit d'une autre session.",
            file=sys.stderr,
        )
        sys.exit(2)
sys.exit(0)
