"""Test de contournement des garde-fous GIT (etage 2).

« Un garde-fou qu'on n'a pas essaye de contourner est decoratif » (CLAUDE.md global).
Le pendant de test_hooks.py, qui teste les hooks Claude Code : ici on teste les hooks
git, en jouant de vraies routes sur des depots jetables.

Origine — red team du 2026-08-25. La docstring de pre_commit_taille.py affirmait que
« toutes les routes convergent sur le commit ». Faux : sur 11 scenarios joues, 4 faisaient
entrer un changement massif dans l'historique sans qu'aucun garde-fou parle.
  - `git merge --no-ff`  -> declenche pre-merge-commit, qui n'etait pas installe. COLMATE.
  - `git revert` / `git cherry-pick` / `git rebase` -> aucun hook « pre- » ne passe.
    Non blocables sans fermer la porte `--no-verify` : couverts par une ALERTE
    post-commit non bloquante (hooks/alerte_commit_gros.py).

Les depots jetables N'ECRASENT NI HOME NI core.hooksPath : ils heritent du vrai montage.
Un banc qui installe ses propres hooks teste un montage imaginaire — c'est ce qui avait
masque le trou de la fusion pendant le premier passage.

Lancer :  python tests/test_garde_fous_git.py     (exit 0 = vert, 1 = rouge)
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

N_FICHIERS = 40   # > MAX_FICHIERS (30)
N_LIGNES = 30     # 40 x 30 = 1200 suppressions > MAX_SUPPRESSIONS (200)


class Depot:
    def __init__(self, base):
        self.d = Path(tempfile.mkdtemp(prefix="gf_", dir=base))
        self.env = dict(
            os.environ,
            GIT_AUTHOR_NAME="test", GIT_AUTHOR_EMAIL="test@local",
            GIT_COMMITTER_NAME="test", GIT_COMMITTER_EMAIL="test@local",
        )
        self.g("init", "-q", "-b", "main")

    def g(self, *a):
        return subprocess.run(
            ["git", *a], cwd=str(self.d), env=self.env, capture_output=True,
            text=True, encoding="utf-8", errors="replace",
        )

    def peupler(self, n=N_FICHIERS):
        for i in range(n):
            (self.d / f"f{i:02d}.txt").write_text("l\n" * N_LIGNES, encoding="utf-8")
        self.g("add", *[f"f{i:02d}.txt" for i in range(n)])
        self.g("commit", "-qm", "base", "--no-verify")

    def tout_supprimer(self, n=N_FICHIERS):
        for i in range(n):
            (self.d / f"f{i:02d}.txt").unlink()
        self.g("add", "-u")

    def branche_massive(self, nom="gros"):
        """Une branche qui supprime tout, prete a etre fusionnee ou picoree."""
        self.g("checkout", "-q", "-b", nom)
        self.tout_supprimer()
        self.g("commit", "-qm", "suppression massive", "--no-verify")
        sha = self.g("rev-parse", "HEAD").stdout.strip()
        self.g("checkout", "-q", "main")
        return sha

    def commit_sur_main(self, nom="z.txt"):
        (self.d / nom).write_text("z\n", encoding="utf-8")
        self.g("add", nom)
        self.g("commit", "-qm", "autre", "--no-verify")

    def n_commits(self):
        return int(self.g("rev-list", "--count", "HEAD").stdout.strip() or 0)

    def jeter(self):
        shutil.rmtree(self.d, ignore_errors=True)


def _sortie(r):
    return (r.stdout or "") + (r.stderr or "")


# --- scenarios de BLOCAGE : le garde-fou doit refuser ------------------------

def sc_commit_gros(base):
    d = Depot(base); d.peupler(); avant = d.n_commits()
    d.tout_supprimer()
    d.g("commit", "-m", "gros")
    bloque = d.n_commits() == avant
    d.jeter(); return bloque


def sc_amend_gros(base):
    d = Depot(base); d.peupler()
    d.tout_supprimer()
    r = d.g("commit", "--amend", "-m", "gros")
    bloque = "REFUSE" in _sortie(r)
    d.jeter(); return bloque


def sc_merge_gros(base):
    """TROU 25/08 : la fusion ne declenchait pas pre-commit."""
    d = Depot(base); d.peupler(); avant = d.n_commits()
    d.branche_massive()
    d.commit_sur_main()
    d.g("merge", "--no-ff", "-m", "fusion", "gros")
    bloque = d.n_commits() == avant + 1  # seul le commit sur main est passe
    d.jeter(); return bloque


# --- scenarios de PASSAGE : les portes de secours doivent rester ouvertes ----

def sc_commit_no_verify(base):
    d = Depot(base); d.peupler(); avant = d.n_commits()
    d.tout_supprimer()
    d.g("commit", "-m", "gros", "--no-verify")
    passe = d.n_commits() == avant + 1
    d.jeter(); return passe


def sc_merge_no_verify(base):
    d = Depot(base); d.peupler(); avant = d.n_commits()
    d.branche_massive()
    d.commit_sur_main()
    d.g("merge", "--no-ff", "--no-verify", "-m", "fusion", "gros")
    passe = d.n_commits() > avant + 1
    d.jeter(); return passe


# --- scenarios d'ALERTE : non bloquant, mais le message doit sortir ----------

def sc_alerte_revert(base):
    d = Depot(base); d.peupler()
    r = d.g("revert", "--no-edit", d.g("rev-parse", "HEAD").stdout.strip())
    a_parle = "ATTENTION" in _sortie(r)
    d.jeter(); return a_parle


def sc_alerte_cherry_pick(base):
    d = Depot(base); d.peupler()
    sha = d.branche_massive()
    r = d.g("cherry-pick", sha)
    a_parle = "ATTENTION" in _sortie(r)
    d.jeter(); return a_parle


def sc_alerte_rebase(base):
    d = Depot(base); d.peupler()
    d.branche_massive()
    d.commit_sur_main()
    d.g("checkout", "-q", "gros")
    r = d.g("rebase", "main")
    a_parle = "ATTENTION" in _sortie(r)
    d.jeter(); return a_parle


def sc_alerte_no_verify(base):
    """Porte de secours prise volontairement : elle passe, mais elle laisse une trace."""
    d = Depot(base); d.peupler()
    d.tout_supprimer()
    r = d.g("commit", "-m", "gros", "--no-verify")
    a_parle = "ATTENTION" in _sortie(r)
    d.jeter(); return a_parle


def sc_silence_petit(base):
    """Cas negatif : une alerte qui hurle a chaque commit ne vaut pas mieux que rien."""
    d = Depot(base); d.peupler(n=3)
    (d.d / "f00.txt").write_text("modif\n", encoding="utf-8")
    d.g("add", "--", "f00.txt")
    r = d.g("commit", "-m", "petit")
    muet = "ATTENTION" not in _sortie(r)
    d.jeter(); return muet


CAS = [
    ("blocage", "commit direct au-dessus des seuils", sc_commit_gros),
    ("blocage", "git commit --amend au-dessus des seuils", sc_amend_gros),
    ("blocage", "git merge --no-ff massive (TROU 25/08)", sc_merge_gros),
    ("porte", "git commit --no-verify passe", sc_commit_no_verify),
    ("porte", "git merge --no-verify passe", sc_merge_no_verify),
    ("alerte", "revert massif : alerte emise", sc_alerte_revert),
    ("alerte", "cherry-pick massif : alerte emise", sc_alerte_cherry_pick),
    ("alerte", "rebase massif : alerte emise", sc_alerte_rebase),
    ("alerte", "commit --no-verify massif : alerte emise", sc_alerte_no_verify),
    ("alerte", "commit ordinaire : silence", sc_silence_petit),
]


def _montage_ok():
    """Les shims sont-ils presents ET branches ? Retourne la liste des manques.

    Presence et branchement sont deux choses : un shim parfaitement copie mais un
    `core.hooksPath` qui pointe ailleurs ne s'execute jamais. On verifie les deux,
    sans quoi la suite entiere pourrait passer au vert sur un montage mort.
    """
    manques = []
    dossier = Path.home() / ".claude" / "githooks"
    for nom in ("pre-commit", "post-commit", "pre-merge-commit"):
        if not (dossier / nom).exists():
            manques.append(f"shim {nom} absent de ~/.claude/githooks/")
    chemin = subprocess.run(
        ["git", "config", "--global", "core.hooksPath"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.strip()
    if not chemin:
        manques.append("core.hooksPath non defini : les shims ne seront jamais appeles")
    elif Path(chemin).resolve() != dossier.resolve():
        manques.append(f"core.hooksPath pointe ailleurs : {chemin} (attendu {dossier})")
    return manques


def verifier():
    """Retourne le nombre d'echecs."""
    print("\n--- garde-fous git (etage 2, red team 25/08) ---")
    manques = _montage_ok()
    if manques:
        for m in manques:
            print(f"FAIL  {m}")
        return len(manques)
    base = tempfile.mkdtemp(prefix="tgf_")
    echecs = 0
    try:
        for famille, titre, fn in CAS:
            try:
                ok = fn(base)
            except Exception as exc:
                ok = False
                titre = f"{titre}  [exception: {exc}]"
            echecs += not ok
            print(f"{'OK  ' if ok else 'FAIL'}  [{famille:<7}] {titre}")
    finally:
        shutil.rmtree(base, ignore_errors=True)
    return echecs


if __name__ == "__main__":
    n = verifier()
    print("\n" + ("VERT — 0 echec(s)" if not n else f"ROUGE — {n} echec(s)"))
    sys.exit(1 if n else 0)
