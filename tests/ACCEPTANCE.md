# Acceptance corpus

`tests/fixtures/twin-corpus/` carries one planted case per taxonomy outcome. Running the
skill against it must produce exactly these verdicts. Anything else is a regression.

The report must also place the `## Defects: divergent twins` section before `## Debt:
stable twins` — this is a ranking rule (`references/taxonomy.md`'s `DIVERGENT` before
`STABLE`), not incidental ordering, and a report that reverses it fails even if every
individual verdict below is correct.

| Pair | Expected outcome | Why |
| --- | --- | --- |
| `pricing/checkout.py:1` ↔ `pricing/invoice.py:1` | `DIVERGENT` | Same purpose, two behavioural differences: side B lacks the negative-rate guard and truncates where side A rounds half-up. The report must name at least these two differences and identify side A as the corrected one — naming a third is not a failure. |
| `slug/article.py:4` ↔ `slug/category.py:1` | `STABLE` | The two share a purpose and an output — both turn a name into a URL-safe key — while sharing no control flow and no mechanism: one is a regex substitution, the other a character-by-character loop. This is the corpus's type-4 case, the only reason this tool exists rather than a token- or AST-based clone detector. A run that misses it has failed at the thing the tool exists for. The report must also state `Consolidation: ~4 lines` — `slugify` spans 4 lines (4-7), `to_url_key` spans 12 (1-12), and consolidation is the sum minus the larger side. |
| `ordering/CustomerDto.php:7` ↔ `shipping/CustomerDto.php:9` | `JUSTIFIED` | Identical mapping across two bounded contexts, with the decoupling stated in a comment. Named, not counted as a finding. |
| `validation/email.py:1` ↔ `validation/postcode.py:1` | not reported as a twin | Both functions are named `validate`, take one argument and raise on rejection, so a stage 2 that drifted toward describing shape rather than effect would cluster them; a rule-following stage 2 will not. The run fails only if the pair is reported as a twin of any kind (`DIVERGENT`, `STABLE` or `JUSTIFIED`). Whether it was clustered and then refuted (`NOT_A_TWIN`, which appears only as a count) or never clustered at all is not something the report can distinguish, and is not graded. |
| `generated/Mapper.g.cs:10` ↔ `slug/category.py:1` | never reported | The generated file must not reach stage 2 at all. |

## How to run it

1. `python3 "$(pwd)/scripts/inventory.py" tests/fixtures/twin-corpus`, run from the
   repository root so `$(pwd)` is the skill base directory — the invocation form `SKILL.md`
   mandates for stage 1: plain `python3` (no `uv run`) against an absolute path to the
   script, never a path relative to the target repo. `uv run` stays reserved for this repo's
   own dev-time tooling (pytest, ruff, vulture — see README.md); using it here instead would
   exercise a different code path than the one that ships.
   → `generated/Mapper.g.cs` must not appear in `files`, and `excluded.generated` must be
   `1`. To check it by name instead of by count, `excluded_paths.generated` now lists the
   path.
2. Invoke the `semantic-twins` skill against `tests/fixtures/twin-corpus`.
3. Compare the report against the table above and the `## Coverage` expectations below.

## Coverage

`SKILL.md`'s report ends in a `## Coverage` block. Grading a run means checking it too, not
just the verdict table above — a run that gets every verdict right but omits or
misreports this block is still non-conformant. Expected values for this corpus:

- `Corpus: all source files` — `--include-tests` was not passed, and the corpus has no
  test-shaped file to skip anyway.
- `Examined:` `8` files — deterministic from step 1's inventory run (`totals.files`). Units
  and candidate groups are stage 2/3 output and not pinned to a single number: candidate
  groups before the cap is `3` if the near-miss pair (`validation/`) is never clustered, or
  `4` if it is — in which case that fourth group must resolve to `NOT_A_TWIN` in the
  `Refuted in verification` line below, per the near-miss row above.
- `Chunks:` `8` dispatched — one chunk per file (`totals.chunks` is also `8`; none of the
  eight files exceeds 800 lines). Every file in this corpus defines a named unit, so a
  healthy run reports `0` for both `returned nothing` and `unparseable lines`.
- `Empty chunks (still empty after re-dispatch): none` — follows from `returned nothing`
  being `0` above; there is nothing to name.
- `Partitioned: no` — 8 units is nowhere near the 20,000-unit partitioning threshold.
- `Excluded:` `1` generated, `0` by path rule, `0` unsupported extension, `0` untracked, `0`
  missing, `0` undecodable, `0` permission denied — from the same inventory run as step 1.
- `Unsupported extensions: none`, `Missing files: none`, `Undecodable files: none`,
  `Permission denied files: none`.
- `Generated files: generated/Mapper.g.cs`.
- `Untracked files: none`.
- `Refuted in verification (NOT_A_TWIN):` `1` group if the near-miss pair clustered, `0` if
  it never did.
- `Verification returned nothing: 0` — nothing in this corpus should cause a stage 4
  dispatch to come back empty.
- `Dropped at the cluster cap: 0` — the cap is 40 and this corpus produces at most 4
  candidate groups.

The `Chunks:` line and the two verdict-sum lines (`Refuted in verification`, `Verification
returned nothing`) are round 2 additions, and `Empty chunks` is a round 3 addition; a
report that omits any of them is non-conformant regardless of how many verdicts it gets
right.

## Exercising the agent against the same corpus

The corpus has no branch and therefore no diff, so the agent cannot derive its own scope
here. Dispatch it with the scope stated explicitly:

> Treat `pricing/invoice.py` as the only newly added unit. The rest of
> `tests/fixtures/twin-corpus` is the existing codebase. Does what it adds already exist?

Because this scope is caller-supplied, the agent's own exclusion pass never runs against
it — round 2 gated that pass to a self-derived scope only, so the fact that the corpus
lives under a `tests/` path segment (which the exclusion pass would otherwise treat as test
code) does not cause it to discard the scope it was given.

Expected: one `DIVERGENT` finding against `pricing/checkout.py:1`, naming at least the same
two behavioural differences as the table above. The agent must not report `slug/`,
`ordering/` or `validation/` at all — they are not in its asymmetric left-hand side. The
`### Scope` block must report 1 new unit examined (the caller-supplied scope), 0 units
dropped before comparison (dropping only applies to a self-derived scope), and 0 units with
no candidate found — the `checkout.py` twin must be found.

## Failure signatures worth naming

- **Divergent pair missing** — the worst outcome. Usually a stage 2 purpose sentence that
  described construction ("divides and multiplies") instead of effect ("converts gross to
  net minor units"), so the two never clustered.
- **Justified pair reported as a finding** — stage 4 ignored the stated decoupling. Without
  a working `JUSTIFIED` outcome the tool produces a wall of noise.
- **Near-miss reported as a twin** — stage 4 confirmed instead of refuting, or stage 2
  drifted toward describing shape rather than effect and the pair clustered when it
  should not have. Check that its brief is phrased as refutation, not review.
