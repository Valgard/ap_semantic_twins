# Acceptance corpus

`tests/fixtures/twin-corpus/` carries one planted case per taxonomy outcome. Running the
skill against it must produce exactly these verdicts. Anything else is a regression.

| Pair | Expected outcome | Why |
| --- | --- | --- |
| `pricing/checkout.py:1` ↔ `pricing/invoice.py:1` | `DIVERGENT` | Same purpose, two behavioural differences: side B lacks the negative-rate guard and truncates where side A rounds half-up. The report must name both differences and identify side A as the corrected one. |
| `slug/article.py:4` ↔ `slug/category.py:1` | `STABLE` | The two share a purpose and an output — both turn a name into a URL-safe key — while sharing no structure, no call and no literal: one is a regex substitution, the other a character-by-character loop. This is the corpus's type-4 case, the only reason this tool exists rather than a token- or AST-based clone detector. A run that misses it has failed at the thing the tool exists for. |
| `ordering/CustomerDto.php:7` ↔ `shipping/CustomerDto.php:9` | `JUSTIFIED` | Identical mapping across two bounded contexts, with the decoupling stated in a comment. Named, not counted as a finding. |
| `validation/email.py:1` ↔ `validation/postcode.py:1` | `NOT_A_TWIN` | Both summarise as "validates user input" and will cluster together. Stage 4 must refute them: they validate unrelated things. |
| `generated/Mapper.g.cs:10` ↔ `slug/category.py:1` | never reported | The generated file must not reach stage 2 at all. |

## How to run it

1. `uv run python scripts/inventory.py tests/fixtures/twin-corpus`
   → `generated/Mapper.g.cs` must appear in `excluded.generated`, not in `files`.
2. Invoke the `semantic-twins` skill against `tests/fixtures/twin-corpus`.
3. Compare the report against the table above.

## Exercising the agent against the same corpus

The corpus has no branch and therefore no diff, so the agent cannot derive its own scope
here. Dispatch it with the scope stated explicitly:

> Treat `pricing/invoice.py` as the only newly added unit. The rest of
> `tests/fixtures/twin-corpus` is the existing codebase. Does what it adds already exist?

Expected: one `DIVERGENT` finding against `pricing/checkout.py:1`, naming both behavioural
differences. The agent must not report `slug/`, `ordering/` or `validation/` at all — they
are not in its asymmetric left-hand side.

## Failure signatures worth naming

- **Divergent pair missing** — the worst outcome. Usually a stage 2 purpose sentence that
  described construction ("divides and multiplies") instead of effect ("converts gross to
  net minor units"), so the two never clustered.
- **Justified pair reported as a finding** — stage 4 ignored the stated decoupling. Without
  a working `JUSTIFIED` outcome the tool produces a wall of noise.
- **Near-miss reported** — stage 4 confirmed instead of refuting. Check that its brief is
  phrased as refutation, not review.
