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
| `ordering/CustomerDto.php:5` ↔ `shipping/CustomerDto.php:7` | `JUSTIFIED` | Identical mapping across two bounded contexts, with the decoupling stated in a comment. Named, not counted as a finding. Reported at the class rather than the method, because every unit the class contains — here, its one `fromRow` method — also pairs. This group is containment-collapsed, so `SKILL.md`'s `## Justified duplication` line for it must include `(contained units matched 1 of 1)`; a report that names the pair and its reason but omits that parenthetical passes the verdict yet still violates `SKILL.md`. |
| `validation/email.py:1` ↔ `validation/postcode.py:1` | not reported as a twin | Both functions are named `validate`, take one argument and raise on rejection, so a stage 2 that drifted toward describing shape rather than effect would cluster them; a rule-following stage 2 will not. The run fails only if the pair is reported as a twin of any kind (`DIVERGENT`, `STABLE` or `JUSTIFIED`). Whether it was clustered and then refuted (`NOT_A_TWIN`, which appears only as a count) or never clustered at all is not something the report can distinguish, and is not graded. |
| `generated/Mapper.g.cs:10` ↔ `slug/category.py:1` | never reported | The generated file must not reach stage 2 at all. |

## How to run it

1. `python3 "$(pwd)/scripts/inventory.py" tests/fixtures/twin-corpus`, run from the repository root so `$(pwd)` is the skill base directory — the invocation form `SKILL.md` mandates for stage 1: plain `python3` (no `uv run`) against an absolute path to the script, never a path relative to the target repo. `uv run` stays reserved for this repo's own dev-time tooling (pytest, ruff, vulture — see README.md); using it here instead would exercise a different code path than the one that ships.
   → `generated/Mapper.g.cs` must not appear in `files`, and `excluded.generated` must be `1`. To check it by name instead of by count, `excluded_paths.generated` now lists the path.
2. Invoke the `semantic-twins` skill against `tests/fixtures/twin-corpus`.
3. Compare the report against the table above and the `## Coverage` expectations below.

## Coverage

`SKILL.md`'s report ends in a `## Coverage` block. Grading a run means checking it too, not just the verdict table above — a run that gets every verdict right but omits or misreports this block is still non-conformant. Expected values for this corpus, in the order `SKILL.md`'s template lists them:

- `Corpus: all source files` — `--include-tests` was not passed, and the corpus has no test-shaped file to skip anyway.
- `Examined:` `8` files — this is stage 2's per-file coverage count (`SKILL.md` is explicit that it counts files whose chunks all returned at least one unit, not `totals.files`, which is only what stage 1 planned to look at). It equals `totals.files`'s `8` here because, per the `Chunks` line below, all `8` of `totals.chunks`'s `8` chunks were dispatched, none returned nothing, and none was discarded as a path mismatch — so every file's every chunk lands in "returned at least one unit" and no file drops out. Units and candidate groups are stage 2/3 output and not pinned to a single number: candidate groups before the cap is `3` if the near-miss pair (`validation/`) is never clustered, or `4` if it is — in which case that fourth group must resolve to `NOT_A_TWIN` in the `Refuted in verification` line below, per the near-miss row above. That `3` already assumes stage 3's containment collapse ran: `CustomerDto` inventories as both a class-level and a method-level unit in each of `ordering/` and `shipping/`, which clusters into two candidate groups — one per level — before collapsing into the single class-level group counted here. A change to which unit kinds stage 2 inventories changes this number.
- `Collapsed into container: 1` group — the one candidate group this corpus's containment collapse removes: `CustomerDto`'s method-level group (`fromRow` ↔ `fromRow`), absorbed into the class-level group already counted above. This is `1` regardless of whether the near-miss clusters, since `validation/` has no class wrapper and plays no part in containment collapse — the same holds for `checkout`/`invoice` and `article`/`category`, which declare no class either. The `generated` pair does declare a class (`Mapper`), but it never reaches stage 2 at all: `inventory.py` excludes it before stage 2 runs, so it plays no part in containment collapse for that reason, not because it lacks one.
- `Dropped as residual duplicate: 0` groups — nothing in this corpus produces an exact `(file, line)` duplicate within a single candidate group; every group's members are distinct locations from the start.
- `Chunks:` `8` of `8` `totals.chunks` dispatched, `8` returned units, `0` returned nothing, `0` unparseable lines, `0` path mismatches — one chunk per file (`totals.chunks` is also `8`; none of the eight files exceeds 800 lines), and every file in this corpus defines a named unit, so a healthy run reports `0` for `returned nothing` and `unparseable lines` alike, and `0` for `path mismatches` too — the dispatched subagents return the `file` path unchanged.
- `Empty chunks (still empty after re-dispatch): none` — follows from `returned nothing` being `0` above; there is nothing to name.
- `Partitioned: no` — 8 units is nowhere near the 20,000-unit partitioning threshold.
- `Excluded:` `0` by path rule, `0` unsupported extension, `1` generated, `0` symlink, `0` submodule, `0` untracked, `0` missing, `0` undecodable, `0` permission denied — from the same inventory run as step 1, in the order `SKILL.md`'s Coverage template lists the nine counters.
- `Unsupported extensions: none`.
- `Generated files: generated/Mapper.g.cs`.
- `Symlink files: none`.
- `Submodule files: none`.
- `Untracked files: none`.
- `Missing files: none`.
- `Undecodable files: none`.
- `Permission denied files: none`.
- `Dispatched to verification:` `3` or `4` groups, matching whichever candidate-group count above applied — this corpus's cap (40) never binds, so `Dropped at the cluster cap` is `0` and `Dispatched to verification` equals candidate groups unchanged.
- `Refuted in verification (NOT_A_TWIN):` `1` group if the near-miss pair clustered, `0` if it never did.
- `Unreadable in verification (UNREADABLE): 0` groups — every cited location in this corpus is a real, readable file; nothing here should cause a stage 4 dispatch to name a member it could not read.
- `Verification returned nothing: 0` — nothing in this corpus should cause a stage 4 dispatch to come back empty.
- `Dropped at the cluster cap: 0` — the cap is 40 and this corpus produces at most 4 candidate groups.

Every line above is a required part of a conformant report, not only the ones that happen to be checkable by eye. `tests/test_acceptance_coverage.py` pins the following against a real `build_inventory` run on this corpus: `Examined:`'s files count, all six numbers in `Chunks:`, the nine `Excluded:` counters, `Unsupported extensions:`, and the seven `<Label> files:` lines. It does not pin `Corpus:`, `Collapsed into container`, `Dropped as residual duplicate`, `Empty chunks`, `Partitioned`, `Dispatched to verification`, `Refuted in verification`, `Unreadable in verification`, `Verification returned nothing`, `Dropped at the cluster cap`, or the units/candidate-group figures inside `Examined:` — none of those are `build_inventory` output, so there is nothing to compare them against; they stay stage 2/3/4 judgement, checked only by a reader. The test compares this document's numbers against `build_inventory`, not against a generated report — it catches this document falling out of sync with the corpus, not a bad run of the skill itself.

## Exercising the agent against the same corpus

The corpus has no branch and therefore no diff, so the agent cannot derive its own scope here. Dispatch it with the scope stated explicitly:

> Treat `pricing/invoice.py` as the only newly added unit. The rest of
> `tests/fixtures/twin-corpus` is the existing codebase. Does what it adds already exist?

Because this scope is caller-supplied, the agent's own exclusion pass never runs against it — that pass only applies to a scope the agent derives itself, so the fact that the corpus lives under a `tests/` path segment (which the exclusion pass would otherwise treat as test code) does not cause it to discard the scope it was given. The same holds on the candidate side: `pricing/checkout.py`, found while searching, also sits under that `tests/` path segment, but the caller's own named scope (`pricing/invoice.py`) sits inside that same test tree — so the test-code exclusion on candidates is dropped for this run too, and `checkout.py` stays eligible to be reported instead of silently folding into the excluded count.

Expected: one `DIVERGENT` finding against `pricing/checkout.py:1`, naming at least the same two behavioural differences as the table above. The agent must not report `slug/`, `ordering/` or `validation/` as findings — they must not appear under Defects, Duplicates or Justified duplication. Appearing in the `### Checked and refuted` count is expected and correct: they are candidates on the existing-code side, examined and found not to match, which is a different thing from being part of its asymmetric left-hand side. The `### Scope` block must report 1 new unit examined (the caller-supplied scope), 0 units dropped before comparison (dropping only applies to a self-derived scope), and 0 units with no candidate found — the `checkout.py` twin must be found.

## Failure signatures worth naming

- **Divergent pair missing** — the worst outcome. Usually a stage 2 purpose sentence that described construction ("divides and multiplies") instead of effect ("converts gross to net minor units"), so the two never clustered.
- **Justified pair reported as a finding** — stage 4 ignored the stated decoupling. Without a working `JUSTIFIED` outcome the tool produces a wall of noise.
- **Near-miss reported as a twin** — stage 4 confirmed instead of refuting, or stage 2 drifted toward describing shape rather than effect and the pair clustered when it should not have. Check that its brief is phrased as refutation, not review.
