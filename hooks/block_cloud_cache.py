"""Hook PreToolUse : bloque toute ecriture dans le cache cloud Claude.

Le dossier local-agent-mode-sessions est un cache volatile ecrase a chaque
synchro — toute edition y est perdue (CLAUDE.md global, section Git).
Exit 2 = blocage, message stderr renvoye au modele.
"""
import json
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

tool_input = data.get("tool_input") or {}
path = (tool_input.get("file_path") or tool_input.get("notebook_path") or "")
if "local-agent-mode-sessions" in path.replace("\\", "/"):
    print(
        "BLOQUE (hook) : edition du cache cloud (local-agent-mode-sessions) interdite — "
        "cache volatile, toute edition y est perdue. Editer le repo source, puis git push "
        "+ re-upload manuel cote Cowork/Desktop.",
        file=sys.stderr,
    )
    sys.exit(2)
sys.exit(0)
