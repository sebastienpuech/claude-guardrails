# ce depot — configuration Claude Code globale

Config de niveau **utilisateur** (toutes sessions, tous repos), versionnée ici. Source de vérité :
ce repo ; copie déployée : `~/.claude/` sur chaque machine.

## Contenu

- `CLAUDE-global.md` — **source de vérité** du CLAUDE.md global. Nommé sans le nom canonique
  pour ne pas être auto-chargé comme mémoire de sous-dossier quand on travaille dans ce repo.
- `hooks/block_cloud_cache.py` — hook PreToolUse : bloque toute écriture dans
  `local-agent-mode-sessions` (cache cloud volatile, toute édition y est perdue).
- `hooks/block_git_add_all.py` — hook PreToolUse : refuse tout `git add` non scopé au chantier
  (incident : 4 545 lignes de suppression avalées par le commit d'une autre session).
- `hooks/autosauvegarde_config.py` — hook Stop : filet **non destructif** sur la config. À chaque
  fin de tour, tout fichier de `~/.claude` (CLAUDE.md, `settings*.json`, `hooks/*.py`) dont le
  contenu a changé est **copié** dans `~/.claude/.sauvegardes/auto/<horodatage>/` (rotation à 30).
  Incident du 21/08/2026 : un déploiement a écrasé deux hooks non commités, reconstitués à la main
  dans les transcripts. Il copie, il ne déplace jamais — un `git stash` viderait le plan de travail.
- `tests/test_hooks.py` — golden des hooks : contournement des deux bloquants, comportement des
  autres. 149 cas, `exit 0` = vert.
- `deploy.ps1` — déploie et vérifie la conformité. Refuse de déployer si le golden est rouge.
  **Sauvegarde toute cible avant de l'écraser** dans `~/.claude/.sauvegardes/deploiements/<horodatage>/` :
  c'est la correction à la cause racine de l'incident du 21/08/2026.
- `settings.hooks.json` — le fragment de référence à fusionner dans `settings.json`.

## Déploiement sur une machine

```powershell
powershell -ExecutionPolicy Bypass -File deploy.ps1            # déployer
powershell -ExecutionPolicy Bypass -File deploy.ps1 -Verifier  # constater une dérive, n'écrit rien
```

`deploy.ps1` fait les étapes 1-2 ci-dessous, vérifie l'étape 3 sans jamais réécrire
`settings.json` (c'est de la config utilisateur : modèle, plugins, thème), et refuse de
déployer un hook dont le golden est rouge. Il vérifie aussi qu'aucune **clé non documentée**
ne traîne dans une entrée de hook — c'est ce qui aurait attrapé l'incident du `if` (cf. Pièges).

Les étapes manuelles restent documentées pour une machine sans PowerShell :

1. Copier `CLAUDE-global.md` → `~/.claude/CLAUDE.md`.
2. Copier `hooks/*.py` → `~/.claude/hooks/`.
3. Fusionner dans `~/.claude/settings.json` (ne pas écraser l'existant) :

```json
{
  "permissions": {
    "ask": ["Bash(git commit:*)"]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python \"<HOME>/.claude/hooks/block_cloud_cache.py\"",
            "timeout": 15
          }
        ]
      },
      {
        "matcher": "Bash|PowerShell",
        "hooks": [
          {
            "type": "command",
            "command": "python \"<HOME>/.claude/hooks/block_git_add_all.py\"",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```

4. Prouver que les garde-fous tirent (un garde-fou non testé est décoratif) : tenter un
   `git add -A` dans un repo jetable et une écriture sous `local-agent-mode-sessions` —
   les deux doivent être BLOQUÉS. Le `git add -A` se tente **via chaque outil couvert par
   le matcher** (Bash *et* PowerShell) : un blocage obtenu sur l'un ne dit rien de l'autre,
   et c'est comme ça qu'un hook à moitié mort est passé inaperçu (cf. Pièges). Vérifier
   aussi qu'un cas légitime PASSE — `git add <fichier>` — sinon on a prouvé un blocage
   aveugle, pas un garde-fou.

## Durcissement du 2026-07-27 (test de contournement)

« Un garde-fou qu'on n'a pas essayé de contourner est décoratif. » Les deux hooks ont été
attaqués : **5 trous sur 13 cas**. Chacun est devenu un cas permanent de `tests/test_hooks.py`.

| Contournement | avant | après |
|---|---|---|
| `git add --al` — git accepte tout préfixe non ambigu (vérifié en live : stage tout le repo) | passait | bloqué |
| `git add -u` — stage toutes les suppressions suivies = **l'incident d'origine** | passait | bloqué |
| `git add *` — glob expansé par le shell | passait | bloqué |
| `git add :/` — pathspec racine, depuis n'importe quel sous-dossier | passait | bloqué |
| Écriture dans le cache via `cp` / `Copy-Item` / `>` (matcher `Edit\|Write` seul) | passait | bloqué |
| Entrée JSON illisible | fail-**open** | fail-**closed** (`exit 2`) |

Un faux positif corrigé dans la foulée : un message de commit qui *documente* l'incident était
lu comme une commande. Le contenu d'un `-m` / `-F` est du texte, il est retiré avant analyse.

`git commit -a` n'est pas traité par les hooks : il est tenu par la permission `ask` sur
`Bash(git commit:*)`. Une règle vit à un seul étage.

## Rituel trimestriel (règle de maintenance)

1. Relire `CLAUDE-global.md` règle par règle : Claude l'a-t-il violée ce trimestre ?
   Sinon, candidate à la coupe (une règle morte est du bruit qui dilue les vivantes).
2. Vérifier que la copie déployée (`~/.claude/CLAUDE.md`) et la source ici sont identiques.
3. Toute modification : éditer ICI, commit, puis redéployer sur chaque machine.

## Pièges appris à la dure

- **Chemins longs Windows** : un clone git dans un dossier à préfixe profond peut échouer
  silencieusement au checkout (« Filename too long ») et produire un index incomplet — un
  commit depuis cet état **supprime** les fichiers manquants. Toujours `git config
  core.longpaths true`, cloner dans un chemin court, et vérifier `git status --porcelain`
  avant tout commit. Incident : 299 fichiers supprimés de un-projet le 2026-07-27,
  restaurés par commit correctif en plumbing (`read-tree` + `commit-tree`).

- **Clé inconnue dans un hook : pas d'erreur, désactivation silencieuse.** Le bloc settings
  portait une clé `"if": "Bash(git *)"` sur le hook `block_git_add_all.py`. Elle est lue
  comme une règle de permission, donc elle exige l'outil *Bash* : sur un appel de l'outil
  *PowerShell* la condition ne matche jamais et le hook est sauté sans le moindre message.
  Résultat : `git add -A` passait via PowerShell — le shell principal sous Windows — pendant
  que le même hook bloquait correctement via Bash. Aucun symptôme visible, JSON valide,
  garde-fou à moitié mort. Diagnostiqué le 2026-07-27 avec un hook temporaire `matcher: "*"`
  qui journalise `tool_name` ; corrigé par retrait de `if` et matcher `Bash|PowerShell`.

  Deux règles qui en découlent. Ne mettre dans un hook que des clés documentées : le tri
  fin appartient au script, qui lui échoue bruyamment. Et prouver le blocage sur **chaque**
  outil couvert par le matcher, pas sur un seul — un `exit 2` obtenu via Bash ne dit rien
  de PowerShell. Une preuve partielle est ce qui rend un garde-fou décoratif sans qu'on le
  sache. *Depuis le 27/07, `deploy.ps1` refuse toute clé non documentée dans une entrée de hook.*

- **Encodage Windows : deux fois la même racine, deux symptômes sans rapport apparent** (27/07).
  Un `.ps1` écrit en UTF-8 est lu en CP1252 par Windows PowerShell 5.1 : un em dash (`E2 80 94`)
  devient `â€"` dont l'octet `0x94` est un guillemet typographique fermant, que le parser traite
  comme **délimiteur de chaîne**. Erreur incompréhensible, pointant une ligne sans rapport.
  Symétriquement, la sortie d'un script Python lue par un appelant en UTF-8 lève
  `UnicodeDecodeError` parce que la console encode en CP1252.

  Règle : **le texte destiné à une machine sort en UTF-8 forcé**
  (`sys.stdout.reconfigure(encoding="utf-8")`) ; **le code destiné à PowerShell 5.1 s'écrit
  en ASCII strict**. Les accents dans un commentaire PowerShell sont sans danger — seuls les
  caractères qui se décodent en guillemet cassent le parsing.

- **Deux sources de vérité créées le même jour** (27/07). Ce repo a été créé à 14h56 ; une
  session ouverte ailleurs a reconstruit la même chose à 17h dans `un-projet/claude-global/`,
  sans le voir. Les deux étaient poussées. Consolidé ici, `claude-global/` supprimé.
  Règle : avant de créer un foyer pour quelque chose de transverse, `gh repo list` — la liste
  des dépôts est la seule vue exhaustive, un `find` local ne voit pas ce qui n'est pas cloné.
