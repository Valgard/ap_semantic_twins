---
name: semantic-twins
description: Use when hunting for semantic twins — type-4 clones, meaning functionally equivalent code that token- and AST-based detectors cannot see because the syntax is unrelated. Runs a whole-project audit in five stages. For the diff-scoped question "does what this change adds already exist in the codebase?", dispatch the semantic-twin-hunter agent instead; it is the same method with a smaller left-hand side.
---

# Semantic Twin Detection

Announce at start: "Using semantic-twins to audit <path> for type-4 clones."

Read `references/taxonomy.md` before stage 4. It defines the five outcomes and what a
finding may claim.

## What this is for

Clone detectors work on normalised tokens or AST hashes, which covers types 1 to 3 —
identical, renamed, near-miss. They are structurally blind to type 4: two units that do
the same thing with unrelated syntax. That is the only reason to spend model tokens here.
If the user wants types 1 to 3, point them at jscpd and stop.

## Stage 1 — Inventory

This skill is loaded with a "Base directory for this skill: `<dir>`" line. Use that
directory: the script ships with the skill, not with the project under audit, so a relative
path would resolve against the target repo and fail. `inventory.py` is standard library
only, so plain `python3` suffices — do not use `uv run`, which would bind to whatever
project happens to sit in the working directory.

```bash
python3 "<skill base directory>/scripts/inventory.py" <repo> > /tmp/twins-inventory.json
```

Read the `totals` and `excluded` counts and state them. If `totals.files` is zero, stop
and report why — an empty inventory means every file was filtered, not that the project
is clean.

## Stage 2 — Purpose extraction

For each entry in `files`, dispatch one **`haiku`** subagent per chunk. Run them in
parallel, in batches of at most 20 concurrent dispatches.

Give each subagent this brief, with `<path>` and the line range filled in:

> Read `<path>` lines `<start>`–`<end>`. For every named unit defined in that range —
> function, method, class, type — emit exactly one JSON object per line, no prose, no
> fences:
>
> `{"file": "...", "line": 0, "name": "...", "kind": "function|method|class|type", "purpose": "...", "inputs": "...", "outputs": "...", "effects": "...", "invariants": "..."}`
>
> **The `purpose` field states what the unit achieves, never how it is built.** This is the
> single rule that decides whether this run finds anything.
>
> - Good: "converts a gross price with a tax rate into net minor units, rounding half-up"
> - Bad: "loops over the line items and divides by a factor"
>
> A construction sentence describes how two twins differ instead of how they agree, and
> sinks the pair invisibly. If you cannot say what a unit achieves, say
> `"purpose": "unclear"` — that is honest and recoverable; a construction sentence is not.
>
> `effects` names side effects (I/O, mutation, network, global state) or `none`.
> `invariants` names guards, throws and rounding rules, or `none`.

Collect every line into one JSONL index.

## Stage 3 — Clustering

Do this yourself, in one pass. Do not dispatch a subagent — this stage needs the whole
index in one context, which is exactly what a subagent does not have.

Read the entire index and group units whose `purpose` describes the same achievement,
regardless of naming, language or location. For each group emit:

- the member locations as `path:line`
- one sentence on the shared purpose
- a confidence from 1 to 5

Two units in the same group need not be in the same language or layer. A twin that crosses
module boundaries is the most valuable kind — two people solved the same problem without
knowing about each other.

Sort groups by confidence, descending. Take the top **40** (or `--max-clusters` if the user
raised it). State how many groups you dropped at the cap.

If the index exceeds roughly 20,000 units it no longer fits one context. Then partition it
by top-level directory, cluster each partition separately, and run a second pass over the
per-partition group summaries to catch twins that cross partitions. Say in the report that
you partitioned, because a cross-partition twin is the most valuable kind and this is where
one can be lost.

## Stage 4 — Adversarial verification

Dispatch one subagent per group, at inherited model strength, in parallel batches of at
most 10.

Give each subagent this brief:

> Read the **actual source** at each of these locations: `<path:line list>`. Do not rely on
> any summary.
>
> Your job is **refutation**. Find the reason these are not the same thing. Only if you
> cannot find one do you report a twin.
>
> Then assign exactly one outcome from `references/taxonomy.md`: `DIVERGENT`, `STABLE`,
> `JUSTIFIED` or `NOT_A_TWIN`. For `DIVERGENT`, list every behavioural difference and say
> which side appears corrected and why. For `JUSTIFIED`, quote the evidence for the
> deliberate separation.
>
> Cite two concrete `path:line` locations. Make no claim about a category, a layer or a
> module.

## Stage 5 — Report

```
# Semantic Twin Audit — <repo>

## Defects: divergent twins (N)

### <path:line> ↔ <path:line>
Shared purpose: <one sentence>
Differences:
- <behavioural difference>
Likely corrected side: <path> — <evidence>

## Debt: stable twins (N)

### <path:line> ↔ <path:line>
Shared purpose: <one sentence>
Consolidation: ~<n> lines

## Justified duplication (N)
- <path:line> ↔ <path:line> — <reason, with the evidence quoted>

## Coverage
Examined: <n> files, <n> units, <n> candidate groups
Excluded: <n> generated, <n> by path rule, <n> unsupported extension, <n> unreadable
Refuted in verification: <n> groups
Dropped at the cluster cap: <n> groups
```

Report defects before debt. Do not propose the refactoring itself: merging two twins is an
architecture and product decision, and across a bounded-context boundary duplication is
frequently correct.

## Honest limits, state them in the report

- Stage 2 is the recall bottleneck. A poor purpose sentence sinks a pair invisibly — it
  appears nowhere as "checked and rejected".
- No completeness claim.
- This does not satisfy the hook-enforced PR review gate, which recognises
  `pr-review-toolkit:*` agents and the `ck-docs-review` lanes. It is additive.
