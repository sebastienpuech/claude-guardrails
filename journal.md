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

- **Couche globale déployée et conforme.** Source de vérité = ce repo. Cycle inchangé :
  éditer ici → `python tests/test_hooks.py` (VERT obligatoire) → `.\deploy.ps1`.
  `deploy.ps1` n'écrit **jamais** `settings.json`, il vérifie contre la liste `$attendus`
  (exit 0 = conforme, exit 2 = dérive). Ne jamais éditer `~/.claude/` comme une source.

- **Hooks en place (6).** `block_git_add_all.py` et `block_cloud_cache.py` sont
  *fail-closed* (ils gardent). `inject_lecons.py`, `rappel_lecon.py`,
  `checkpoint_precompact.py` et `journal_etat.py` sont *fail-open* — dérogation déclarée au
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

- **En attente d'arbitrage** (rien n'est fait sans « oui ») : baisser
  `CLAUDE_CODE_AUTO_COMPACT_WINDOW` de 120000 à 100000 dans `settings.json` (sauvegarde
  `settings.json.bak-2026-08-19` en place) ; ajouter à `CLAUDE-global.md` les deux règles
  « `/compact` avant la pause » et « ce qui compte s'écrit dans un fichier, pas dans le
  contexte » ; ouvrir `~/.claude/checkpoints/ECHEC.log` (242 o, 19/08 19:10), jamais lu.

- **Re-mesure prévue vers le 2026-09-02** : `python audit/audit_usage.py 14`, pour voir si
  le checkpoint + le journal ont fait baisser la part de réchauffage (88 % du `cache_write`
  des grosses sessions au 19/08, ≈ 24 % de la facture 60 jours).

## Log (append-only)

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
