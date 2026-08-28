"""Hook UserPromptSubmit : rappelle de tenir une CARTE quand la session bifurque.

Probleme mesure (24/08/2026, 17 transcripts du un projet reel). Sebastien :
« dans ces projets complexes, je me perds moi-meme et tu me perds aussi dans les
differentes iterations. J'explore des branches, je reviens, je diverge. » Mesure :

    seuil                              sessions concernees
    >= 15 tours humains                 5 / 17  (29 %)
    >= 3 bifurcations                   3 / 17  (18 %)
    >= 15 tours ET >= 3 bifurcations    3 / 17  (18 %)   <- seuil retenu

Sur ces 3 sessions, 2 avaient deja publie un artefact (un chantier interne) et
1 non (22 tours, 4 bifurcations, aucune carte) : c'est exactement le cas que ce hook
attrape. Le seuil combine ecarte le faux positif d'une session de 3 tours qui contient
2 revirements — court et confus n'est pas la meme chose que long et arborescent.

Choix assume : il RAPPELLE, il ne fabrique rien. Meme posture qu'alerte_contexte.py.
Publier une carte coute un artefact et du temps ; la decision reste humaine.

Etat : un petit fichier par session dans ~/.claude/rappels-carte/. Les compteurs sont
incrementes a chaque prompt (O(1)) — le transcript n'est JAMAIS relu en entier, il peut
peser des dizaines de Mo. Seule la detection « une carte existe-t-elle deja ? » lit la
fin du fichier, et seulement au moment ou le seuil est franchi.

DEROGATION ASSUMEE a doctrine.md principe 1 (fail-closed) : ce hook n'est pas un
verifieur, c'est un rappel. S'il plante, il ne doit PAS bloquer une demande.
Fail-open, exit 0 toujours.

Confidentialite : le fichier d'etat ne contient que des compteurs. Aucun verbatim du
prompt n'est ecrit nulle part.

Reglages :
    CLAUDE_RAPPEL_CARTE=off              desactive completement
    CLAUDE_RAPPEL_CARTE_TOURS            defaut 15
    CLAUDE_RAPPEL_CARTE_BIFURCATIONS     defaut 3
    CLAUDE_RAPPEL_CARTE_DOSSIER          dossier d'etat (tests)

Regle d'abandon, ecrite avant la mise en service : si au bout d'un mois aucune carte
n'a ete produite a la suite d'un rappel, ou si les cartes produites ne sont jamais
rouvertes, retirer le hook — pas l'elargir.
"""
import io
import json
import os
import re
import sys
from pathlib import Path

TOURS_MIN = int(os.environ.get("CLAUDE_RAPPEL_CARTE_TOURS", "15"))
BIFURC_MIN = int(os.environ.get("CLAUDE_RAPPEL_CARTE_BIFURCATIONS", "3"))
ECART_RELANCE = 15          # tours a attendre avant de re-rappeler
QUEUE_OCTETS = 3_000_000    # on ne lit que la fin du transcript

DOSSIER = Path(os.environ.get("CLAUDE_RAPPEL_CARTE_DOSSIER")
               or Path.home() / ".claude" / "rappels-carte")

# Un revirement : le message repart en arriere, corrige, ou change de branche.
_DEBUT = re.compile(
    r"^\s*[\"'«“]?\s*(non\b|attends?\b|en fait\b|plut[oô]t\b|reprends?\b"
    r"|revien|finalement\b|oublie\b|annule\b|stop\b|arr[eê]te)", re.I)
_CORPS = re.compile(
    r"(tu t'es [eé]gar|on a perdu le fil|je ne sais plus o[uù]|je me perds"
    r"|c'[eé]tait pas [cç]a|c'est pas ce que|revenons? en arri[eè]re)", re.I)

_ARTEFACT = re.compile(r"claude\.ai/code/artifact/")

# Texte ASCII strict : la sortie d'un hook passe par stdout, encode par defaut en
# cp1252 sur cette machine. Un tiret cadratin y devient l'octet 0x97, illisible cote
# Claude Code qui lit de l'UTF-8 ; un caractere absent de la table ferait carrement
# lever UnicodeEncodeError et le rappel serait perdu. Bug reel, vu au test du 24/08.
GABARIT = """Une carte tient en six elements, toujours les memes :
  1. LE TRONC - les etapes produit dans l'ordre, datees, une par palier franchi.
  2. LES LOSANGES - les recadrages de Sebastien, verbatim court, poses sur le tronc
     a l'endroit exact ou ils ont fait devier la trajectoire.
  3. LES BRANCHES - les fils ouverts en cours de route, chacun avec son etat :
     vivant / clos / gele, et pourquoi.
  4. "TU ES ICI" - un marqueur unique sur le tronc. Sans lui la carte raconte le
     passe au lieu de situer le present.
  5. LES DETTES - ce qui reste a faire, rattache au fil dont ca depend.
  6. UNE URL STABLE par chantier, mise a jour EN PLACE (parametre url de l'outil
     Artifact) - jamais un nouveau lien a chaque revision."""


def _lire_etat(chemin):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:
        return {"tours": 0, "bifurcations": 0, "dernier_rappel": 0}


def _carte_existe(transcript):
    """Une URL d'artefact a-t-elle deja ete produite ? Lit la fin du transcript."""
    try:
        p = Path(transcript)
        taille = p.stat().st_size
        with p.open("rb") as f:
            f.seek(max(0, taille - QUEUE_OCTETS))
            bloc = f.read().decode("utf-8", errors="ignore")
        return bool(_ARTEFACT.search(bloc))
    except Exception:
        return False


def main():
    if os.environ.get("CLAUDE_RAPPEL_CARTE", "").lower() == "off":
        return 0
    try:                                   # ceinture : stdout en UTF-8 quoi qu'il arrive
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        entree = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0

    session = str(entree.get("session_id") or "inconnue")[:8]
    prompt = entree.get("prompt") or ""

    DOSSIER.mkdir(parents=True, exist_ok=True)
    chemin = DOSSIER / ("%s.json" % session)
    etat = _lire_etat(chemin)

    etat["tours"] = etat.get("tours", 0) + 1
    if _DEBUT.match(prompt) or _CORPS.search(prompt):
        etat["bifurcations"] = etat.get("bifurcations", 0) + 1
    try:
        chemin.write_text(json.dumps(etat), encoding="utf-8")
    except Exception:
        pass

    if etat["tours"] < TOURS_MIN or etat["bifurcations"] < BIFURC_MIN:
        return 0
    if etat["tours"] - etat.get("dernier_rappel", 0) < ECART_RELANCE:
        return 0

    etat["dernier_rappel"] = etat["tours"]
    try:
        chemin.write_text(json.dumps(etat), encoding="utf-8")
    except Exception:
        pass

    deja = _carte_existe(entree.get("transcript_path") or "")
    entete = ("[carte] session a %d tours dont %d bifurcations."
              % (etat["tours"], etat["bifurcations"]))
    if deja:
        corps = ('Une carte a ete publiee dans cette session. Verifie qu\'elle est a jour '
                 'AVANT de repondre : les %d derniers tours y figurent-ils, le marqueur '
                 '"tu es ici" est-il au bon endroit ? Si non, mets-la a jour en place '
                 '(meme URL) et donne le lien.' % ECART_RELANCE)
    else:
        corps = ("Aucune carte publiee. Propose-en une avant de repondre : un artefact, "
                 "une seule URL pour tout le chantier.\n" + GABARIT)

    sys.stdout.write(entete + " " + corps + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
