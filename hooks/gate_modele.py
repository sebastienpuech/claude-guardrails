"""Hook UserPromptSubmit : force une evaluation modele/effort avant tout travail.

Probleme : le modele et l'effort sont choisis une fois et plus jamais reconsideres.
Le defaut Opus 5 / xhigh tourne aussi bien sur « ou est ce fichier ? » que sur
« on refait le moteur meta ». Le premier surpaie, le second sous-traite.

Trois designs ont ete essayes et ecartes avant celui-la (session du 24/08/2026) :

1. Classifieur par mots-cles. Mort sur « demontre que tout groupe d'ordre p2 est
   abelien » : quatre mots, zero fichier, et il faut Fable 5. Un lexique de preuve
   rattrape ce cas-la, mais pas « c'est quoi un groupe abelien ? » qui porte les
   memes mots pour une reponse d'une phrase. Le lexique dit le DOMAINE, jamais la
   PROFONDEUR dedans.
2. Appel LLM dedie avant chaque prompt. Mort sur l'infrastructure : pas de cle API
   sur cette machine, tout passe par le forfait Max via l'Agent SDK, qui relance le
   CLI claude (spawns jusqu'a 180 s documentes dans un-autre-projet/agents/llm_client.py).
   Plusieurs secondes ajoutees entre la touche Entree et la reponse.
3. Blocage (exit 2). Mort sur la doc : UserPromptSubmit qui bloque EFFACE le prompt
   tape. Rattrapable via le presse-papier, mais devenu inutile une fois (4) trouve.

4. Retenu — le hook ne juge rien. Il injecte une consigne dans le contexte, et c'est
   le modele deja charge qui evalue : lui seul sait que « on refait le moteur meta »
   designe trois semaines de travail. Cout : ~100 tokens par prompt, zero processus,
   zero latence. La profondeur d'un travail n'est pas une propriete du texte du
   prompt — c'est une propriete du travail, que le texte ne fait que designer.

Le bareme croise DEUX axes, pas un (corrige le 24/08 apres verification a l'ecran) :
la profondeur du noyau (fable ou non) et le decoupage du travail (ultracode ou non).
« ultracode » n'est PAS une valeur d'effort -- les transcripts ne connaissent que
high/xhigh/max (16 419 tours mesures, zero « ultracode »). C'est la position haute du
selecteur de Claude Code, qui pose max ET allume l'orchestration multi-agents en un
seul geste ; elle est proposee sur Fable comme sur Opus. On ne peut donc pas cumuler
« max » et « ultracode » : ce sont deux crans du meme curseur.

Deuxieme limite, structurelle : la lecture du reglage a TOUJOURS un tour de retard. Ce
hook s'execute avant que la reponse du tour courant soit ecrite dans le transcript, et
l'effort courant n'existe nulle part ailleurs (verifie le 24/08 : absent des niveaux
User et Machine, absent de PowerShell, absent de l'environnement des hooks). Mesure :
bascule xhigh -> high a 18:11, le hook annoncait encore xhigh au prompt suivant. Non
reparable en lisant ailleurs, donc DIT dans la consigne — sinon une bascule volontaire
declenche un faux positif juste apres que l'utilisateur a eu raison.

Limite assumee : ce hook ne peut pas EMPECHER. Il obtient au mieux un arret volontaire
en debut de tour, avant la partie chere. C'est moins etanche qu'un blocage, en echange
c'est le seul mecanisme qui voit ce qu'il faut voir.

DEROGATION ASSUMEE a doctrine.md principe 1 (fail-closed), meme raison qu'alerte_contexte :
ce n'est pas un verifieur, c'est un conseil. S'il plante il ne doit rien casser. Fail-open,
exit 0 toujours. Et surtout stdout MUET en cas d'echec : ici stdout entre dans le contexte
du modele, un demi-message injecte serait pire que pas de hook du tout.

Confidentialite : ne lit jamais le texte des messages, ni le prompt (il n'en a pas besoin).
Seulement l'identifiant de modele et le niveau d'effort.
"""
import datetime
import json
import os
import sys
from pathlib import Path

DOSSIER = Path(os.environ.get("CLAUDE_GATE_MODELE_DOSSIER")
               or Path.home() / ".claude" / "gate-modele")
QUEUE_OCTETS = 2_000_000  # un transcript peut peser 47 Mo : on n'en lit que la fin
MARQUEUR = "[[MODELE]]"   # ASCII volontaire : greppable, aucun risque d'encodage Windows

CONSIGNE = """[reglage courant : modele={modele} / effort={effort}]
Avant de traiter ce message, juge l'ampleur et la profondeur REELLES du travail
demande -- pas la longueur du message. Deux axes : la PROFONDEUR du noyau (fable
s'il est dur : preuve, arbitrage d'architecture, philo ou meta a enjeu) et le
DECOUPAGE (ultracode si le travail se scinde vraiment en N parties parallelisables).
  consultation, lookup, geste mecanique ...... claude-sonnet-5 / medium
  travail courant (code, doc, correction) .... claude-opus-5 / high
  probleme dur, indivisible, plan ............ claude-opus-5 / xhigh
  noyau dur, indivisible, a enjeu ............ claude-fable-5 / max
  large et decoupable, noyau simple .......... claude-opus-5 / ultracode
  large et decoupable, noyau dur (refonte) ... claude-fable-5 / ultracode
ultracode lance N agents en parallele : c'est le cran le plus cher, et jamais un
substitut a la profondeur -- le nombre ne demontre pas un theoreme.
Si le reglage courant convient : NE DIS RIEN, travaille normalement.
Sinon : reponds UNIQUEMENT "{marqueur} <modele> + <effort> -- <raison en 8 mots>"
et arrete-toi la. En cours de session, ne signale qu'un ecart net : basculer
invalide le cache de contexte et se paie. Enfin, le reglage affiche ci-dessus est lu
sur le tour PRECEDENT (le tour courant n'est pas encore ecrit au moment de ce hook) :
s'il vient de changer, cette lecture est perimee -- ne signale jamais un ecart que
l'utilisateur vient lui-meme de corriger."""


def _effort_env() -> str:
    return os.environ.get("CLAUDE_EFFORT") or "inconnu"


def _reglage_courant(transcript: Path, settings: Path):
    """(modele, effort) tels que Claude Code les a REELLEMENT utilises au dernier tour.

    Les deux valeurs vivent sur la meme ligne du transcript : les entrees "assistant"
    portent `message.model` et, a la racine, `effort`. C'est la source de verite --
    mieux que la variable d'environnement CLAUDE_EFFORT, dont rien ne garantissait
    qu'elle soit visible d'un processus lance par Claude Code. Constate le 24/08/2026 :
    le champ existait dans le transcript, la question de l'heritage est devenue sans
    objet. L'environnement ne sert plus que de repli.

    Au tout premier prompt d'une session, aucune reponse d'assistant n'est encore
    ecrite : repli sur le defaut de settings.json, en annoncant que ce n'est pas
    confirme plutot qu'en inventant une valeur.
    """
    try:
        taille = transcript.stat().st_size
        with transcript.open("rb") as f:
            f.seek(max(0, taille - QUEUE_OCTETS))
            brut = f.read().decode("utf-8", errors="ignore")
        for ligne in reversed(brut.split("\n")):
            if '"model"' not in ligne:
                continue
            try:
                entree = json.loads(ligne)
            except Exception:
                continue  # ligne tronquee par la lecture en queue, ou corrompue
            modele = (entree.get("message") or {}).get("model")
            if modele:
                return str(modele), str(entree.get("effort") or _effort_env())
    except Exception:
        pass
    modele = "?"
    try:
        defaut = json.loads(settings.read_text(encoding="utf-8")).get("model")
        if defaut:
            modele = f"{defaut} (defaut settings.json, pas encore confirme)"
    except Exception:
        pass
    return modele, _effort_env()


def _tracer(session: str, modele: str, effort: str) -> None:
    """Une ligne par session : ce que le hook a vu. Sert a la mesure a posteriori.

    Appele APRES l'ecriture sur stdout, jamais avant : la trace est un confort, la
    consigne est le produit. L'ordre inverse a supprime une injection entiere le
    24/08/2026, parce qu'un dossier de trace n'etait pas creable.
    """
    marqueur = DOSSIER / f"{session}.txt"
    if marqueur.exists():
        return
    DOSSIER.mkdir(parents=True, exist_ok=True)
    marqueur.write_text(
        f"{datetime.datetime.now().isoformat()} modele={modele} effort={effort}\n",
        encoding="utf-8")


def main() -> int:
    try:
        if os.environ.get("CLAUDE_GATE_MODELE", "").lower() == "off":
            return 0
        entree = json.load(sys.stdin)
        modele, effort = _reglage_courant(
            Path(entree.get("transcript_path") or ""),
            Path.home() / ".claude" / "settings.json")
        # Chaine construite ENTIEREMENT avant impression : un plantage a mi-parcours
        # doit laisser stdout vide, jamais y deposer un demi-message.
        texte = CONSIGNE.format(modele=modele, effort=effort, marqueur=MARQUEUR)
        sys.stdout.write(texte + "\n")
        try:
            _tracer(str(entree.get("session_id") or "inconnue")[:8], modele, effort)
        except Exception:
            pass  # la trace ne doit jamais compromettre une injection deja emise
    except Exception as exc:  # fail-open assume : ne jamais gener une demande
        try:
            DOSSIER.mkdir(parents=True, exist_ok=True)
            (DOSSIER / "ECHEC.log").open("a", encoding="utf-8").write(
                f"{datetime.datetime.now().isoformat()} {type(exc).__name__}: {exc}\n"
            )
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
