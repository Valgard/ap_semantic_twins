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
./scripts/install.sh --check  # report content drift, broken or misdirected symlinks,
                               # missing destinations, unexpected files under the deployed
                               # scripts/ or at the top level, and a symlink/copy mode mismatch
```

The skill symlink points at `skills/semantic-twins/`, the agent symlink at
`agents/semantic-twin-hunter.md`. After a symlink install, add `/agents/semantic-twin-hunter.md`
to `~/.claude/.gitignore` — `~/.claude/agents/` is tracked, and this symlink is machine-specific.

Restart Claude Code afterwards — skills and agents are discovered at session start.

Installed as a plugin instead, the agent is registered as
`semantic-twins:semantic-twin-hunter`, while `SKILL.md`'s description names it by its bare
name. Whether that still reaches the agent has not been tested; use `install.sh` until it has.

## Layout

| Path | Purpose |
| --- | --- |
| `.claude-plugin/plugin.json` | Plugin manifest |
| `skills/semantic-twins/SKILL.md` | The audit orchestrator |
| `skills/semantic-twins/references/taxonomy.md` | Four verification outcomes plus one pre-verification exclusion, and what a finding may claim |
| `skills/semantic-twins/references/examples/notes.txt` | Structural fixture exercising `install.sh --check`'s recursive directory diff, not taxonomy content |
| `skills/semantic-twins/scripts/inventory.py` | Stage 1: deterministic file inventory and chunking plan |
| `agents/semantic-twin-hunter.md` | Diff-scoped agent, `pr-review-toolkit` shape |
| `scripts/install.sh` | Deployment into `~/.claude` |
| `tests/fixtures/twin-corpus/` | Acceptance corpus, one planted case per outcome |
| `tests/ACCEPTANCE.md` | Expected verdicts for that corpus |
| `tests/test_acceptance_anchors.py` | Pins the `path:line` anchors in `ACCEPTANCE.md`'s expectations table to a real definition |
| `tests/test_acceptance_coverage.py` | Pins `ACCEPTANCE.md`'s Coverage numbers against a real inventory run, and its quoted headings and consolidation figure against their sources |
| `tests/test_inventory_*.py` | Unit and corpus tests for `skills/semantic-twins/scripts/inventory.py` |
| `tests/test_install.py` | Subprocess-driven tests for `scripts/install.sh` |
| `tests/conftest.py` | Shared pytest fixtures |
| `pytest.ini` | pytest configuration |
| `pyproject.toml` / `uv.lock` | Dev tooling: pytest, ruff, vulture |
| `docs/specs/` | The design this implements |

## Development

```bash
uv run pytest
uv run ruff format . && uv run ruff check --fix .
uv run vulture skills/semantic-twins/scripts tests --min-confidence 80
```

## Known limits

Stage 2 is the recall bottleneck: a purpose sentence that describes construction instead
of effect sinks a pair invisibly — it appears nowhere as "checked and rejected". The tool
makes no completeness claim, and it does not satisfy the hook-enforced PR review gate.
