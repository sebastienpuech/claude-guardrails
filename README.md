# ce depot — configuration Claude Code globale

Config de niveau **utilisateur** (toutes sessions, tous repos), versionnée ici. Source de vérité :
ce repo ; copie déployée : `~/.claude/` sur chaque machine.

## Contenu

- `CLAUDE-global.md` — **source de vérité** du CLAUDE.md global. Nommé sans le nom canonique
  pour ne pas être auto-chargé comme mémoire de sous-dossier quand on travaille dans ce repo.
- `hooks/block_cloud_cache.py` — hook PreToolUse : bloque toute écriture dans
  `local-agent-mode-sessions` (cache cloud volatile, toute édition y est perdue).
- `hooks/block_git_add_all.py` — hook PreToolUse : bloque `git add -A` / `--all` / `.`
  (incident : 4 545 lignes de suppression avalées par le commit d'une autre session).

## Déploiement sur une machine

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
  sache.
