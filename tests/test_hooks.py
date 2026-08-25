"""Test de contournement des hooks globaux.

« Un garde-fou qu'on n'a pas essaye de contourner est decoratif » (CLAUDE.md global, Methode).
Chaque cas TROU trouve le 2026-07-27 est ici en test permanent (doctrine.md principe 2 :
chaque echec reel devient un test, jamais une regle isolee de plus).

Lancer :  python tests/test_hooks.py     (exit 0 = vert, 1 = rouge)
"""
import json
import os
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

        # Audit du 2026-08-18 : une fiche restee au squelette passait pour saine.
        (racine / "lecons" / "2026-01-01-squelette.md").write_text(
            "---\ntitre: Squelette\ndate: 2026-01-01\ntype: bug\ntags: []\n"
            "fichiers: []\ncommit: abc1234\nstatut: actif\n---\n\n"
            "<ce qu'on a vu, une phrase>\n", encoding="utf-8")
        cas.append(("AUDIT 18/08 : fiche restee squelette -> exclue",
                    "Squelette" not in contexte(racine)))

        # Audit du 2026-08-18 : le commentaire YAML etait lu comme une valeur.
        (racine / "lecons" / "2026-01-01-commentee.md").write_text(
            "---\ntitre: Commentee\ndate: 2026-01-01\n"
            "type: bug            # bug | convention | workflow\ntags: []\n"
            "fichiers: []\ncommit: abc1234\nstatut: actif\n---\n\nCorps rempli.\n",
            encoding="utf-8")
        texte = contexte(racine)
        cas.append(("AUDIT 18/08 : commentaire YAML ignore dans la valeur",
                    "[bug]" in texte and "#" not in texte))

        for i in range(20):
            _fiche(racine / "lecons", f"masse-{i:02d}", f"Fiche {i:02d}")
        import re as _re
        texte = contexte(racine)
        # Derive du total annonce plutot que code en dur : ajouter un cas au-dessus
        # ne doit pas casser ce test pour une mauvaise raison.
        total = int(_re.search(r"repo \((\d+)\)", texte).group(1))
        cas.append(("plafond a 15 + reste annonce",
                    f"+{total - 15} autres" in texte and texte.count("\n- ") == 16))

        for note, ok in cas:
            echecs += not ok
            print(f"{'OK  ' if ok else 'FAIL'}  {note}")
    return echecs


def _verifier_fail_open():
    print("\n--- fail-open assume (les informatifs ne bloquent jamais) ---")
    echecs = 0
    # Repertoire NEUTRE (hors repo, sans journal ni lecons) : sans lui, un hook qui se
    # rabat sur os.getcwd() parlerait de ce repo-ci et le test echouerait pour une
    # raison etrangere au fail-open (constate le 2026-08-20, journal.md ajoute ici).
    import tempfile
    _neutre = tempfile.TemporaryDirectory()
    neutre = _neutre.name
    for hook in ("inject_lecons.py", "rappel_lecon.py", "journal_etat.py"):
        p = subprocess.run(
            [sys.executable, str(HOOKS / hook)], input="{pas du json",
            capture_output=True, text=True, cwd=neutre,
        )
        ok = p.returncode == 0 and not p.stdout.strip()
        echecs += not ok
        print(f"{'OK  ' if ok else 'FAIL'}  {hook:<62} exit={p.returncode}, muet={not p.stdout.strip()}")
    _neutre.cleanup()
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


def _verifier_checkpoint():
    """checkpoint_precompact.py : il ecrit, il n'invente pas, et il ne bloque JAMAIS.

    Un hook PreCompact qui plante bloquerait la compaction d'une session longue —
    donc fail-open assume (l'inverse de doctrine.md principe 1, cf. docstring du hook).
    """
    import tempfile
    print("\n--- checkpoint_precompact.py ---")
    mod = _charger("checkpoint_precompact.py")
    echecs = 0
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        mod.DOSSIER = base / "checkpoints"
        transcript = base / "t.jsonl"
        transcript.write_text("\n".join([
            json.dumps({"type": "user", "message": {"content": "DEMANDE-UNE"}}),
            "{ligne corrompue au milieu",
            json.dumps({"type": "user", "message": {"content": [
                {"type": "tool_result", "content": "sortie d'outil"}]}}),
            json.dumps({"type": "user", "message": {"content": "<system-reminder>bruit</system-reminder>"}}),
            json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Write", "input": {"file_path": "/x/y.py"}}]}}),
            json.dumps({"type": "user", "message": {"content": "DEMANDE-DEUX"}}),
        ]), encoding="utf-8")

        sortie, _ = mod._rediger({"session_id": "abcd1234-ef", "transcript_path": str(transcript),
                                  "trigger": "auto", "cwd": str(base)})
        texte = sortie.read_text(encoding="utf-8")
        cas = [
            ("le fichier est ecrit", sortie.is_file()),
            ("demande verbatim conservee", "DEMANDE-UNE" in texte and "DEMANDE-DEUX" in texte),
            ("ligne corrompue : les suivantes sont quand meme lues", "DEMANDE-DEUX" in texte),
            ("un tool_result n'est pas une demande", "sortie d'outil" not in texte),
            ("un system-reminder n'est pas une demande", "bruit" not in texte),
            ("2 demandes comptees, pas 4", "2 demandes" in texte),
            ("fichier ecrit trace", "/x/y.py" in texte),
            ("chemin du transcript conserve", str(transcript) in texte),
        ]

        # transcript absent : on ecrit quand meme un fichier, on ne plante pas
        vide, _ = mod._rediger({"session_id": "zz", "transcript_path": str(base / "nexiste.jsonl"),
                                "trigger": "manual", "cwd": str(base)})
        cas.append(("transcript absent : fichier quand meme ecrit", vide.is_file()))

        # Compteur de compactions : silencieux au 1er passage, bruyant au 2e (seuil
        # d'abandon du CLAUDE.md global). Le rang se deduit des fichiers deja sur
        # disque ; deux passages dans la meme minute ecrasent le meme fichier, ce qui
        # est sans importance ici — ce qu'on prouve, c'est que l'alerte sort au 2e.
        arg = {"session_id": "seance99-xx", "transcript_path": str(transcript),
               "trigger": "auto", "cwd": str(base)}
        f1, r1 = mod._rediger(arg)
        t1 = f1.read_text(encoding='utf-8')
        f2, r2 = mod._rediger(arg)
        t2 = f2.read_text(encoding='utf-8')
        cas += [
            ("1re compaction de la session : rang 1", r1 == 1),
            ("1re compaction : aucune alerte", "ALERTE" not in t1),
            ("2e compaction de la session : rang 2", r2 == 2),
            ("2e compaction : banniere d'alerte en tete du fichier", "ALERTE" in t2),
            ("l'alerte dit quoi faire, pas seulement qu'il y a probleme",
             "Ecrire l'etat" in t2),
        ]

        for note, ok in cas:
            echecs += not ok
            print(f"{'OK  ' if ok else 'FAIL'}  {note}")

    # fail-open bout en bout : JSON illisible sur stdin => exit 0, la compaction passe.
    # Le hook calcule DOSSIER depuis Path.home() ; en sous-processus on ne peut pas le
    # monkeypatcher, alors on lui ment sur son dossier maison (USERPROFILE sous Windows,
    # HOME ailleurs). Sans ca le test ecrivait son propre echec dans le VRAI
    # ~/.claude/checkpoints/ECHEC.log — 12 lignes de bruit constatees le 20/08, qui
    # rendaient illisible le seul canal d'alerte du hook.
    vrai_journal = Path.home() / ".claude" / "checkpoints" / "ECHEC.log"
    avant = vrai_journal.stat().st_size if vrai_journal.is_file() else -1
    with tempfile.TemporaryDirectory() as tmp:
        faux_home = {**os.environ, "USERPROFILE": tmp, "HOME": tmp}
        p = subprocess.run([sys.executable, str(HOOKS / "checkpoint_precompact.py")],
                           input="{pas du json", capture_output=True, text=True,
                           env=faux_home)
        journal_echec = Path(tmp) / ".claude" / "checkpoints" / "ECHEC.log"
        apres = vrai_journal.stat().st_size if vrai_journal.is_file() else -1
        cas = [
            (f"fail-open : JSON illisible ne bloque pas la compaction (exit={p.returncode})",
             p.returncode == 0),
            ("l'echec est trace dans le faux home (fail-open != silencieux)",
             journal_echec.is_file() and "JSONDecodeError" in journal_echec.read_text(encoding="utf-8")),
            (f"le vrai ECHEC.log n'a pas bouge ({avant} -> {apres} octets)", avant == apres),
        ]
        for note, ok in cas:
            echecs += not ok
            print(f"{'OK  ' if ok else 'FAIL'}  {note}")

    # Bout en bout : le 2e compactage d'une session crie sur stderr — seul canal d'un
    # hook PreCompact vers Sebastien (exit 2 n'y parle pas a Claude) — sans bloquer.
    with tempfile.TemporaryDirectory() as tmp:
        faux_home = {**os.environ, "USERPROFILE": tmp, "HOME": tmp}
        charge = json.dumps({"session_id": "boucle01-zz", "transcript_path": "",
                             "trigger": "auto", "cwd": tmp})
        runs = [subprocess.run([sys.executable, str(HOOKS / "checkpoint_precompact.py")],
                               input=charge, capture_output=True, text=True,
                               env=faux_home) for _ in range(2)]
        cas = [
            ("1er compactage : stderr muet", runs[0].stderr.strip() == ""),
            ("2e compactage : alerte sur stderr", "2e COMPACTAGE" in runs[1].stderr),
            (f"l'alerte ne bloque pas la compaction (exit={runs[1].returncode})",
             runs[1].returncode == 0),
        ]
        for note, ok in cas:
            echecs += not ok
            print(f"{'OK  ' if ok else 'FAIL'}  {note}")
    return echecs


def _verifier_journal_etat():
    """journal_etat.py : injecte l'etat du projet, PAS le journal entier.

    Enjeu du 2026-08-20 : ce hook existe pour tuer le rechauffage (88 % du cache_write
    des grosses sessions). S'il injectait tout le journal (80 Ko sur un-autre-projet), il
    couterait plus cher que le mal qu'il soigne. Le plafond et la selection du seul bloc
    d'etat SONT la raison d'etre du hook, pas un detail — testes comme tels.
    """
    import tempfile
    print("\n--- journal_etat.py (etat du projet a l'ouverture) ---")
    mod = _charger("journal_etat.py")
    echecs = 0
    with tempfile.TemporaryDirectory() as tmp:
        racine = Path(tmp)
        cas = []

        cas.append(("aucun journal -> muet", mod.contexte(racine) == ""))

        journal = racine / "journal.md"
        journal.write_text("\n".join([
            "# Journal", "", "Preambule a ne pas injecter.", "",
            "## Etat actuel (glissant)", "", "CHANTIER-EN-COURS", "",
            "## Log (append-only)", "",
            "### 2026-08-20 - entree recente", "", "corps A", "",
            "### 2026-08-19 - entree du milieu", "", "corps B", "",
            "### 2026-08-18 - troisieme", "", "corps C", "",
            "### 2026-08-17 - QUATRIEME-DE-TROP", "", "corps D", "",
        ]), encoding="utf-8")
        texte = mod.contexte(racine)
        cas.append(("le bloc d'etat est injecte", "CHANTIER-EN-COURS" in texte))
        cas.append(("le preambule n'est pas injecte", "Preambule" not in texte))
        cas.append(("le corps du log n'est pas injecte", "corps A" not in texte))
        cas.append(("les 3 dernieres entrees sont citees",
                    "entree recente" in texte and "troisieme" in texte))
        cas.append(("la 4e entree est exclue (plafond DERNIERES)",
                    "QUATRIEME-DE-TROP" not in texte))
        cas.append(("le chemin du fichier est nomme", "journal.md" in texte))

        # Les vrais journaux ecrivent « Etat actuel » AVEC accent : sans normalisation,
        # le hook retomberait sur la premiere section venue.
        journal.write_text("\n".join([
            "## Autre section", "", "PIEGE", "",
            "## État actuel (glissant)", "", "BON-BLOC", "",
        ]), encoding="utf-8")
        texte = mod.contexte(racine)
        cas.append(("titre accentue reconnu, pas la 1re section venue",
                    "BON-BLOC" in texte and "PIEGE" not in texte))

        # Plafond : un bloc d'etat qui enfle redevient le probleme qu'on soigne.
        plafond = mod.PLAFOND_CAR
        try:
            mod.PLAFOND_CAR = 200
            journal.write_text("## Etat actuel\n\n" + "ligne de remplissage\n" * 60,
                               encoding="utf-8")
            texte = mod.contexte(racine)
            cas.append(("bloc trop long -> tronque", len(texte) < 900))
            cas.append(("la troncature est annoncee", "tronque" in texte))
        finally:
            mod.PLAFOND_CAR = plafond

        # Un journal sans aucune section : rien a dire, on se tait.
        journal.write_text("# Journal\n\nque du texte libre\n", encoding="utf-8")
        cas.append(("journal sans section '##' -> muet", mod.contexte(racine) == ""))

        # Repli sur l'autre emplacement de la convention.
        journal.unlink()
        (racine / "docs").mkdir()
        (racine / "docs" / "journal.md").write_text("## Etat actuel\n\nDEPUIS-DOCS\n",
                                                    encoding="utf-8")
        texte = mod.contexte(racine)
        cas.append(("repli sur docs/journal.md", "DEPUIS-DOCS" in texte))
        cas.append(("le chemin annonce est le bon", "docs/journal.md" in texte))

        for note, ok in cas:
            echecs += not ok
            print(f"{'OK  ' if ok else 'FAIL'}  {note}")

    # Mesure du 2026-08-19 : 10 sessions reelles sur 53 vivaient dans un SOUS-dossier
    # (un-projet/skills/un-skill). Un hook qui ne regarde que le cwd serait
    # muet la ou il sert le plus.
    with tempfile.TemporaryDirectory() as tmp:
        racine = Path(tmp)
        subprocess.run([G, "init", "-q", str(racine)], capture_output=True)
        (racine / "journal.md").write_text("## Etat actuel\n\nVU-DEPUIS-LE-FOND\n",
                                           encoding="utf-8")
        profond = racine / "meta" / "skills" / "mode-plan"
        profond.mkdir(parents=True)
        trouvee = mod.racine_git(profond)
        ok = trouvee is not None and "VU-DEPUIS-LE-FOND" in mod.contexte(trouvee)
        echecs += not ok
        print(f"{'OK  ' if ok else 'FAIL'}  journal de la racine trouve depuis un sous-dossier")

    # Hors repo git (ex. ouverture dans ~) : muet, et surtout exit 0.
    p = subprocess.run([sys.executable, str(HOOKS / "journal_etat.py")],
                       input=json.dumps({"cwd": str(Path.home())}),
                       capture_output=True, text=True)
    ok = p.returncode == 0
    echecs += not ok
    print(f"{'OK  ' if ok else 'FAIL'}  hors repo git : n'echoue pas (exit={p.returncode})")

    # Contrat de sortie verifie sur du vrai stdout, pas sur la docstring.
    with tempfile.TemporaryDirectory() as tmp:
        racine = Path(tmp)
        subprocess.run([G, "init", "-q", str(racine)], capture_output=True)
        (racine / "journal.md").write_text("## Etat actuel\n\nCONTRAT\n", encoding="utf-8")
        p = subprocess.run([sys.executable, str(HOOKS / "journal_etat.py")],
                           input=json.dumps({"cwd": str(racine)}),
                           capture_output=True, text=True)
        try:
            sortie = json.loads(p.stdout)["hookSpecificOutput"]
            ok = (sortie["hookEventName"] == "SessionStart"
                  and "CONTRAT" in sortie["additionalContext"])
        except Exception:
            ok = False
        echecs += not ok
        print(f"{'OK  ' if ok else 'FAIL'}  contrat SessionStart/additionalContext respecte")
    return echecs


def _verifier_alerte_contexte():
    """alerte_contexte.py : il jauge, il ne compacte pas, et il ne bloque JAMAIS.

    Il remplace CLAUDE_CODE_AUTO_COMPACT_WINDOW, retiree le 20/08/2026 apres la boucle
    de compactage (167 compactages en 36 h, dont 27 dans une seule session). Elle
    forcait un compactage a 120k, a peine au-dessus du plancher de contexte (~69k).
    La lecon : alerter, laisser la decision humaine. Invariant le plus important ici —
    une alerte qui dit « le contexte est plein » ne doit rien ajouter au contexte.
    """
    import tempfile
    print("\n--- alerte_contexte.py (jauge de contexte) ---")
    mod = _charger("alerte_contexte.py")
    echecs = 0

    def _usage(lu, cree, neufs=10):
        return json.dumps({"type": "assistant", "message": {"usage": {
            "input_tokens": neufs, "cache_read_input_tokens": lu,
            "cache_creation_input_tokens": cree}}})

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        mod.DOSSIER = base / "alertes"
        transcript = base / "t.jsonl"
        transcript.write_text("\n".join([
            _usage(1_000, 0),
            "{ligne corrompue au milieu",
            json.dumps({"type": "user", "message": {"content": "ligne sans usage"}}),
            _usage(400_000, 100_000),
        ]), encoding="utf-8")
        total = mod._total_contexte(transcript)
        cas = [
            ("somme lu+cree+neufs, pas seulement les tokens neufs", total == 500_010),
            ("c'est la DERNIERE requete qui compte, pas la premiere", total > 1_000),
            ("ligne corrompue au milieu : ignoree, pas d'exception", total > 0),
            ("500k -> palier 3 avec un seuil de 150k", total // 150_000 == 3),
            ("premier franchissement -> alerte", not mod._palier_deja_signale("s1", 3)),
            ("meme palier -> silence (pas de harcelement)", mod._palier_deja_signale("s1", 3)),
            ("palier suivant -> alerte a nouveau", not mod._palier_deja_signale("s1", 4)),
        ]
        for titre, ok in cas:
            echecs += not ok
            print(f"{'OK  ' if ok else 'FAIL'}  {titre}")

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        env = {**os.environ, "CLAUDE_ALERTE_CONTEXTE_DOSSIER": str(base / "etat")}
        transcript = base / "t.jsonl"
        transcript.write_text(_usage(900_000, 0), encoding="utf-8")

        def _run(charge):
            return subprocess.run(
                [sys.executable, str(HOOKS / "alerte_contexte.py")],
                input=charge, capture_output=True, text=True, env=env)

        p1 = _run(json.dumps({"session_id": "golden", "transcript_path": str(transcript)}))
        try:
            sortie = json.loads(p1.stdout)
        except Exception:
            sortie = {}
        p2 = _run("{pas du json")
        petit = base / "petit.jsonl"
        petit.write_text(_usage(1_000, 0), encoding="utf-8")
        p3 = _run(json.dumps({"session_id": "golden-bas", "transcript_path": str(petit)}))
        casb = [
            ("exit 0 : ne bloque jamais une demande", p1.returncode == 0),
            ("systemMessage emis au franchissement", "systemMessage" in sortie),
            ("suppressOutput : rien n'entre dans le contexte", sortie.get("suppressOutput") is True),
            ("aucune injection via hookSpecificOutput", "hookSpecificOutput" not in sortie),
            ("le total est chiffre dans le message", "900k" in sortie.get("systemMessage", "")),
            ("stdin illisible -> fail-open, exit 0", p2.returncode == 0),
            ("stdin illisible -> stdout muet", p2.stdout.strip() == ""),
            ("sous le seuil -> silence total", p3.returncode == 0 and p3.stdout.strip() == ""),
        ]
        for titre, ok in casb:
            echecs += not ok
            print(f"{'OK  ' if ok else 'FAIL'}  {titre}")
    return echecs


def _verifier_gate_modele():
    """gate_modele.py : il conseille par injection, il ne bloque ni ne classe.

    Invariants, tous nes d'un echec reel du 24/08/2026 :
    (a) sa sortie ENTRE dans le contexte du modele, donc texte brut -- du JSON serait
        interprete par Claude Code comme une decision structuree ;
    (b) tout echec laisse stdout MUET : une consigne a moitie ecrite qui entre dans le
        contexte est pire que pas de hook ;
    (c) la TRACE ne doit jamais empecher l'INJECTION. Premiere version : _tracer() etait
        appele avant l'ecriture, un dossier de trace non creable a supprime la consigne
        entiere. Le produit passe d'abord, le confort ensuite ;
    (d) l'effort se lit dans le transcript (champ `effort`, ecrit par Claude Code lui-meme),
        pas dans CLAUDE_EFFORT dont l'heritage n'etait pas garanti.
    """
    import tempfile
    print("\n--- gate_modele.py (conseil modele/effort) ---")
    echecs = 0

    def _tour(modele, effort=None):
        o = {"type": "assistant", "message": {"model": modele}}
        if effort:
            o["effort"] = effort
        return json.dumps(o)

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        transcript = base / "t.jsonl"
        transcript.write_text("\n".join([
            _tour("claude-opus-5", "medium"),
            "{ligne corrompue au milieu",
            json.dumps({"type": "user", "message": {"content": "pas de modele ici"}}),
            _tour("claude-fable-5", "high"),
        ]), encoding="utf-8")
        sans_effort = base / "sans_effort.jsonl"
        sans_effort.write_text(_tour("claude-opus-5"), encoding="utf-8")
        vide = base / "vide.jsonl"
        vide.write_text("", encoding="utf-8")

        # DOSSIER impossible a creer : un fichier ordinaire sert de parent
        obstacle = base / "obstacle"
        obstacle.write_text("je ne suis pas un dossier", encoding="utf-8")

        env = {**os.environ, "CLAUDE_GATE_MODELE_DOSSIER": str(base / "etat"),
               "CLAUDE_EFFORT": "xhigh"}
        env.pop("CLAUDE_GATE_MODELE", None)

        def _run(charge, e=None):
            return subprocess.run(
                [sys.executable, str(HOOKS / "gate_modele.py")],
                input=charge, capture_output=True, text=True, env=e or env)

        def _charge(sid, chemin):
            return json.dumps({"session_id": sid, "transcript_path": str(chemin)})

        p1 = _run(_charge("g1", transcript))
        p2 = _run(_charge("g2", vide))
        p3 = _run(_charge("g3", transcript), {**env, "CLAUDE_GATE_MODELE": "off"})
        p4 = _run("ceci n'est pas du json")
        p5 = _run(_charge("g5", sans_effort),
                  {k: v for k, v in env.items() if k != "CLAUDE_EFFORT"})
        p6 = _run(_charge("g6", sans_effort))
        p7 = _run(_charge("g7", transcript),
                  {**env, "CLAUDE_GATE_MODELE_DOSSIER": str(obstacle / "sous")})

        def _est_json(texte):
            try:
                json.loads(texte)
                return True
            except Exception:
                return False

        trace = base / "etat" / "g1.txt"
        cas = [
            ("exit 0 : ne bloque jamais une demande", p1.returncode == 0),
            ("c'est le DERNIER modele du transcript qui compte",
             "claude-fable-5" in p1.stdout),
            ("ligne corrompue au milieu : ignoree, pas d'exception",
             p1.returncode == 0 and p1.stdout.strip() != ""),
            ("l'effort vient du transcript, pas de l'environnement",
             "effort=high]" in p1.stdout),
            ("le marqueur de mesure est present et greppable",
             "[[MODELE]]" in p1.stdout),
            ("le bareme cite les trois modeles et les deux axes",
             all(m in p1.stdout for m in
                 ("claude-sonnet-5", "claude-opus-5", "claude-fable-5",
                  "medium", "high", "xhigh", "max", "ultracode"))),
            ("ultracode figure sur Fable ET sur Opus (verifie a l'ecran 24/08)",
             "claude-opus-5 / ultracode" in p1.stdout
             and "claude-fable-5 / ultracode" in p1.stdout),
            ("le critere max/ultracode est le DECOUPAGE, pas la difficulte",
             "DECOUPAGE" in p1.stdout and "indivisible" in p1.stdout),
            ("TROU 24/08 : la lecture a un tour de retard, la consigne le dit",
             "PRECEDENT" in p1.stdout and "perimee" in p1.stdout),
            ("sortie en texte brut, JAMAIS du JSON (sinon lu comme une decision)",
             not _est_json(p1.stdout.strip())),
            ("transcript vide -> repli sur le defaut de settings.json",
             p2.returncode == 0 and p2.stdout.strip() != ""),
            ("le repli s'annonce comme non confirme, il n'invente rien",
             "?" in p2.stdout or "pas encore confirme" in p2.stdout),
            ("interrupteur off -> silence total",
             p3.returncode == 0 and p3.stdout.strip() == ""),
            ("stdin illisible -> fail-open, exit 0", p4.returncode == 0),
            ("stdin illisible -> stdout MUET (rien n'entre dans le contexte)",
             p4.stdout.strip() == ""),
            ("transcript sans effort ET env absent -> le dit, ne l'invente pas",
             "effort=inconnu]" in p5.stdout),
            ("transcript sans effort -> repli sur l'environnement",
             "effort=xhigh]" in p6.stdout),
            ("TROU 24/08 : trace impossible -> la consigne est emise quand meme",
             p7.stdout.strip() != "" and "claude-fable-5" in p7.stdout),
            ("TROU 24/08 : trace impossible -> exit 0 malgre tout", p7.returncode == 0),
            ("trace ecrite une fois par session (mesure a posteriori)",
             trace.exists() and "effort=high" in trace.read_text(encoding="utf-8")),
        ]
        for titre, ok in cas:
            echecs += not ok
            print(f"{'OK  ' if ok else 'FAIL'}  {titre}")
    return echecs


def _verifier_autosauvegarde():
    """autosauvegarde_config.py : copie ce qui change, ne deplace JAMAIS rien.

    Le filet repond a l'incident du 21/08/2026 (deploiement qui ecrase du travail
    de hook non commite). La propriete qui compte n'est pas « ca sauvegarde » mais
    « ca ne touche pas a l'original » : la suggestion d'origine passait par
    `git stash push`, qui retire les fichiers du repertoire de travail. Un filet
    qui vide le plan de travail a chaque fin de tour serait pire que le mal.
    """
    import tempfile
    print("\n--- autosauvegarde_config.py (filet de config) ---")
    mod = _charger("autosauvegarde_config.py")
    echecs = 0
    with tempfile.TemporaryDirectory() as tmp:
        cible = Path(tmp)
        (cible / "hooks").mkdir()
        settings = cible / "settings.json"
        settings.write_text('{"a": 1}', encoding="utf-8")
        hook = cible / "hooks" / "un_hook.py"
        hook.write_text("print('v1')\n", encoding="utf-8")
        auto = cible / ".sauvegardes" / "auto"
        cas = []

        copies = mod.snapshot(cible, horodatage="T1")
        cas.append(("1er passage : les 2 fichiers sont sauvegardes", len(copies) == 2))
        cas.append(("settings.json copie",
                    (auto / "T1" / "settings.json").read_text(encoding="utf-8") == '{"a": 1}'))
        cas.append(("le hook est copie sous son sous-dossier",
                    (auto / "T1" / "hooks" / "un_hook.py").is_file()))

        # LA propriete du design : l'original reste en place, intact.
        cas.append(("l'original n'a pas bouge", hook.is_file()))
        cas.append(("l'original n'est pas modifie",
                    hook.read_text(encoding="utf-8") == "print('v1')\n"))

        cas.append(("2e passage sans changement : rien de copie",
                    mod.snapshot(cible, horodatage="T2") == []))
        cas.append(("aucun snapshot vide cree", not (auto / "T2").exists()))

        hook.write_text("print('v2')\n", encoding="utf-8")
        copies = mod.snapshot(cible, horodatage="T3")
        cas.append(("seul le fichier modifie est recopie", copies == ["hooks/un_hook.py"]))
        cas.append(("l'ancienne version reste consultable",
                    (auto / "T1" / "hooks" / "un_hook.py").read_text(encoding="utf-8")
                    == "print('v1')\n"))

        # Rotation : sans elle, le filet remplit le disque en silence.
        plafond = mod.MAX_SNAPSHOTS
        try:
            mod.MAX_SNAPSHOTS = 3
            for i in range(5):
                hook.write_text(f"print('r{i}')\n", encoding="utf-8")
                mod.snapshot(cible, horodatage=f"R{i}")
            restants = sorted(p.name for p in auto.iterdir() if p.is_dir())
            cas.append(("rotation : au plus MAX_SNAPSHOTS conserves", len(restants) == 3))
            cas.append(("rotation : ce sont les plus recents", restants == ["R2", "R3", "R4"]))
        finally:
            mod.MAX_SNAPSHOTS = plafond

        # Etat corrompu : on resauvegarde tout plutot que de se taire.
        (cible / ".sauvegardes" / "empreintes.json").write_text("pas du json",
                                                                encoding="utf-8")
        cas.append(("empreintes illisibles -> on resauvegarde",
                    len(mod.snapshot(cible, horodatage="T4")) == 2))

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
        + _verifier_checkpoint()
        + _verifier_journal_etat()
        + _verifier_alerte_contexte()
        + _verifier_gate_modele()
        + _verifier_autosauvegarde()
    )
    print(f"\n{'VERT' if total == 0 else 'ROUGE'} — {total} echec(s)")
    sys.exit(1 if total else 0)
