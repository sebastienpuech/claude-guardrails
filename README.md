# claude-guardrails

[![verifications](https://github.com/sebastienpuech/claude-guardrails/actions/workflows/verifications.yml/badge.svg)](https://github.com/sebastienpuech/claude-guardrails/actions/workflows/verifications.yml)

*(Version française : [README.fr.md](README.fr.md))*

Guardrails for a coding agent, each one born from an incident that actually happened, and each
one covered by a test that tries to defeat it.

Blocking an agent from running `git add -A` is easy. What is harder, and what this repository
is actually about: proving the block still fires when the input is malformed, keeping a written
record of the seventeen ways it was bypassed, and admitting in public which three of them cannot
be closed at all.

## The part that is unusual

**The guardrails were attacked on purpose, and the failures are published.** One red-team pass
found 17 bypasses. 14 were closed. The remaining 3 are documented as unclosable rather than
quietly dropped: `git revert`, `cherry-pick` and `rebase` fire no `pre-` hook at all, so the
repository stops pretending to block them and raises a visible alert afterwards instead. A
guardrail nobody has tried to defeat is decoration.

**Fail-closed is proven, not asserted.** `tests/test_hooks.py` feeds deliberately broken JSON to
both blocking hooks and requires exit code 2. The question worth asking of any guardrail — does
it disappear silently when it crashes? — is answered here by a test rather than by a claim.
Informational hooks fail *open* by design, and that asymmetry is tested too.

**Every hook carries its scar, dated.** The docstrings do not say what the hook does; they say
what went wrong. `block_git_add_all.py` exists because one session's commit swallowed 4,545 lines
of deletions. `autosauvegarde_config.py` exists because a deployment overwrote two uncommitted
hooks on 2026-08-21, recovered by hand from transcripts. `alerte_parc.py` exists because a
monitor computed anomalies every morning for 13 days and told nobody: its only output channel
needed a token that had never been configured. A silent watchman is worse than no watchman,
because everything looks calm.

## What is actually verified

185 test cases across two suites, re-run on 2026-08-28. Python 3.10+, no dependencies.

```bash
python tests/test_hooks.py           # 175 cases — hooks, fail-closed, path handling
python tests/test_garde_fous_git.py  #  10 cases — git guardrails, bypass attempts
```

Both exit 0. On a fresh clone you will see 175 cases run and the second suite report
`IGNORE`: it exercises the *real* installation — shims in `~/.claude/githooks/` plus
`core.hooksPath` — rather than an isolated copy, so it has nothing to test until you deploy. A
half-installed setup still fails loudly; only a machine with nothing installed at all is skipped.
That is also why the CI badge above covers 175 cases, not 185.

## What this does not do

- **The hook paths are placeholders.** `settings.hooks.json` ships `<HOME>/.claude/hooks/…`,
  which you must replace with your own path. Claude Code exposes no path placeholder for
  user-level hooks (checked against the documentation on 2026-08-28); the portable answer is to
  package hooks as a plugin and use `${CLAUDE_PLUGIN_ROOT}`. That conversion is the next
  milestone, and until it lands this repository is a reference to read and adapt rather than a
  drop-in install.
- **`pytest` collects nothing here.** The suites are hand-written runners with their own
  reporting, invoked directly as shown above. Running `pytest` in this directory reports zero
  tests, which looks like an empty repository and is not.
- **CI covers the portable half only.** The 175-case suite runs on every push, on Python 3.10 and
  3.12. The git guardrails cannot be covered there: they test a real deployment, and deploying
  means changing the runner's global git configuration.
- **It does not measure its own effect.** Nowhere does this repository show "since these hooks,
  zero incidents of type X in N days". The incidents that motivated each hook are dated; the
  absence of their recurrence is not. That is the missing number, and it is the one that would
  settle the over-engineering question either way.
- **`deploy.ps1` is PowerShell**, so it is Windows-first. On macOS or Linux it needs `pwsh`, and
  it has never been run there. The hooks themselves are plain Python and portable; the deployment
  script is not.
- **Setting this up touches every git repository on your machine.** The `githooks/` shims only
  fire once `core.hooksPath` is set globally, and that setting is global by nature: from then on,
  the pre-commit and post-commit shims run in every repository you commit to, not only this one.
  `deploy.ps1` does not set it for you — it reads the current value and prints the command for
  you to run yourself. Deliberate, and worth knowing before you paste that command.
- **Two hooks are wired inconsistently, and the journal says so.** `rappel_carte.py` ships in
  `hooks/` but is declared nowhere, so it never runs. `alerte_parc.py` is checked by `deploy.ps1`
  but missing from the `settings.hooks.json` fragment, so anyone merging that fragment as-is will
  see a drift warning from the script itself. Both are known and recorded in `journal.md` rather
  than quietly cleaned up before publishing.
- **It is one person's configuration.** Count it yourself with
  `git ls-files | xargs wc -l`; it is a few thousand lines for a single user. Whether that is
  proportionate to the incidents documented in `journal.md`, or a harness feeding itself, the
  repository does not answer.

## This repository is an extract

Three files stay private and are not published here: the author's global `CLAUDE.md`, a
machine-monitoring script, and a usage audit. Two consequences are visible from the inside.

Hook docstrings cite `doctrine.md` when they explain *why* a rule exists ("fail-closed is
principle 1"). That file is not in this repository. The citations are provenance notes, not
dependencies: nothing needs them to read, run or modify the code, and both test suites run on a
bare clone.

`deploy.ps1` deploys the global `CLAUDE.md` at step 2. With the file absent it reports the gap
and continues rather than crashing, so the remaining steps still run.

## Layout

| Path | What it is |
|---|---|
| `hooks/` | The hooks themselves. Blocking ones exit 2; informational ones never block. |
| `githooks/` | Git-side hooks: pre-commit, post-commit, pre-merge-commit. |
| `tests/` | The two suites, including the bypass attempts. |
| `settings.hooks.json` | The wiring, with placeholder paths. |
| `deploy.ps1` | Deployment to `~/.claude/`. Backs up before overwriting, because it once did not. |
| `journal.md` | The dated log: what broke, what was changed, what was rejected. |

## License

MIT. See [LICENSE](LICENSE).
