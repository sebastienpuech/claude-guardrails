"""Test de contournement des hooks globaux.

« Un garde-fou qu'on n'a pas essaye de contourner est decoratif » (CLAUDE.md global, Methode).
Chaque cas TROU trouve le 2026-07-27 est ici en test permanent (doctrine.md principe 2 :
chaque echec reel devient un test, jamais une regle isolee de plus).

Lancer :  python tests/test_hooks.py     (exit 0 = vert, 1 = rouge)
"""
import json
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "hooks"
G = "g" + "it"  # evite de declencher le hook sur la commande qui lance ce test

CAS_GIT = [
    # (commande, doit_bloquer, note)
    (f"{G} add -A", True, "canonique"),
    (f"{G} add .", True, "canonique"),
    (f"{G} add ./", True, "canonique"),
    (f"{G} add --all", True, "canonique"),
    (f"{G} add -A -- .", True, "canonique + pathspec"),
    (f"{G} -C /tmp/x add -A", True, "option globale -C"),
    (f"{G} -c user.name=x add -A", True, "option globale -c"),
    (f"{G} --git-dir=/tmp/.git add -A", True, "option globale --git-dir"),
    (f"{G}   add   -A", True, "espaces multiples"),
    (f"cd foo && {G} add -A", True, "commande chainee"),
    (f"{G} add --al", True, "TROU 27/07 : abreviation longue acceptee par git"),
    (f"{G} add --a", True, "TROU 27/07 : abreviation minimale"),
    (f"{G} add --upd", True, "TROU 27/07 : abreviation de --update"),
    (f"{G} add -u", True, "TROU 27/07 : stage toutes les suppressions suivies"),
    (f"{G} add -uA", True, "TROU 27/07 : groupe d'options courtes"),
    (f"{G} add -vA", True, "TROU 27/07 : groupe d'options courtes"),
    (f"{G} add *", True, "TROU 27/07 : glob expanse par le shell"),
    (f"{G} add :/", True, "TROU 27/07 : pathspec racine du repo"),
    (f"{G} add :(top)", True, "TROU 27/07 : pathspec magique racine"),
    # Faux positifs a ne pas produire
    (f"{G} add src/foo.py", False, "legitime : fichier explicite"),
    (f"{G} add src/foo.py src/bar.py", False, "legitime : plusieurs fichiers"),
    (f"{G} add -p src/foo.py", False, "legitime : patch interactif scope"),
    (f"{G} status", False, "pas un add"),
    (f"{G} log --all", False, "--all hors add"),
    ("echo add -A", False, "pas une commande git"),
    (f'{G} commit -m "fix : {G} add --al passait, desormais bloque"',
     False, "FAUX+ 27/07 : message de commit documentant l'incident"),
    (f'{G} commit -m "ligne 1\n\n  - {G} add -A et -u sont refuses"',
     False, "FAUX+ 27/07 : message multi-ligne"),
    (f"{G} commit -m 'texte avec {G} add .'",
     False, "FAUX+ 27/07 : message en quotes simples"),
    (f'{G} commit -m "msg" && {G} add -A',
     True, "un vrai add apres un message reste bloque"),
]

CAS_CACHE = [
    # (payload, doit_bloquer, note)
    ({"file_path": "C:/Users/x/AppData/Roaming/Claude/local-agent-mode-sessions/s/SKILL.md"},
     True, "edition directe (Edit/Write)"),
    ({"file_path": r"C:\Users\x\AppData\Roaming\Claude\local-agent-mode-sessions\s\SKILL.md"},
     True, "edition directe, chemin Windows"),
    ({"command": "cp a.md '/c/Users/x/AppData/Roaming/Claude/local-agent-mode-sessions/s/SKILL.md'"},
     True, "TROU 27/07 : copie via Bash"),
    ({"command": "Copy-Item a.md 'C:\\...\\local-agent-mode-sessions\\s\\SKILL.md'"},
     True, "TROU 27/07 : copie via PowerShell"),
    ({"command": "echo x > /c/.../local-agent-mode-sessions/s/SKILL.md"},
     True, "TROU 27/07 : redirection"),
    ({"command": "ls /c/.../local-agent-mode-sessions/"},
     False, "lecture seule autorisee"),
    ({"command": "diff a.md /c/.../local-agent-mode-sessions/s/SKILL.md"},
     False, "lecture seule autorisee (constat de derive)"),
    ({"file_path": "<HOME>/dev/un-projet/meta/SKILL.md"},
     False, "repo source : autorise"),
]


def _lancer(hook: str, payload: str) -> int:
    return subprocess.run(
        [sys.executable, str(HOOKS / hook)], input=payload, capture_output=True, text=True
    ).returncode


def _verifier(titre, hook, cas, cle):
    echecs = 0
    print(f"\n--- {titre} ---")
    for entree, doit_bloquer, note in cas:
        payload = json.dumps({"tool_input": entree if isinstance(entree, dict) else {cle: entree}})
        bloque = _lancer(hook, payload) == 2
        ok = bloque == doit_bloquer
        echecs += not ok
        etiquette = "OK  " if ok else ("TROU" if doit_bloquer else "FAUX+")
        libelle = entree if isinstance(entree, str) else next(iter(entree.values()))[:58]
        print(f"{etiquette}  {libelle:<62} {note}")
    return echecs


def _verifier_fail_closed():
    print("\n--- fail-closed (entree illisible) ---")
    echecs = 0
    for hook in ("block_git_add_all.py", "block_cloud_cache.py"):
        code = _lancer(hook, "{ceci n'est pas du json")
        ok = code == 2
        echecs += not ok
        print(f"{'OK  ' if ok else 'FAIL'}  {hook:<62} exit={code} (attendu 2)")
    return echecs


if __name__ == "__main__":
    total = (
        _verifier("block_git_add_all.py", "block_git_add_all.py", CAS_GIT, "command")
        + _verifier("block_cloud_cache.py", "block_cloud_cache.py", CAS_CACHE, "command")
        + _verifier_fail_closed()
    )
    print(f"\n{'VERT' if total == 0 else 'ROUGE'} — {total} echec(s)")
    sys.exit(1 if total else 0)
