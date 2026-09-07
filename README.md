# semantic-twins

Finds semantic twins — type-4 clones — in a project: code that does the same thing while
looking nothing alike. Token- and AST-based detectors (jscpd, PMD CPD, SonarQube) cover
types 1 to 3 and are structurally blind to this one.

Two entry points, one method:

- **`/semantic-twins <path>`** audits a whole project in five stages.
- **`semantic-twin-hunter`** is an agent for the diff-scoped question: does what this
  change adds already exist here? Same method, smaller left-hand side, no index needed.

## Install

```bash
./scripts/install.sh          # symlink by default, --mode copy for a copy
./scripts/install.sh --check  # report drift in copy mode
```

After a symlink install, add `/agents/semantic-twin-hunter.md` to `~/.claude/.gitignore` —
`~/.claude/agents/` is tracked, and this symlink is machine-specific.

Restart Claude Code afterwards — skills and agents are discovered at session start.

## Layout

| Path | Purpose |
| --- | --- |
| `SKILL.md` | The audit orchestrator |
| `agents/semantic-twin-hunter.md` | Diff-scoped agent, `pr-review-toolkit` shape |
| `references/taxonomy.md` | The five verification outcomes and what a finding may claim |
| `scripts/inventory.py` | Stage 1: deterministic file inventory and chunking plan |
| `scripts/install.sh` | Deployment into `~/.claude` |
| `tests/fixtures/twin-corpus/` | Acceptance corpus, one planted case per outcome |
| `tests/ACCEPTANCE.md` | Expected verdicts for that corpus |
| `docs/specs/` | The design this implements |

## Development

```bash
uv run pytest
uv run ruff format . && uv run ruff check --fix .
uv run vulture scripts tests --min-confidence 80
```

## Known limits

Stage 2 is the recall bottleneck: a purpose sentence that describes construction instead
of effect sinks a pair invisibly — it appears nowhere as "checked and rejected". The tool
makes no completeness claim, and it does not satisfy the hook-enforced PR review gate.
