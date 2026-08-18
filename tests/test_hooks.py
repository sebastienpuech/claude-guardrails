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




# --- hooks informatifs (2026-08-18) : ils n'exit 2 JAMAIS -------------------
# Derogation declaree au principe 1 : inject_lecons et rappel_lecon INFORMENT.
# Le signal teste n'est donc pas le blocage mais la sortie : parle / se tait.
# Limite connue et assumee de rappel_lecon : `echo "git commit -m 'fix : x'"`
# declenche un rappel (le texte est lu comme une commande). Consequence = une
# ligne de suggestion en trop, jamais un blocage. Pas de parseur shell pour ca.

def _charger(nom):
    import importlib.util
    spec = importlib.util.spec_from_file_location(nom[:-3], HOOKS / nom)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAS_RAPPEL = [
    (f'{G} commit -m "[bot] fix : le watchdog relancait un process mort"', True, "correctif canonique"),
    (f'{G} commit -m "corrige le parseur de frontmatter"', True, "sans prefixe de zone"),
    (f'{G} commit -m "[x] hotfix : y"', True, "hotfix"),
    (f'{G} -C /tmp/x commit -m "fix : y"', True, "option globale -C"),
    (f'{G} commit -m "fix : a" && {G} push', True, "commande chainee"),
    (f'{G} commit -m "[meta] feat : skill lecon-de-repo"', False, "feature, pas un correctif"),
    (f'{G} commit -m "[x] feat : ajoute Y, corrige aussi Z"', False, "le mot n'est pas en tete"),
    (f'{G} commit -m "[x] docs : parle de fix"', False, "docs"),
    (f"{G} log --grep=fix", False, "pas un commit"),
    (f"{G} status", False, "pas un commit"),
]


def _verifier_rappel():
    print("\n--- rappel_lecon.py (detection du correctif) ---")
    detecte = _charger("rappel_lecon.py").message_de_correctif
    echecs = 0
    for cmd, doit_rappeler, note in CAS_RAPPEL:
        ok = (detecte(cmd) is not None) == doit_rappeler
        echecs += not ok
        print(f"{'OK  ' if ok else 'FAIL'}  {cmd:<62} {note}")
    return echecs


def _fiche(dossier, slug, titre, statut="actif"):
    (dossier / f"2026-01-01-{slug}.md").write_text(
        f"---\ntitre: {titre}\ndate: 2026-01-01\ntype: bug\ntags: []\n"
        f"fichiers: []\ncommit: abc1234\nstatut: {statut}\n---\n",
        encoding="utf-8",
    )


def _verifier_injection():
    import tempfile
    print("\n--- inject_lecons.py (selection des fiches) ---")
    contexte = _charger("inject_lecons.py").contexte
    echecs = 0
    with tempfile.TemporaryDirectory() as tmp:
        racine = Path(tmp)
        cas = []

        cas.append(("aucun dossier lecons -> muet", contexte(racine) == ""))

        (racine / "lecons").mkdir()
        cas.append(("dossier vide -> muet", contexte(racine) == ""))

        _fiche(racine / "lecons", "vivante", "Fiche vivante")
        _fiche(racine / "lecons", "morte", "Fiche morte", "supersede-par:2026-01-01-vivante")
        texte = contexte(racine)
        cas.append(("la fiche active est citee", "Fiche vivante" in texte))
        cas.append(("la fiche supersedee est exclue", "Fiche morte" not in texte))
        cas.append(("le compte est juste", "(1)" in texte))

        for i in range(20):
            _fiche(racine / "lecons", f"masse-{i:02d}", f"Fiche {i:02d}")
        texte = contexte(racine)
        cas.append(("plafond a 15 + reste annonce", "+6 autres" in texte))

        for note, ok in cas:
            echecs += not ok
            print(f"{'OK  ' if ok else 'FAIL'}  {note}")
    return echecs


def _verifier_fail_open():
    print("\n--- fail-open assume (les informatifs ne bloquent jamais) ---")
    echecs = 0
    for hook in ("inject_lecons.py", "rappel_lecon.py"):
        p = subprocess.run(
            [sys.executable, str(HOOKS / hook)], input="{pas du json",
            capture_output=True, text=True,
        )
        ok = p.returncode == 0 and not p.stdout.strip()
        echecs += not ok
        print(f"{'OK  ' if ok else 'FAIL'}  {hook:<62} exit={p.returncode}, muet={not p.stdout.strip()}")
    return echecs


def _verifier_repertoire():
    """Defaut du tir reel du 2026-08-18 : le hook lisait le cwd de la SESSION.

    Un `cd autre-repo && git commit` etait donc attribue au mauvais repo — lecon
    proposee au mauvais endroit, anti-spam indexe sur la mauvaise cle.
    """
    import tempfile
    print("\n--- rappel_lecon.py (ou la commande a REELLEMENT tourne) ---")
    mod = _charger("rappel_lecon.py")
    echecs = 0
    with tempfile.TemporaryDirectory() as tmp:
        cible, session = Path(tmp).resolve(), Path.home()

        def ou(cmd):
            return mod.repertoire_cible(cmd, session)

        cas = [
            ("TIR 18/08 : cd <dir> && git commit -> <dir>",
             ou(f"cd {cible} && {G} commit -m 'fix : x'") == cible),
            ("TIR 18/08 : git -C <dir> commit -> <dir>",
             ou(f"{G} -C {cible} commit -m 'fix : x'") == cible),
            ("chemin quote (espaces)",
             ou(f"cd '{cible}' && {G} commit -m 'fix : x'") == cible),
            ("sans cd -> cwd de la session",
             ou(f"{G} commit -m 'fix : x'") == session),
            ("cd vers un dossier inexistant -> cwd de la session",
             ou(f"cd /nexiste/pas && {G} commit -m 'fix : x'") == session),
            ("chemin git-bash traduit en chemin Windows",
             mod._denude("/c/Users/x") == "C:/Users/x"),
        ]
        for note, ok in cas:
            echecs += not ok
            print(f"{'OK  ' if ok else 'FAIL'}  {note}")
    return echecs


if __name__ == "__main__":
    total = (
        _verifier("block_git_add_all.py", "block_git_add_all.py", CAS_GIT, "command")
        + _verifier("block_cloud_cache.py", "block_cloud_cache.py", CAS_CACHE, "command")
        + _verifier_fail_closed()
        + _verifier_rappel()
        + _verifier_repertoire()
        + _verifier_injection()
        + _verifier_fail_open()
    )
    print(f"\n{'VERT' if total == 0 else 'ROUGE'} — {total} echec(s)")
    sys.exit(1 if total else 0)
