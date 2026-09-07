# Finding taxonomy

Every candidate pair or group leaves verification with exactly one outcome.

## `DIVERGENT` — a defect

Same purpose, different behaviour. A fix, an edge case or a validation landed on one side
only. This is a latent bug, not tidiness, and it is reported first.

Report it as a behavioural difference, not as duplication:

> `pricing/checkout.py:1` and `pricing/invoice.py:1` both convert a gross price into net
> minor units. They differ in two ways: `invoice.py` truncates where `checkout.py` rounds
> half-up, and it lacks the negative-rate guard. `checkout.py` looks like the corrected
> side.

Always name which side appears corrected, and say what the evidence for that is.

## `STABLE` — debt

Same purpose, same behaviour. Doubled maintenance load, nothing broken. Ranked by how much
code consolidation would remove.

## `JUSTIFIED` — deliberately separate

Duplication that is the right answer. Named in the report, never counted as a finding.
Recognise it by:

- the two sides live in different bounded contexts, and coupling them would couple the
  contexts
- one side is an anti-corruption layer against a foreign schema
- a comment, ADR or commit message states the decoupling
- the two sides belong to different layers with deliberately independent lifecycles

This outcome is the condition for the tool being used at all. Without a legitimate "this is
fine" verdict the report becomes a wall of noise and is ignored after two runs.

## `NOT_A_TWIN` — refuted

Verification found a reason the two are not the same thing. Appears only in the tally.

Expect a lot of these, and treat that as the system working. Summaries agree easily where
source does not: "validates user input" describes dozens of unrelated functions.

# Pre-verification exclusion

## `GENERATED` — out of scope

Generated code and migrations. Snapshots and minified bundles fall under the same
pre-verification exclusion. Excluded before verification; counted only. It never reaches
verification, so it is not one of the four outcomes above.

# Ranking

`DIVERGENT` before `STABLE`. Within the `STABLE` section in audit mode, larger
consolidation first. A drifted twin is a latent bug; a stable twin is maintenance load and
nothing worse.

# What a finding may claim

Every finding cites **two concrete locations** as `path:line`. It never makes a claim about
a category, a layer or a module. A correctly measured single case placed under a category
heading claims a reach it has not earned.

The report also states what it examined and what it excluded. It makes no completeness
claim.
