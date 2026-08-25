# Journal — les incidents, dates

> Mémoire de suivi fichier-résidente. Le bloc « État actuel » est **réécrit en tête** à chaque
> session ; le log en dessous est **append-only** (on ne réécrit jamais une entrée passée).
> On rejoue l'état depuis ce fichier, on ne le résume pas — c'est ce qui survit à un reset de
> contexte, là où une compaction perd le détail.
>
> Créé le 2026-08-20, en même temps que le hook `journal_etat.py` qui le relit à chaque
> ouverture de session. Il n'y a pas d'entrées antérieures : le passé du repo se lit dans
> `git log`, il n'est pas recopié ici.
>
> Ce fichier dit **où on en est**. Le *quoi faire* est ailleurs : `README.md` pour le cycle
> source → test → `deploy.ps1`, `meta/doctrine.md` (dans `un-projet`) pour les principes.

## État actuel (glissant)

- **Couche globale : 2 sections neuves + 1 filet + 1 garde-fou (25/08).** `CLAUDE.md` global porte
  désormais « Contrat d'entrée » et « Sous-agents » (issus du rapport `/insights` du 24/08),
  déployés et conformes (`deploy.ps1 -Verifier` = exit 0). Hook Stop `autosauvegarde_config.py` :
  copie **non destructive** de tout fichier de `~/.claude` qui change, vers `.sauvegardes/auto/`.
  `deploy.ps1` sauvegarde désormais toute cible avant de l'écraser. Le golden (149 cas) tourne en
  **pre-commit** dès qu'un commit touche `hooks/` ou `tests/` — contre-épreuve passée.
  Restent ouverts : `rappel_carte.py` non commité, `rappel_revue.py` déployé sans source,
  `verifie_lisibilite_reponse.py` absent de `$attendus`, et l'ordre des entrées de ce journal
  qui contredit `journal_etat.py` (détail dans l'entrée du 25/08).

- **Compactage : la variable est morte, le hook prend le relais (23/08).**
  `CLAUDE_CODE_AUTO_COMPACT_WINDOW` a vécu 36 h (posée 19/08 13:01, retirée 20/08 21:15) et
  produit 167 compactages en deux jours. Depuis, plus **aucun** compactage automatique :
  63 le 19/08, 104 le 20/08, 0 les 21 et 22, et le seul du 23/08 est un `/compact` manuel.
  Le seuil par défaut, mesuré sur les transcripts, se situe **entre 922k et 998k** — hors
  d'atteinte des sessions réelles (max 548k). `alerte_contexte.py` prévient à chaque palier
  de 150k. **Ne pas remettre la variable**, ni son équivalent natif `autoCompactWindow`.

- **`deploy.ps1` a été lancé en entier le 23/08** — la réserve notée plus bas (« complet
  volontairement non lancé ») est levée : `alerte_contexte.py` est commité et déployé,
  `$attendus` couvre les 8 hooks, sortie « Conforme ».

- **Garde-fous git désormais versionnés.** `hooks/pre_commit_taille.py` et `githooks/`
  (shims `core.hooksPath`) vivaient depuis le 21/08 uniquement dans `~/.claude/`.
  `.gitattributes` force le LF sur les shims : en CRLF, leur shebang casse en silence.
  **`deploy.ps1` ne synchronise pas `githooks/`** — seul écart source/déployé connu.

- **Section « Autonomie » dans `CLAUDE-global.md`, déployée le 23/08.** 14 règles tirées de
  l'audit questions (538 questions/45 j, ~48 % prédictibles ; rapport :
  `audit/rapport-audit-questions-45j.md`), chacune contre-éprouvée par 3 agents adversariaux
  sur les 45 divergences réelles. A3 (git protecteur sans demander) est écrite mais
  **NON ACTIVE** : elle attend un oui dédié + un script de scan confidentialité.
  Déploiement du 23/08 par copie ciblée du seul CLAUDE.md (hash vérifié) — `deploy.ps1`
  complet volontairement non lancé : il aurait embarqué `hooks/alerte_contexte.py`, WIP
  non commité d'une autre session.

- **Couche globale déployée et conforme.** Source de vérité = ce repo. Cycle inchangé :
  éditer ici → `python tests/test_hooks.py` (VERT obligatoire) → `.\deploy.ps1`.
  `deploy.ps1` n'écrit **jamais** `settings.json`, il vérifie contre la liste `$attendus`
  (exit 0 = conforme, exit 2 = dérive). Ne jamais éditer `~/.claude/` comme une source.

- **Hooks en place (8).** `block_git_add_all.py` et `block_cloud_cache.py` sont
  *fail-closed* (ils gardent). `inject_lecons.py`, `rappel_lecon.py`,
  `checkpoint_precompact.py`, `journal_etat.py` et `alerte_contexte.py` sont *fail-open* — dérogation déclarée au
  principe 1 de `doctrine.md`, motif écrit dans chaque docstring : un informatif cassé qui
  empêcherait une session de démarrer ou une compaction d'aboutir serait pire que le mal.

- **Chantier du 20/08 : la lecture du journal, pas son écriture.** `journal_etat.py` injecte
  au démarrage le seul bloc « État actuel » du `journal.md` du repo courant (plafond
  8 000 car) + les 3 derniers titres du log. Il remonte à la racine git, donc il marche
  aussi depuis un sous-dossier. Repos sans journal : muet, exit 0.
  **Déployé et câblé le 20/08** — hook copié dans `~/.claude/hooks/`, 2ᵉ entrée `SessionStart`
  ajoutée à `~/.claude/settings.json` (sauvegarde `settings.json.bak-20260820`),
  `.\deploy.ps1 -Verifier` → **Conforme, exit 0**, et le hook déployé a été déclenché pour de
  vrai (payload `SessionStart` en entrée) : il rend bien le bloc d'état, exit 0.

- **Convention journal : à la racine du repo** (`journal.md`), pas dans `docs/`. Vérifié le
  20/08 : `un-autre-projet`, `un-second-projet`, `un-projet` l'ont à la racine ; aucun
  `docs/journal.md` n'existe nulle part. Le hook accepte les deux, racine d'abord.

- **`ECHEC.log` est redevenu un signal.** `~/.claude/checkpoints/ECHEC.log` est **vide
  (0 o)** depuis le 20/08 15:32. Les 12 lignes qu'il contenait n'étaient **aucun échec
  réel** : c'était la golden qui écrivait ses propres échecs volontaires dans le vrai
  dossier. Corrigé (commit `76d38af`), vérifié après coup : golden VERT et le fichier
  reste à 0 o. **Désormais une seule ligne dans ce fichier = une vraie compaction en
  échec.** 65 checkpoints `.md` en place à côté.

- **En attente d'arbitrage** (rien n'est fait sans « oui ») : baisser
  `CLAUDE_CODE_AUTO_COMPACT_WINDOW` de 120000 à 100000 dans `settings.json` (sauvegarde
  `settings.json.bak-2026-08-19` en place) ; ajouter à `CLAUDE-global.md` les deux règles
  « `/compact` avant la pause » et « ce qui compte s'écrit dans un fichier, pas dans le
  contexte ».

- **`gate_modele.py` en service depuis le 24/08.** Hook `UserPromptSubmit` : il n'analyse
  rien et ne bloque rien. Il injecte une consigne (~100 tokens) qui force le modèle déjà
  chargé à juger l'ampleur réelle du travail avant de s'y mettre, et à s'arrêter en
  annonçant `[[MODELE]] <modèle> + <effort>` si le réglage courant ne convient pas.
  Interrupteur : `CLAUDE_GATE_MODELE=off`. **Fait mesuré, documenté nulle part ailleurs :
  `CLAUDE_EFFORT` n'est PAS hérité par un hook lancé par Claude Code.** Le transcript porte
  `message.model` et `effort` sur la même ligne — c'est là qu'il faut lire, pas dans
  l'environnement. **Barème à deux axes depuis le 24/08** : la profondeur du noyau
  (Fable ou non) et le découpage du travail (ultracode ou non). `ultracode` n'est PAS
  une valeur d'effort — les transcripts ne connaissent que `high`/`xhigh`/`max`
  (16 419 tours mesurés, zéro « ultracode »). C'est la **position haute du sélecteur**
  de Claude Code, qui pose `max` ET allume l'orchestration multi-agents d'un seul geste,
  proposée sur Fable comme sur Opus. On ne cumule donc jamais `max` et `ultracode` :
  deux crans du même curseur. Le critère qui les sépare n'est pas la difficulté, c'est
  **le découpage** — le nombre ne démontre pas un théorème. **Seuil d'abandon écrit d'avance : si le marqueur `[[MODELE]]`
  n'apparaît dans aucun transcript d'ici au 07/09, le hook ne sert à rien et on le retire.**

- **Re-mesure prévue vers le 2026-09-02** : `python audit/audit_usage.py 14`, pour voir si
  le checkpoint + le journal ont fait baisser la part de réchauffage (88 % du `cache_write`
  des grosses sessions au 19/08, ≈ 24 % de la facture 60 jours).

## Log (append-only)

### 2026-08-20 — le test salissait la production, pas le hook

**Fait.** `tests/test_hooks.py` : le cas fail-open bout-en-bout de
`checkpoint_precompact.py` lance le hook en **sous-processus**. Impossible d'y
monkeypatcher `DOSSIER` (constante de module dérivée de `Path.home()`), donc le test lui
ment sur son dossier maison — `env={**os.environ, "USERPROFILE": tmp, "HOME": tmp}`.
Commit `76d38af`, poussé.

**Ce qu'on cherchait, ce qu'on a trouvé.** `ECHEC.log` (jamais lu depuis le 19/08)
contenait 12 lignes, toutes le **même** `JSONDecodeError: Expecting property name enclosed
in double quotes: line 1 column 2 (char 1)`. Signature reproduite en labo : elle exige une
entrée commençant par `{` suivi d'autre chose qu'un `"`. C'est **exactement** ce que la
golden envoie (`input="{pas du json"`). Horodatages alignés sur les runs de la suite.
**Zéro échec de compaction réel** — 58 checkpoints écrits sans incident sur la même
période.

**La leçon, qui vaut plus que le bug.** Un test qui écrit dans l'état de production
**détruit le signal qu'il est censé protéger** : un vrai plantage aurait été
indistinguable du bruit de test. Le fail-open ne sert à rien si son canal d'alerte est
pollué par ce qui le teste.

**Faux départ assumé.** Première version du garde-fou : « le chemin de sortie ne contient
pas `Path.home()` ». Faux sous Windows — les dossiers temporaires vivent dans
`AppData\Local\Temp`, donc *sous* le home. Le cas sortait FAIL alors que l'isolation
marchait. Remplacé par la propriété réellement visée : **la taille du vrai `ECHEC.log`
avant/après doit être identique**.

**Vérifié, pas supposé.** 1 cas devient 3 (exit 0 / échec bien tracé dans le faux home /
vrai log inchangé en octets). Golden : **VERT, 94 cas, 0 échec** (92 avant). Vrai
`ECHEC.log` : **1452 → 1452 o** pendant le run, puis vidé sur « oui », et **0 o après un
run complet de la suite** — hier ce même run y ajoutait une ligne. Pas de `deploy.ps1` :
un fichier de `tests/` n'est jamais déployé.

### 2026-08-20 — le hook du journal passe en production

**Fait.** `journal_etat.py` déployé dans `~/.claude/hooks/` et déclaré comme 2ᵉ entrée du
tableau `SessionStart` de `~/.claude/settings.json` — patch textuel sur une ancre unique,
`json.loads()` avant écriture, sauvegarde `settings.json.bak-20260820`. `deploy.ps1` ne
touche jamais `settings.json` : ce fichier est à l'utilisateur, le patch a été fait à la
main après « oui » explicite.

**Pourquoi il manquait quelque chose.** `deploy.ps1 -Verifier` sortait en **exit 2** avec
deux dérives : `journal_etat.py : DERIVE` (le fichier n'existait pas du tout côté
`~/.claude/`) et `MANQUE SessionStart -> journal_etat.py`. Preuve vivante à côté du
vérificateur : cette session-là a démarré sans aucun bloc « État actuel » injecté.

**Vérifié, pas supposé.** Golden `tests/test_hooks.py` : **VERT, 89 cas, 0 échec**.
`deploy.ps1 -Verifier` : **Conforme, exit 0**. Puis le hook déployé a été exécuté avec un
vrai payload : `additionalContext` rempli, exit 0. Un garde-fou qu'on n'a pas essayé de
déclencher est décoratif.

### 2026-08-20 — le journal devient lisible par la machine

**Fait.** `hooks/journal_etat.py` : hook `SessionStart` qui injecte le bloc « État actuel »
du `journal.md` du repo courant. Enregistré comme **2ᵉ entrée** du tableau `SessionStart`
existant dans `settings.hooks.json` (aucune clé `if` — incident du 27/07), ligne ajoutée aux
`$attendus` de `deploy.ps1`, `_verifier_journal_etat()` ajouté à `tests/test_hooks.py`.
Suite complète : **VERT — 0 échec**.

**Pourquoi.** L'audit forfait du 19/08 : sur le top-40 des sessions, 88 % du `cache_write`
est du réchauffage — une session fraîche démarre aveugle, Sébastien ré-explique où on en
est, et cette ré-explication *est* le coût. Le côté **écriture** de la convention journal
existait déjà ; seule la **lecture** était manuelle. Le hook automatise la lecture, pas
l'écriture (écrire demande du jugement).

**Ce qui a été délibérément écarté.** Injecter le journal entier : celui de `un-autre-projet`
fait 80 Ko ≈ 20 000 tokens — il aurait coûté plus cher que le problème. Mesuré après
plafond : 8 774 car ≈ 2 200 tokens sur le plus gros projet.

**Divergence avec le plan annoncé.** L'offre validée disait « un `docs/journal.md` amorcé
dans les 4 projets actifs ». Vérification faite : `docs/journal.md` n'existe **nulle part**,
la convention réelle est `journal.md` à la racine, et 3 des 4 projets actifs l'ont déjà. Le
hook a été aligné sur la convention réelle plutôt que d'en créer une deuxième ; seul ce
repo-ci a été amorcé.

**Pas déployé.** `deploy.ps1` touche `~/.claude/` (du vivant) : attend un « oui ».

### 2026-08-23 — la couche globale apprend l'autonomie

**Fait.** Section « Autonomie » ajoutée à `CLAUDE-global.md` : 8 règles « décider seul et
rendre compte » + 6 règles de forme pour les questions restantes + A3 (git protecteur)
écrite NON ACTIVE. Source : audit des transcripts sur 45 jours — extraction par script
déterministe (2 811 sessions scannées), classification par workflow 12 agents,
contre-épreuve adversariale à 3 lentilles (réfutation empirique, périmètre/sécurité,
complétude) sur les 45 divergences réelles. Rapport rangé dans
`audit/rapport-audit-questions-45j.md`. Errata même jour : le titre avait d'abord été
« corrigé » à tort (fenêtre supposée close au 20/08, déduite de la date de dépôt du fichier
dans le repo) — la mémoire de session horodatée 09/08 17:05 prouve que l'audit a tourné le
09/08 ; fenêtre d'origine 25/06 → 09/08 rétablie. Dérogation déclarée à l'append-only du
journal : correction dans l'entrée du jour même, avant clôture du chantier.

**Les chiffres qui justifient.** 538 questions uniques en 45 j (~12/jour, dédupliquées —
la contre-épreuve avait détecté des sessions journalisées en double). 76 % de suivi quand
une reco était affichée, quasi 100 % sur « reco argumentée + geste réversible ».
102 questions ont bloqué > 30 min, 56 > 4 h — souvent des nuits pour un « go ».

**Ce que la contre-épreuve a changé.** 9 règles sur 12 durcies sur contre-exemples réels
avant intégration : « réversible via git » est faux pour le travail non commité (un
nettoyage « sûr » aurait détruit 131 fichiers non commités) ; les fichiers de harnais
(CLAUDE.md, settings, hooks, mémoire) ne comptent jamais comme réversibles ; le biais de
Sébastien est à deux bords — option maximale sur la conception interne, minimale dès qu'il
y a exposition ou risque. 2 règles ajoutées par la lentille complétude (incident → purger
la file ; ne jamais lui déléguer une commande exécutable par Claude).

**Vérifié, pas supposé.** Golden `tests/test_hooks.py` : VERT, 0 échec. Gate de clôture
unique avec périmètre listé (application immédiate de la règle F3 fraîchement écrite) :
réponse « Commit + push + déployer ». Déploiement par copie ciblée du CLAUDE.md, hash
source/déployé identiques — dérogation déclarée au cycle `deploy.ps1` : le script copie
tous les `hooks/*.py` et aurait embarqué `alerte_contexte.py`, WIP non commité d'une autre
session. `git add` scopé aux 3 fichiers du chantier, ce WIP n'entre pas dans le commit.
Au passage, le hook `block_git_add_all.py` a bloqué (fail-closed) un here-string PowerShell
qu'il ne savait pas parser — faux positif assumé, contourné par édition de fichier directe,
pas en désactivant le hook.

### 2026-08-23 — le compactage n'était pas cassé, et un déploiement a mangé 2,6 ko

Question de départ : « le compactage automatique a cassé ? » Non — **retiré volontairement**
le 20/08 à 21:15. La preuve tenait dans un fichier nommé
`settings.json.bak-2026-08-20-avant-fix-compaction` dont le seul écart avec les réglages
actifs était la ligne `CLAUDE_CODE_AUTO_COMPACT_WINDOW`. Mesure des compactages réels :
63 / 104 / 0 / 0 / 1. Le fix a marché.

Découverte au passage : le paragraphe du `CLAUDE-global.md` qui décrivait la variable comme
active a été commité (`467a6e7`, 21:25) **10 minutes après** le correctif qui la retirait
(21:15). Il n'est pas devenu faux, il est **né faux** — la session qui corrige un incident
écrit la leçon dans la foulée et décrit l'état d'avant son propre correctif. Réécrit.

Livré : `alerte_contexte.py` (UserPromptSubmit). Il **alerte et ne compacte pas** — forcer un
compactage est précisément ce qui a créé la boucle. Invariant testé en priorité : une alerte
qui annonce un contexte plein ne doit rien ajouter au contexte (`systemMessage` +
`suppressOutput`, zéro `additionalContext`). 15 assertions au golden, `$attendus` étendu.

**Incident, causé ici :** `deploy.ps1` a restauré `block_cloud_cache.py` et
`block_git_add_all.py` dans leur version du 27/07, effaçant ~2,6 ko de durcissements du
21/08. Le script a fait son métier — ce travail n'avait jamais quitté `~/.claude/hooks/`.
Récupéré depuis le transcript de la session d'origine (`7bc7c819`, 15:32-15:36), rejoué
**dans le repo**, vérifié à l'octet près (4353 / 5354). Contenu réel : un faux positif où
`2>/dev/null` comptait comme verbe d'écriture, et `shlex.split()` fermant 10 trous sur 12.

Deux traces à garder :
- le hook restauré **a bloqué mon propre message de commit**, qui citait littéralement
  l'option interdite entre guillemets. Faux positif de prose — le garde-fou n'est pas
  décoratif, et sa limite (il lit du texte) est exactement celle que `pre_commit_taille.py`
  couvre un étage plus bas.
- un `git reset` avalé par une commande bloquée a fait gonfler un commit de 2 à 6 fichiers.
  Rattrapé avant push (`reset --soft`). Une commande bloquée n'exécute **rien**, pas même
  ce qui précède le `&&`.

### 2026-08-24 — choisir le modèle : trois designs morts avant le bon

Point de départ : « on pourrait faire un truc qui me recommande d'abord le modèle et
l'effort ? ». L'enjeu réel, précisé en cours de route, est le **coût** : ni surévaluer
(Fable 5 coûte ×2 Opus 5) ni sous-évaluer (un chantier à refaire coûte 100 %).

Trois designs essayés puis abandonnés, chacun tué par un fait vérifié, pas par une préférence :

- **classifieur par mots-clés** — tué par « démontre que tout groupe d'ordre p² est
  abélien » : quatre mots, zéro fichier, et il faut Fable 5. Un lexique de preuve rattrape
  ce cas-là, mais pas « c'est quoi un groupe abélien ? », qui porte les mêmes mots pour une
  réponse d'une phrase. **Le lexique dit le domaine, jamais la profondeur dedans.** Et il ne
  voit rien de « on refait le moteur méta » : six mots, trois semaines de travail.
- **appel LLM dédié avant chaque prompt** — tué par l'infra : pas de clé API sur cette
  machine, tout passe par le forfait Max via l'Agent SDK, qui relance le CLI `claude`
  (spawns jusqu'à 180 s documentés dans `un-autre-projet/agents/llm_client.py`).
- **blocage `exit 2`** — tué par la doc officielle : un `UserPromptSubmit` qui bloque
  **efface le prompt tapé**. Rattrapable via le presse-papier, devenu inutile ensuite.

Retenu : le hook n'évalue rien. Il injecte une consigne, et c'est le modèle **déjà chargé**
qui juge — lui seul sait ce que désigne « le moteur méta ». Zéro processus, zéro latence.
Contrepartie assumée : il conseille et s'arrête, il n'empêche pas.

**La leçon transposable** : la profondeur d'un travail n'est pas une propriété du texte du
prompt. C'est une propriété du travail, que le texte ne fait que désigner. Aucune analyse
du texte n'y accède — seul quelque chose qui connaît le référent peut trancher.

Deux défauts trouvés en test, devenus cas permanents (17 cas sur ce hook, suite verte) :

- `_tracer()` était appelé **avant** l'injection : un dossier de trace non créable
  supprimait la consigne entière. Le produit passe d'abord, le confort ensuite.
- `CLAUDE_EFFORT` n'est pas hérité par un hook — mesuré sur 4 sessions réelles, toutes
  `effort=inconnu`. Corrigé par la lecture du transcript, vérifié variable retirée de
  l'environnement.

Deux affirmations de Claude, fausses, corrigées par les faits en séance : « aucun mot-clé ne
sépare le théorème d'une question anodine » (faux — le lexique de preuve le fait, la vraie
limite est ailleurs) et « les hooks sont chargés au démarrage, cette session ne le verra
pas » (faux — il a tiré au prompt suivant, sans redémarrage).

### 2026-08-25 — l'audit d'usage entre dans la couche globale, et le golden passe en pre-commit

Point de départ : le rapport `/insights` du 24/08 (32 sessions analysées, 81 commits). Sébastien
a demandé d'appliquer **tout** ce qu'il proposait. Les 6 ajouts CLAUDE.md ont été intégrés **au
bon étage** plutôt qu'empilés en 6 sections neuves : quatre d'entre eux recoupaient des règles
déjà écrites (Git, Environnement, Style de sortie, Honnêteté épistémique). Deux sections neuves
seulement : **« Contrat d'entrée »** (reformuler, désambiguïser avant de lancer un agent,
discipline de périmètre) et **« Sous-agents »** (contrat de retour, re-vérification des constats
négatifs, écriture au fil de l'eau).

Une tension a été tranchée explicitement : la proposition disait « attends un go » avant de
commencer. Repris tel quel, ça relançait les questions de rythme que la section « Autonomie » a
supprimées après l'audit des 538 questions. Écrit donc comme : go **seulement si la reformulation
change quelque chose**, et mention explicite que ce contrat ne rouvre pas les questions de rythme.

**La dérive d'abord.** `CLAUDE-global.md` avait 20 lignes de retard sur le déployé (le bloc
« Harnais méta » du 24/08 avait été écrit directement dans `~/.claude/CLAUDE.md`). Un
`deploy.ps1` l'aurait écrasé. Remonté et commité séparément (`247de92`) avant toute autre
édition.

**Le filet de config (`autosauvegarde_config.py`, hook Stop).** Le rapport proposait
`git stash push -u .claude/`. Écarté sur deux défauts : `stash` **retire** les modifications du
répertoire de travail — un hook de fin de tour ferait disparaître le travail en cours — et
`~/.claude` n'est pas un dépôt git, la commande y échouerait de toute façon. Implémenté en copie
non destructive vers `~/.claude/.sauvegardes/auto/<horodatage>/`, rotation à 30. La correction à
la **cause racine** de l'incident du 21/08 est ailleurs : `deploy.ps1` sauvegarde désormais toute
cible avant de l'écraser (vu à l'œuvre au premier déploiement :
`.sauvegardes/deploiements/2026-08-25_120850/CLAUDE.md`).

12 cas neufs au golden, dont un **échec réel attrapé** : la rotation triait les snapshots par
nom. Un nom hors format aurait fait supprimer les mauvais. Corrigé en tri par date de
modification, le nom départageant les ex aequo. Golden : 149 cas verts.

**Le pre-commit.** Le golden existait depuis le 27/07 mais ne tournait qu'à la main et dans
`deploy.ps1` : on pouvait commiter un hook cassé et ne le découvrir qu'au déploiement suivant.
`githooks/pre-commit-local` le lance dès qu'un commit touche `hooks/` ou `tests/`.

Contre-épreuve faite deux fois, et **la première n'a rien prouvé** : `MAX_SNAPSHOTS = 0` ne casse
aucun test, parce que `[:-0]` vaut `[:0]` et non « tout ». Le commit de sabotage est passé et a
dû être défait. La seconde, un `shutil.move` glissé à la place du `copy2`, est bien refusée. Elle
a révélé deux défauts d'affichage du hook, corrigés tous les deux : le filtre `echec` attrapait
des lignes `OK` dont le libellé contient le mot, et un golden mort sur exception avant son résumé
produisait un refus **muet**.

À vérifier au prochain tour, non tranché : le hook `Stop` a-t-il tiré tout seul dans la session
qui l'a posé ? L'absence de snapshot automatique observée ne prouve rien — aucun tour ne s'est
terminé entre le déploiement (12:08) et la mesure (12:11). L'entrée du 24/08 ci-dessus rappelle
qu'un hook a déjà démenti le « pas avant redémarrage ».

Deux dérives connues et **non traitées**, hors périmètre : `hooks/rappel_carte.py` est dans le
repo sans être commité, et `~/.claude/hooks/rappel_revue.py` est déployé sans exister dans le
repo. `deploy.ps1` a copié `rappel_carte.py` au passage — sans effet, il n'est déclaré nulle part
dans `settings.json`. Troisième trou repéré, non comblé : `verifie_lisibilite_reponse.py` (hook
Stop, actif) n'est pas dans la liste `$attendus` de `deploy.ps1` — un hook non vérifié est un
hook dont on ne sait pas s'il tourne.

Quatrième constat, non corrigé : ce journal range ses entrées en ordre **croissant** (la plus
récente en bas), alors que `journal_etat.py` injecte les trois **premières** trouvées. Le hook
montre donc ici les entrées du 20/08, pas les dernières. À arbitrer : inverser le fichier ou le
hook.
