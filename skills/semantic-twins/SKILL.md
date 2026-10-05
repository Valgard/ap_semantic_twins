---
name: semantic-twins
description: Use when hunting for semantic twins — type-4 clones, meaning functionally equivalent code that token- and AST-based detectors cannot see because the syntax is unrelated. Runs a whole-project audit in five stages. For the diff-scoped question "does what this change adds already exist in the codebase?", dispatch the semantic-twin-hunter agent instead (semantic-twins:semantic-twin-hunter when installed as a plugin); it is the same method with a smaller left-hand side.
---

# Semantic Twin Detection

Announce at start: "Using semantic-twins to audit <path> for type-4 clones."

Read `<skill base directory>/references/taxonomy.md` before stage 4. It defines four
verification outcomes plus one pre-verification exclusion, the ranking rule for ordering
findings — larger consolidation first within `STABLE` — and what a finding may claim.

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

Pass `--include-tests` when the caller wants the test corpus audited instead of skipped.
When you do, say so in the Coverage block's `Corpus:` line — a report of test-file twins
read as if it covered production code would mislead.

```bash
INVENTORY="$(mktemp "${TMPDIR:-/tmp}/twins-inventory-XXXXXX")"
python3 "<skill base directory>/scripts/inventory.py" <repo> > "$INVENTORY"
echo "$INVENTORY"
```

The path is unique per run — a fixed name collides between concurrent audits. It is echoed
above because shell state does not carry into your next instruction: read the path back
from the transcript, not from a variable that no longer exists by then.

If `python3` exited non-zero, or `$INVENTORY` is empty or does not parse as JSON, stop here
and report the command you ran and its output — do not proceed into stages that would read
nothing from a file that was never written correctly.

Read `totals`, `excluded`, `excluded_paths` and `unsupported_extensions` — stage 5's
`Excluded:` line, its `Unsupported extensions:` line and its seven path lists all come from
these four, so a stage that reads only the counts leaves the report with nothing to fill
the rest in. State the `totals` and `excluded` counts now.
If `totals.files` is zero, stop and report why: if every `excluded` counter is zero, nothing
was tracked — there is no committed source to audit. If `excluded.untracked` is the only
nonzero counter, files exist but none are committed — a branch in progress, `inventory.py`'s
most common case, not a report of wholesale filtering. Otherwise one or more of the other
`excluded` buckets is nonzero and every candidate file was filtered — name the nonzero
buckets.

Cap every `excluded_paths` list you print in the Coverage block at 20 entries, then say
`and <n> more` — the same pattern stage 2 uses for its empty-chunk list; none of these lists
comes with a cap built in. `excluded_paths.untracked` needs a second pass before either
capping or counting it: `inventory.py` deliberately does not run the extension whitelist or
the path-rule exclusions (`vendor`, `node_modules`, `migrations`, `__snapshots__`, `dist`,
`build` segments; `.min.js`/`.generated.cs` suffixes; test paths, unless `--include-tests`
was passed) against untracked paths — an untracked `node_modules/` or `.venv/` would
otherwise dwarf every other bucket in the same `Excluded:` line and dump tens of thousands of
paths into the report. Filter `excluded_paths.untracked` through those same rules yourself
before counting or listing it, so its number sits next to `unsupported extension` and `by
path rule` on equal footing.

The inventory's `repo` field holds the absolute audit root; every `files[].path` is relative
to it. Confirm `repo` matches the audit target before trusting anything downstream of it —
you read this field anyway for path joining, so the check costs nothing extra. Note that root
now: each `path` you hand to a stage 2 or stage 4 subagent must be the root joined with it,
because those subagents do not share your working directory. Paths quoted back in the report
stay relative — they are for a human reading about their own repo.

## Stage 2 — Purpose extraction

For each entry in `files`, dispatch one **`haiku`** subagent per chunk. Run them in
parallel, in batches of at most 20 concurrent dispatches.

Give each subagent this brief, with `<path>` and the line range filled in:

> Read `<path>` lines `<start>`–`<end>`. For every named unit defined in that range —
> function, method, class, type — emit exactly one JSON object per line, no prose, no
> fences:
>
> `{"file": "...", "line": 0, "name": "...", "kind": "function|method|class|type", "owner": "...", "purpose": "...", "inputs": "...", "outputs": "...", "effects": "...", "invariants": "..."}`
>
> **The `purpose` field states what the unit achieves, never how it is built.** This is the
> single rule that decides whether this run finds anything.
>
> - Good: "converts a gross price with a tax rate into net minor units, rounding half-up"
> - Bad: "loops over the line items and divides by a factor"
>
> "Rounding half-up" in the good example is a behaviour clause, not a construct: it names
> what the result looks like when the exact value sits between two answers, not how the
> code gets there. What follows the purpose must be observable in the result, not in the
> code — that is the line between a detail worth keeping and a construction sentence.
>
> Test your sentence before you emit it. The real test: **it must stay true if the unit were
> rewritten from scratch with completely different constructs.** If rewriting the
> implementation would falsify your sentence, the sentence describes the implementation, not
> the purpose — write it again.
>
> Naming a language construct is the surest sign of a sentence that will fail this test,
> including but not limited to: "loop", "regex", "recursion", "lookup", "iterates",
> "splits", "substitution", "character by character", "lowercasing", "collapsing",
> "trimming". This list illustrates the test, it does not replace it: a closed list invites
> reaching for the nearest unlisted word instead of applying the test.
>
> A construction sentence describes how two twins differ instead of how they agree, and
> sinks the pair invisibly. If you cannot say what a unit achieves, say
> `"purpose": "unclear"` — that is honest and recoverable; a construction sentence is not.
>
> `effects` names side effects (I/O, mutation, network, global state) or `none`.
> `invariants` names guards, throws and rounding rules, or `none`.
>
> `owner` names the class or type this unit is a member of — the nearest enclosing one, if
> the file declares more than one — or `none` for a unit with no enclosing class, including
> a class or type unit itself. Stage 3's containment rule reads this field directly, so
> get it right rather than leaving it for a start-line heuristic to approximate later.
>
> `file` must be copied byte for byte from the `<path>` you were given above — do not
> normalise, shorten or resolve it. A record whose `file` differs from the dispatched path
> is unusable downstream: it points at a different file, or at nothing.

Collect every line into one JSONL index. Before anything else, check each record's `file`
field against the path you dispatched that chunk against. Discard any record whose `file`
does not match exactly — do not cluster it — and count it as a path mismatch, in the same
spirit as the unparseable-line count below: a normalised or shortened path is not safe to
trust downstream.

Track what came back, per chunk: how many you dispatched — count chunks, not attempts, so a
chunk re-dispatched below is still one dispatch, not two — how many returned at least one
unit, how many returned nothing at all, how many lines failed to parse as JSON — count
the unparseable lines rather than dropping them silently — and how many records were
discarded as path mismatches. If a chunk returned nothing,
re-dispatch it once; count it toward "returned nothing" only if it is still empty after
that retry, so the number means "still empty after we tried again," not "empty on the first
try." Name the `path:range` of each chunk still empty after re-dispatch for the Coverage
block instead of letting it vanish — list up to 20 there and say "and `<n>` more" beyond
that, so a badly degraded run does not produce a report that is mostly a list of ranges.
These five numbers are mandatory in stage 5's report — a run where a third of the chunk
agents came back empty must not read like a complete one.

Before moving to stage 3, reconcile these numbers the way stage 5 reconciles its own:
chunks dispatched must equal chunks that returned at least one unit plus chunks that
returned nothing. Unparseable lines and path mismatches are a separate axis, counted within
whichever chunks produced them, not a third bucket in this sum. If the two sides do not
match, a chunk's outcome was miscounted — find it before proceeding.

Anchor the dispatch count against `totals.chunks` from stage 1's inventory — the one number
in this pipeline that a script, not a model, produced. If you dispatched fewer chunks than
`totals.chunks` (a context limit, a budget, a broken batch chain), that is not an internal
detail to absorb quietly: state both numbers side by side in the Coverage block's `Chunks:`
line — `<n> of <n> totals.chunks dispatched` — even when they match, so their absence never
has to be read as a claim of completeness.

Track, per file, whether every one of its chunks landed in "returned at least one unit."
`Examined: <n> files` in stage 5's report is that count — files stage 2 actually covered —
not `totals.files`, which is only what stage 1 planned to look at before any dispatch
happened. A file with even one chunk still empty after re-dispatch does not count as
examined.

Chunks overlap by 40 lines so that no unit straddling a seam is missed, which means a unit
inside the overlap is emitted by both neighbouring subagents. Before clustering, discard
records that duplicate an existing `(file, line, name)` — keep the first, drop the rest.
The unit count in stage 5's `Examined:` line is taken after this dedup, not before, so it
matches what stage 3 actually saw.

## Stage 3 — Clustering

Do this yourself, in one pass. Do not dispatch a subagent — this stage needs the whole
index in one context, which is exactly what a subagent does not have.

Read the entire index and group units whose `purpose` describes the same achievement,
regardless of naming, language or location. `purpose` is the key; use each unit's `effects`
as a secondary check — two units whose purpose reads alike but whose `effects` conflict (one
pure, one with I/O, mutation or network) are a weaker candidate pair, not an automatic
exclusion, since stage 4 is better placed than you are to say whether the conflict is real.
Keep them grouped, and let their `effects` and `invariants` travel with them into stage 4's
brief, where they are a refutation lead rather than something stage 4 has to rediscover from
the source on its own. For each group emit:

- the member locations as `path:line`, with each member's `effects` and `invariants`
  carried over from stage 2
- one sentence on the shared purpose
- a confidence from 1 to 5

Two units in the same group need not be in the same language or layer. A twin that crosses
module boundaries is the most valuable kind — two people solved the same problem without
knowing about each other.

Within each group, discard any member whose `path:line` duplicates another member's, even
after stage 2's dedup — a residual duplicate here is the same unit counted against itself,
not a second twin. This is the same guard stage 2's dedup applies, just at group-assembly
time; if a group is left with fewer than two distinct members afterward, discard the group
itself, since a twin needs at least two. Count each group discarded this way as
`Dropped as residual duplicate: <n> groups` for the Coverage block — a bucket of its own,
distinct from `Collapsed into container` below: this guard runs for a different reason
(an exact duplicate, not a contained unit) and a group it drops must not vanish into either
count.

Collapse containment next, before recording the candidate count below. Stage 2 inventories
a class and its own methods as separate units, so a class duplicated across two files
clusters twice: once as a class-level group, once as a method-level group per duplicated
method. Left alone, one duplication is reported once per contained unit, all competing for
slots under the cap below.

A class-level group X **contains** a method-level group Y when every member of Y has an
`owner` matching, in the same `file`, the `name` of a member of X. Stage 2's `owner` field
already resolves which enclosing class a method belongs to when a file declares more than
one, so this check needs no extra tie-breaking of its own. When X contains Y:

- From the stage 2 index, not from the groups alone, list every unit whose `(file, owner)`
  matches a member of X's `(file, name)`. This is the full contained set across all of X's
  members, including methods that never clustered into any group at all.
- For each of those methods, check whether it pairs, in some group, with the corresponding
  method of X's other member(s) — the method occupying the same role in the other class,
  ordinarily the same name.
- If every one of them pairs this way: report only X. Drop Y and any other method-level
  group made entirely of X's contained methods. Record how many contained units matched as
  its own field on X — `<k> of <n> contained units matched`, where `n` is the contained-unit
  count of **one** member of X, not the total summed across every member: for a two-member X
  with one method each, the intended reading is `1 of 1` per member, not `2 of 2` summed
  across both. Since a full match means every member's contained set is the same size, any
  one member fixes `n`. Not appended to the shared-purpose sentence: stage 4 is free to
  rewrite that sentence after reading the source, and a note folded into it would not
  survive the rewrite.
- If even one of them does not pair — a unique method, or one whose counterpart in the
  other class never clustered — the class is only partly duplicated. Drop X instead and
  keep the method-level groups that did pair as separate findings. A partial match is not a
  whole-class finding: reporting X anyway would claim more duplication than exists.

The same containment relationship can also land inside a single group instead of across
two: a class and one of its own methods sometimes cluster together in one group, because
their purpose sentences read alike. Apply the same guard the dedup step above already uses,
extended from exact duplicates to containment: if a group has a member that is itself
contained — by the test above — in another member of the *same* group, discard the
contained member and keep the container. If fewer than two distinct members remain in the
group afterward, discard the group itself, since a twin needs at least two.

Record the surviving count as **candidate groups** — the Coverage block reports it before
the next step caps it. Also record how many groups the containment collapse above removed —
whether by the cross-group X-contains-Y rule or the single-group cleanup that follows it —
as `Collapsed into container: <n> groups`, so a collapsed group stays distinguishable from
one that never clustered at all.

Sort groups by confidence, descending. Take the top **40** (or a higher cap the caller
named). State how many groups you dropped at the cap.

If the index exceeds roughly 20,000 units it no longer fits one context. Then partition it
by top-level directory, cluster each partition separately, and run a second pass over the
per-partition group summaries to catch twins that cross partitions. State in the report
whether you partitioned and into how many partitions, because a cross-partition twin is the
most valuable kind and this is where one can be lost.

## Stage 4 — Adversarial verification

Dispatch one subagent per group — omit the model parameter on the dispatch so it inherits
the orchestrator's model strength, the mirror of stage 2's explicit `haiku` — in parallel
batches of at most 10.

Give each subagent this brief, with the member list (each member's `inputs`, `outputs`,
`effects` and `invariants` from stage 2 included), stage 3's shared-purpose sentence, and —
when stage 3 recorded one — its contained-units-matched count, filled in:

> Read the **actual source around** each of these locations: `<path:line list>` — the whole
> file, or enough of it to see what sits above the cited line, not only the line itself. A
> `JUSTIFIED` verdict rests on evidence that sits above the unit — a comment, an ADR
> reference, a commit message — never inside the cited line, so reading only that line
> cannot find it. If a comment refers to a decision recorded elsewhere, say so and quote
> what is actually present rather than assuming the reference alone is sufficient. Stage 3's
> summary layer clustered them on this claimed shared purpose: `<stage 3's purpose
> sentence>`. Treat that as a lead, not a fact — do not rely on any summary. Stage 2 also
> recorded each member's `inputs`, `outputs`, `effects` and `invariants`: `<member
> inputs/outputs/effects/invariants list>`. Treat these as leads too — a claimed `none` is
> as unverified as the purpose sentence until you have read the source. A signature
> mismatch is a refutation lead of the same kind: two units with the same stated purpose,
> one taking a string and returning a string, the other taking a list and returning
> nothing, are probably not twins.
>
> Your job is **refutation**. Find the reason these are not the same thing. Only if you
> cannot find one do you report a twin.
>
> Then assign exactly one outcome:
>
> - `DIVERGENT` — same purpose, different behaviour. A fix, an edge case or a validation
>   landed on one side only. A defect, not tidiness. List every behavioural difference and
>   say which side appears corrected and why.
> - `STABLE` — same purpose, same behaviour. Debt, nothing broken.
> - `JUSTIFIED` — deliberately separate: different bounded contexts, an anti-corruption
>   layer against a foreign schema, deliberately independent lifecycles, or a comment, ADR
>   or commit message stating the decoupling. Quote that evidence. Named, never counted as
>   a finding.
> - `NOT_A_TWIN` — you found the reason they differ.
> - `UNREADABLE` — a cited location could not be read: a wrong path, a deleted file, or
>   content that no longer matches what stage 3 clustered. Say which member and why. This is
>   not `NOT_A_TWIN`: you found no evidence at all, not a reason the two differ, and it must
>   not be counted as a health signal the way a refutation is. Not one of the taxonomy's four
>   verdicts either — the same kind of escape stage 2's `"purpose": "unclear"` is, scoped to
>   this stage.
>
> Return the shared purpose as one sentence, as it stands after reading the source —
> corrected from stage 3's claim if that claim was wrong.
>
> If a contained-units-matched count was given to you above, return it unchanged in your
> response. It is a structural fact about the group's composition from stage 3, not a claim
> about behaviour, so reading the source does not revise it.
>
> For every member, report its line span as `path:start-end` and its line count. For a
> `STABLE` verdict these numbers are required, not optional: they are the only input to the
> consolidation size the report ranks by.
>
> Cite the concrete `path:line` location of **every member** of the group. Make no claim
> about a category, a layer or a module.

## Stage 5 — Report

Reconcile before writing anything. The number of groups dispatched to verification is not
something to recall from memory — compute it as candidate groups (before the cap) minus
`Dropped at the cluster cap`, both already required below, so it is anchored on numbers
fixed at stage 3, not on how stage 4's dispatch loop felt like it went. Unlike stage 2's
anchor against `totals.chunks`, this side is self-reported, not script-measured — there is
no equivalent of a script-counted number for groups. What holds it steady instead is
sequencing: stage 3 finishes and this count is fixed before stage 4 ever dispatches, so a
stage 4 failure cannot shrink it in sympathy. Print that computed count in the Coverage
block as `Dispatched to verification: <n> groups` so the arithmetic is checkable from the
report alone, without a reader having to re-derive it. Sum the verdicts
stage 4 actually returned — `DIVERGENT` + `STABLE` + `JUSTIFIED` + `NOT_A_TWIN` +
`UNREADABLE` — and compare it to that computed count. They must match; any shortfall is a
stage 4 dispatch that came back empty, and belongs in the Coverage block as
`Verification returned nothing`, not silently absorbed into whichever total is convenient.
A failed stage 4 dispatch must not be indistinguishable from a group that never existed.

Groups can have more than two members — the consolidation formula is member-count
arithmetic (sum of the members minus the largest), not a pairwise one. Every heading below
lists **every member**, comma-separated, however many there are: a pair is a group of two,
not a separate shape.

```
# Semantic Twin Audit — <repo>

## Defects: divergent twins (N)

### <path:line>, <path:line>, ...
Shared purpose: <one sentence>
Contained units matched: <n> of <n> (containment-collapsed groups only, from stage 3)
Differences:
- <behavioural difference>
Likely corrected side: <path> — <evidence>

## Debt: stable twins (N)

### <path:line>, <path:line>, ...
Shared purpose: <one sentence>
Contained units matched: <n> of <n> (containment-collapsed groups only, from stage 3)
Consolidation: ~<n> lines

## Justified duplication (N)
- <path:line>, <path:line>, ... — <reason, with the evidence quoted> (containment-collapsed groups only: contained units matched <n> of <n>)

## Coverage
Corpus: <all source files | tests>
Examined: <n> files, <n> units, <n> candidate groups (before the cap)
Collapsed into container: <n> groups
Dropped as residual duplicate: <n> groups
Chunks: <n> of <n> totals.chunks dispatched, <n> returned units, <n> returned nothing, <n> unparseable lines, <n> path mismatches
Empty chunks (still empty after re-dispatch): <path:range>, <path:range>, ... and <n> more (or none)
Partitioned: yes (<n> partitions) | no
Excluded: <n> by path rule, <n> unsupported extension, <n> generated, <n> symlink, <n> submodule, <n> untracked, <n> missing, <n> undecodable, <n> permission denied
Unsupported extensions: <ext>: <n>, <ext>: <n>, ... (or none)
Generated files: <path>, <path>, ... (or none)
Symlink files: <path>, <path>, ... (or none)
Submodule files: <path>, <path>, ... (or none)
Untracked files: <path>, <path>, ... (or none)
Missing files: <path>, <path>, ... (or none)
Undecodable files: <path>, <path>, ... (or none)
Permission denied files: <path>, <path>, ... (or none)
Dispatched to verification: <n> groups
Refuted in verification (NOT_A_TWIN): <n> groups
Unreadable in verification (UNREADABLE): <n> groups
Verification returned nothing: <n> groups
Dropped at the cluster cap: <n> groups
```

Consolidation size is the sum of the members' line counts minus the largest member's — what
would disappear if the twins were merged into the largest one. Write it as an estimate,
because it is one: a consolidation that needs a new shared abstraction saves less than the
arithmetic suggests.

Omit the `Contained units matched` line entirely for an ordinary group — most groups are not
the product of stage 3's containment collapse, and the line only means something for the
ones that are.

The paths reaching you from stages 3 and 4 are absolute, because that is what you handed the
subagents. Strip the audit root back off before writing the report: a reader wants
`src/Pricing/NetCalculator.cs:42`, not an absolute path from someone else's machine.

Report defects before debt. Do not propose the refactoring itself: merging two twins is an
architecture and product decision, and across a bounded-context boundary duplication is
frequently correct.

## Honest limits, state them in the report

- Stage 2 is the recall bottleneck. A poor purpose sentence sinks a pair invisibly — it
  appears nowhere as "checked and rejected".
- No completeness claim.
- This does not satisfy the hook-enforced PR review gate, which recognises
  `pr-review-toolkit:*` agents and the `ck-docs-review` lanes. It is additive.
