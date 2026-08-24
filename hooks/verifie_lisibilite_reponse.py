"""Hook Stop — retient UNE fois une reponse longue et sous-structuree a une demande
multiple, et force soit la restructuration, soit une derogation ecrite.

STATUT : ecrit, teste, mesure — et **DECONSEILLE AU DEPLOIEMENT**. Ce fichier est
inerte (aucune cle "Stop" dans settings.hooks.json) et le rejeu sur l'historique dit
de l'y laisser. Il est conserve comme resultat negatif documente, pour qu'on ne
refasse pas la tentative dans six mois.

VERDICT DU REJEU (246 tours reels, 14 transcripts, 2026-08-24) — trois metriques
essayees, aucune ne separe le pathologique du normal :

  1. « aucun repere de structure »        ->   3 declenchements / 246  (1,2 %)
     Sous son propre seuil d'abandon (« <3 en 2 semaines -> retirer »). Une seule
     puce perdue dans la prose suffit a le faire taire.
  2. « moins de reperes que de demandes » ->   3 declenchements / 246  (idem)
     Elargir le detecteur de demandes (29 -> 32 tours a risque) ne bouge rien :
     le verrou n'etait pas la detection.
  3. « paragraphes de prose »             -> 62 a 96 % des reponses longues
     Mediane a 6 paragraphes, plus longue serie a 3 d'affilee. Distribution
     unimodale et lisse : aucun seuil n'isole une queue.

CONCLUSION, et c'est elle qui compte : le « pate de texte » n'est pas une anomalie
de mes reponses, c'est leur FORME PAR DEFAUT. Un hook attrape des exceptions ; il ne
peut pas gater une norme. Tout seuil qui declenche assez pour servir declenche sur
la moitie des tours, et tout seuil assez rare pour etre tolerable ne declenche
jamais. Le correctif n'est pas mecanique, il est dans la forme par defaut elle-meme.

Chiffre utile qui sort de la mesure : la mediane de mes reponses longues tient
**3 paragraphes de prose d'affilee au maximum**. C'est un plafond deja atteint la
moitie du temps — donc tenable, et verifiable a l'oeil sans aucun script.

--------------------------------------------------------------------------------
CE QUE CE HOOK FAIT DONC A LA PLACE : IL OBSERVE, IL NE BLOQUE PAS
--------------------------------------------------------------------------------
Mode par defaut = **observation**. Il n'interrompt jamais rien : il ecrit une ligne
par reponse longue dans mesures.csv (longueur, nb de demandes, tableaux, puces,
titres, plus longue serie de prose). C'est le trou reel du diagnostic du 24/08 :
la regle de style existait depuis des mois et **rien ne mesurait son respect** —
le seul chiffre disponible datait de juillet et n'avait jamais ete reactualise.
Sans mesure entretenue, aucune boucle de correction n'est possible.

Cout pour l'utilisateur : nul. Aucune interruption, aucun faux positif possible,
aucun ceremonial sur les tours triviaux. C'est la seule version de ce hook qui ne
puisse pas rejoindre le cimetiere des garde-fous decoratifs — elle ne pretend pas
bloquer, elle pretend compter, et elle compte.

Mode bloquant conserve derriere CLAUDE_VERIFIE_LISIBILITE=bloquant, documente
comme deconseille par les chiffres ci-dessus. Ne pas l'activer sans une raison neuve.

--------------------------------------------------------------------------------
CE QUI A ETE VERIFIE, PAS SUPPOSE (2026-08-24)
--------------------------------------------------------------------------------
1. L'evenement Stop existe. Verifie par lecture directe du binaire
   (<HOME>/.local/bin/claude, 307 Mo) : le code qui construit le payload
   contient litteralement
       hook_event_name:"Stop", stop_hook_active:n, last_assistant_message:p
   Aucun des 5 evenements deja cables (SessionStart, UserPromptSubmit, PreToolUse,
   PostToolUse, PreCompact) ne donne acces au texte final de la reponse.

2. L'anti-boucle est documente dans le binaire lui-meme :
   "For Stop/SubagentStop hooks, check stop_hook_active in the input and return
    success while it's true. Set CLAUDE_CODE_STOP_HOOK_BLOCK_CAP to raise this limit."

3. LE SEUIL A ETE MESURE, PAS CHOISI. Rejeu du hook sur 245 tours reels
   (14 transcripts, scratchpad/dryrun_hook.py). La premiere version proposee
   bloquait quand la reponse ne contenait AUCUNE structure : elle se serait
   declenchee **2 fois sur 245 tours**, soit sous son propre seuil d'echec
   ("<3 declenchements en 2 semaines -> retirer"). Morte avant deploiement, parce
   qu'une seule puce perdue au milieu de la prose suffisait a la faire taire.
   Quatre regles comparees sur les 44 tours a risque (demande multiple ET >2000 car) :
       aucune structure du tout ..................  2  ( 5 %)   <- inutilisable
       ni tableau ni titre ....................... 30  (68 %)   <- trop large
       densite < 1 marque / 800 caracteres ....... 15  (34 %)
       marques < nombre de demandes .............. 12  (27 %)   <- retenue
   La regle retenue est la seule qui dise quelque chose de vrai : si la demande
   portait sur 4 choses, la reponse doit porter au moins 4 reperes visuels.
   Elle est indexee sur la demande, pas sur la longueur.

--------------------------------------------------------------------------------
CE QUE CE HOOK NE FAIT PAS
--------------------------------------------------------------------------------
Il ne lit pas le sens. Il ne verifie pas que chaque sous-question a recu une
reponse — aucun candidat teste ne sait le faire sans lire le fond, et la mesure du
24/08 (48 sous-demandes lues a la main) montre que le vrai defaut de couverture
survient dans des reponses DEJA structurees. Ce hook traite la forme. La couverture
du fond reste un angle mort declare.

Fail-open assume sur toute erreur de lecture : un verificateur de style ne doit
jamais empecher une reponse de partir.
Interrupteur : CLAUDE_VERIFIE_LISIBILITE=off.
"""
import datetime
import json
import os
import re
import sys
from pathlib import Path

DOSSIER = Path(os.environ.get("CLAUDE_VERIFIE_LISIBILITE_DOSSIER")
               or Path.home() / ".claude" / "verifie-lisibilite")
QUEUE_OCTETS = 2_000_000
SEUIL_DEMANDES = 2
SEUIL_CARACTERES = 2000

_TABLE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*\|", re.MULTILINE)
_PUCES = re.compile(r"^\s*[-*\u2022]\s", re.MULTILINE)
_TITRES = re.compile(r"^#{1,6}\s", re.MULTILINE)
_NUMEROTE = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)
_DEROGATION = re.compile(r"[E\u00c9e\u00e9]cart d[\u00e9e]clar[\u00e9e]", re.IGNORECASE)

_PHRASES = re.compile(r"[.!?\n]+")
# Interrogatifs et verbes de demande les plus frequents chez cet utilisateur.
# Volontairement court : un detecteur trop large gonfle le signal et fait bloquer
# des tours a demande unique.
# Interrogatifs : liste volontairement PLUS COURTE que celle de la mesure du 24/08,
# qui comptait \u00ab que \u00bb et \u00ab qu' \u00bb \u2014 donc toute subordonnee ordinaire (\u00ab je pense que\u2026 \u00bb).
# Ces deux marqueurs gonflaient le compte sans designer une demande.
_INTERRO = re.compile(
    r"^\s*(est-ce que|est ce que|qu'est-ce|qu est ce|pourquoi|comment|combien|quand|"
    r"o\u00f9 est|ou est|quel |quelle |quels |quelles |peux-tu|peux tu|pourrais-tu|pourrais tu|"
    r"as-tu|as tu|sais-tu|sais tu|y a-t-il|saurais|"
    r"what |why |how |when |which |can you|could you|would you|do you)",
    re.IGNORECASE)
# Imperatifs : verbe en tete de phrase. C'est le signal fiable \u2014 une phrase qui
# commence par \u00ab corrige \u00bb ou \u00ab verifie \u00bb EST une demande, sans ambiguite.
_IMPERATIF = re.compile(
    r"^\s*(fais|va |vas-y|vas y|regarde|verifie|v\u00e9rifie|corrige|explique|ecris|\u00e9cris|reecris|r\u00e9\u00e9cris|"
    r"genere|g\u00e9n\u00e8re|analyse|compare|donne|dis|dites|montre|liste|identifie|propose|resume|r\u00e9sume|"
    r"cree|cr\u00e9e|ajoute|modifie|lance|execute|ex\u00e9cute|produis|rends|cherche|teste|revise|r\u00e9vise|"
    r"audite|mesure|calcule|reflechis|r\u00e9fl\u00e9chis|assure-toi|relis|reponds|r\u00e9ponds|prends|mets|"
    r"construis|developpe|d\u00e9veloppe|implemente|impl\u00e9mente|trouve|decris|d\u00e9cris|indique|precise|"
    r"pr\u00e9cise|confirme|valide|aide|continue|poursuis|arrete|arr\u00eate|note|enregistre|sauvegarde|"
    r"envoie|publie|deploie|d\u00e9ploie|ouvre|ferme|supprime|retire|enleve|enl\u00e8ve|complete|compl\u00e8te|"
    r"termine|finis|lis |prepare|pr\u00e9pare|planifie|organise|structure|formate|traduis|synthetise|"
    r"synth\u00e9tise|detaille|d\u00e9taille|classe|trie|filtre|separe|s\u00e9pare|combine|fusionne|decoupe|"
    r"d\u00e9coupe|commence|recommence|documente|reprends|refais|integre|int\u00e8gre|schematise|sch\u00e9matise)\b",
    re.IGNORECASE)


def _compte_demandes(texte):
    """Nombre de sous-demandes distinctes : le max entre les '?' et les phrases
    interrogatives ou imperatives. Le seul comptage des '?' ratait la moitie des
    tours multi-demandes (22 detectes contre 33 reels, mesure du 24/08)."""
    n_q = texte.count("?")
    n_p = 0
    for phrase in _PHRASES.split(texte):
        p = phrase.strip()
        if len(p) < 3:
            continue
        if _INTERRO.match(p) or _IMPERATIF.match(p):
            n_p += 1
    return max(n_q, n_p)


def _marques_structure(texte):
    """Reperes visuels. Un tableau vaut 3 : il porte plus d'information de structure
    qu'une puce isolee."""
    return (len(_PUCES.findall(texte))
            + len(_TITRES.findall(texte))
            + len(_NUMEROTE.findall(texte))
            + 3 * len(_TABLE.findall(texte)))


def _texte_final(entree):
    brut = entree.get("last_assistant_message")
    if isinstance(brut, str):
        return brut
    if isinstance(brut, list):
        return "\n".join(b["text"] for b in brut
                         if isinstance(b, dict) and isinstance(b.get("text"), str))
    if isinstance(brut, dict) and isinstance(brut.get("text"), str):
        return brut["text"]
    return ""


def _derniere_demande_humaine(transcript):
    """Dernier vrai tour humain : ni tool_result, ni meta, ni resume de compaction."""
    try:
        taille = transcript.stat().st_size
        with transcript.open("rb") as f:
            f.seek(max(0, taille - QUEUE_OCTETS))
            brut = f.read().decode("utf-8", errors="ignore")
        lignes = brut.split("\n")
        if taille > QUEUE_OCTETS and lignes:
            lignes.pop(0)
        for ligne in reversed(lignes):
            if '"kind"' not in ligne or '"human"' not in ligne:
                continue
            try:
                entree = json.loads(ligne)
            except Exception:
                continue
            if entree.get("isMeta") or entree.get("isCompactSummary"):
                continue
            origin = entree.get("origin") or {}
            msg = entree.get("message") or {}
            if (origin.get("kind") == "human" and msg.get("role") == "user"
                    and isinstance(msg.get("content"), str)):
                return msg["content"]
    except Exception:
        pass
    return ""


_MARQUE_DEBUT = re.compile(r"^\s*([-*•]\s|#{1,6}\s|\d+[.)]\s|\|)")


def _serie_prose_max(texte):
    """Plus longue serie de paragraphes de prose consecutifs, sans repere entre eux.
    C'est LA metrique qui correspond a « trois pages de prose » — pas le total."""
    cur = mx = 0
    for bloc in re.split(r"\n\s*\n", texte):
        b = bloc.strip()
        if not b:
            continue
        if _MARQUE_DEBUT.match(b) or len(b) < 120:
            cur = 0
        else:
            cur += 1
            mx = max(mx, cur)
    return mx


def _mesurer(session, reponse, n_dem):
    """Une ligne par reponse longue. Mode observation : c'est tout ce que fait le hook
    par defaut. Sans cette trace, personne ne saura jamais si la regle est tenue —
    c'est exactement le trou qui a rendu decoratifs les trois garde-fous precedents."""
    try:
        DOSSIER.mkdir(parents=True, exist_ok=True)
        fichier = DOSSIER / "mesures.csv"
        neuf = not fichier.exists()
        with fichier.open("a", encoding="utf-8") as f:
            if neuf:
                f.write("horodatage;session;caracteres;demandes;tableaux;puces;titres;"
                        "numerotes;serie_prose_max\n")
            f.write(";".join(str(x) for x in (
                datetime.datetime.now().isoformat(timespec="seconds"),
                session,
                len(reponse),
                n_dem,
                len(_TABLE.findall(reponse)),
                len(_PUCES.findall(reponse)),
                len(_TITRES.findall(reponse)),
                len(_NUMEROTE.findall(reponse)),
                _serie_prose_max(reponse),
            )) + "\n")
    except Exception:
        pass


def main():
    try:
        if os.environ.get("CLAUDE_VERIFIE_LISIBILITE", "").lower() == "off":
            return 0
        entree = json.load(sys.stdin)

        if entree.get("hook_event_name") == "SubagentStop":
            return 0
        if entree.get("stop_hook_active"):
            return 0

        reponse = _texte_final(entree)
        n_car = len(reponse)
        if n_car <= SEUIL_CARACTERES:
            return 0

        demande = _derniere_demande_humaine(Path(entree.get("transcript_path") or ""))
        n_dem = _compte_demandes(demande)
        session = str(entree.get("session_id") or "inconnue")[:8]

        # --- mode par defaut : observer, ne jamais interrompre ---
        _mesurer(session, reponse, n_dem)
        if os.environ.get("CLAUDE_VERIFIE_LISIBILITE", "").lower() != "bloquant":
            return 0

        # --- mode bloquant, deconseille par la mesure (voir en-tete) ---
        if n_dem < SEUIL_DEMANDES:
            return 0
        if _DEROGATION.search(reponse):
            return 0
        n_marques = _marques_structure(reponse)
        if n_marques >= n_dem:
            return 0

        print(json.dumps({
            "decision": "block",
            "reason": (
                f"Retenu avant envoi. La demande porte sur {n_dem} points, la reponse fait "
                f"{n_car} caracteres et ne contient que {n_marques} repere(s) de structure. "
                "Reprends la reponse avec un repere par point demande (tableau, puces ou "
                "titres — une entree par sous-demande), et verifie qu'aucune sous-demande "
                "n'est restee sans reponse. Si la prose continue est vraiment le bon format "
                "ici, ecris a la place une ligne 'Ecart declare : <regle>, <raison courte>' "
                "et conclus. Ne repete pas ce message."
            ),
            "systemMessage": (
                f"[lisibilite] {n_dem} demandes · {n_car} car. · {n_marques} reperes "
                "-> reponse renvoyee pour restructuration ou derogation."
            ),
        }, ensure_ascii=True))
    except Exception as exc:
        try:
            DOSSIER.mkdir(parents=True, exist_ok=True)
            with (DOSSIER / "ECHEC.log").open("a", encoding="utf-8") as f:
                f.write(f"{datetime.datetime.now().isoformat()} {type(exc).__name__}: {exc}\n")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
