# claude-guardrails

[![verifications](https://github.com/sebastienpuech/claude-guardrails/actions/workflows/verifications.yml/badge.svg)](https://github.com/sebastienpuech/claude-guardrails/actions/workflows/verifications.yml)

*(English version: [README.md](README.md))*

Des garde-fous pour un agent de code, chacun né d'un incident réellement survenu, et chacun
couvert par un test qui essaie de le mettre en défaut.

Empêcher un agent de lancer `git add -A` est facile. Ce qui l'est moins, et qui est le vrai sujet
de ce dépôt : prouver que le blocage se déclenche encore quand l'entrée est illisible, tenir le
compte écrit des dix-sept façons dont il a été contourné, et reconnaître publiquement que trois
d'entre elles ne peuvent pas être fermées.

## Ce qui est peu courant

**Les garde-fous ont été attaqués exprès, et les échecs sont publiés.** Une passe de red team a
trouvé 17 contournements. 14 ont été fermés. Les 3 restants sont documentés comme non colmatables
plutôt que discrètement oubliés : `git revert`, `cherry-pick` et `rebase` ne déclenchent aucun
hook « pre- », donc le dépôt cesse de prétendre les bloquer et lève une alerte visible après coup.
Un garde-fou que personne n'a essayé de contourner est décoratif.

**Le fail-closed est prouvé, pas affirmé.** `tests/test_hooks.py` envoie du JSON volontairement
cassé aux deux hooks bloquants et exige le code de sortie 2. La question qu'il faut poser à tout
garde-fou — disparaît-il en silence quand il plante ? — reçoit ici une réponse par un test et non
par une affirmation. Les hooks informatifs, eux, échouent *ouvert* par conception, et cette
asymétrie est testée aussi.

**Chaque hook porte sa cicatrice, datée.** Les docstrings ne disent pas ce que fait le hook :
elles disent ce qui a mal tourné. `block_git_add_all.py` existe parce que le commit d'une session
a avalé 4 545 lignes de suppression. `autosauvegarde_config.py` existe parce qu'un déploiement a
écrasé deux hooks non commités le 21/08/2026, récupérés à la main dans les transcripts.
`alerte_parc.py` existe parce qu'un moniteur a calculé des anomalies chaque matin pendant 13 jours
sans le dire à personne : sa seule sortie exigeait un jeton jamais configuré. Un veilleur muet est
pire qu'aucun veilleur, parce que tout a l'air calme.

## Ce qui est réellement vérifié

185 cas de test répartis en deux suites, relancées le 28/08/2026. Python 3.10+, aucune dépendance.

```bash
python tests/test_hooks.py           # 175 cas — hooks, fail-closed, traitement des chemins
python tests/test_garde_fous_git.py  #  10 cas — garde-fous git, tentatives de contournement
```

Les deux sortent en 0. Sur un clone neuf, vous verrez 175 cas s'exécuter et la seconde suite
afficher `IGNORE` : elle teste l'installation *réelle* — les shims dans `~/.claude/githooks/`
plus `core.hooksPath` — et non une copie isolée, donc elle n'a rien à tester tant que rien n'est
déployé. Une installation à moitié faite échoue toujours franchement ; seule une machine où rien
n'est installé est ignorée. C'est aussi pourquoi le badge d'intégration continue ci-dessus
couvre 175 cas et non 185.

## Ce que ça ne fait pas

- **Les chemins des hooks sont des marqueurs.** `settings.hooks.json` porte
  `<HOME>/.claude/hooks/…`, à remplacer par votre propre chemin. Claude Code n'expose aucun
  placeholder de chemin pour les hooks de niveau utilisateur (vérifié en documentation le
  28/08/2026) ; la réponse portable est de packager les hooks en plugin et d'utiliser
  `${CLAUDE_PLUGIN_ROOT}`. Cette conversion est le jalon suivant, et tant qu'elle n'est pas faite
  ce dépôt est une référence à lire et à adapter, pas une installation clés en main.
- **`pytest` ne collecte rien ici.** Les suites sont des runners écrits à la main, avec leur
  propre affichage, à lancer directement comme ci-dessus. Lancer `pytest` dans ce dossier annonce
  zéro test, ce qui ressemble à un dépôt vide et ne l'est pas.
- **L'intégration continue ne couvre que la moitié portable.** La suite de 175 cas tourne à
  chaque push, sur Python 3.10 et 3.12. Les garde-fous git ne peuvent pas y être couverts : ils
  testent un déploiement réel, et déployer signifie modifier la configuration git globale de la
  machine qui exécute.
- **Le dépôt ne mesure pas son propre effet.** Nulle part il ne montre « depuis ces hooks, zéro
  incident de type X en N jours ». Les incidents qui ont motivé chaque hook sont datés ; l'absence
  de leur récurrence ne l'est pas. C'est le chiffre qui manque, et c'est celui qui trancherait la
  question de la sur-ingénierie dans un sens ou dans l'autre.
- **`deploy.ps1` est du PowerShell**, donc pensé pour Windows. Sur macOS ou Linux il exige
  `pwsh`, et il n'y a jamais été lancé. Les hooks eux-mêmes sont du Python portable ; le script
  de déploiement, non.
- **L'installer touche tous les dépôts git de la machine.** Les shims de `githooks/` ne se
  déclenchent qu'une fois `core.hooksPath` posé en global, et ce réglage est global par nature :
  à partir de là, les shims pre-commit et post-commit tournent dans **tous** les dépôts où vous
  committez, pas seulement celui-ci. `deploy.ps1` ne le pose pas à votre place — il lit la valeur
  courante et **affiche** la commande, à vous de la lancer. C'est délibéré, et c'est bon à savoir
  avant de coller cette commande.
- **Deux hooks sont câblés de travers, et le journal le dit.** `rappel_carte.py` est livré dans
  `hooks/` mais n'est déclaré nulle part, donc il ne tourne jamais. `alerte_parc.py` est vérifié
  par `deploy.ps1` mais absent du fragment `settings.hooks.json`, donc quiconque fusionne ce
  fragment tel quel verra le script lui-même signaler un écart. Les deux sont connus et
  consignés dans `journal.md` plutôt que nettoyés en douce avant publication.
- **C'est la configuration d'une seule personne.** Comptez vous-même avec
  `git ls-files | xargs wc -l` : quelques milliers de lignes pour un seul utilisateur. Est-ce
  proportionné aux incidents consignés dans `journal.md`, ou est-ce un harnais qui s'auto-alimente ?
  Le dépôt ne tranche pas.

## Ce dépôt est un extrait

Trois fichiers restent privés et ne sont pas publiés ici : le `CLAUDE.md` global de l'auteur, un
script de surveillance de machine, et un audit de consommation. Deux conséquences se voient de
l'intérieur.

Les docstrings des hooks citent `doctrine.md` quand elles expliquent *pourquoi* une règle existe
(« le fail-closed est le principe 1 »). Ce fichier n'est pas dans ce dépôt. Ce sont des notes de
provenance, pas des dépendances : rien n'en a besoin pour lire, faire tourner ou modifier le code,
et les deux suites de tests tournent sur un clone nu.

`deploy.ps1` déploie le `CLAUDE.md` global à l'étape 2. En l'absence du fichier, il signale le
manque et poursuit au lieu de planter, donc les étapes suivantes s'exécutent quand même.

## Organisation

| Chemin | Ce que c'est |
|---|---|
| `hooks/` | Les hooks. Les bloquants sortent en 2 ; les informatifs ne bloquent jamais. |
| `githooks/` | Les hooks côté git : pre-commit, post-commit, pre-merge-commit. |
| `tests/` | Les deux suites, tentatives de contournement comprises. |
| `settings.hooks.json` | Le câblage, avec des chemins à substituer. |
| `deploy.ps1` | Le déploiement vers `~/.claude/`. Sauvegarde avant d'écraser, parce qu'une fois il ne l'a pas fait. |
| `journal.md` | Le log daté : ce qui a cassé, ce qui a été changé, ce qui a été rejeté. |

## Licence

MIT. Voir [LICENSE](LICENSE).
