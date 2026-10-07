# Open decisions — reply

2026-09-24 · Ranjit Savant

Of the six decisions raised across both streams, one is mine and is answered
below; four need Minnie, with a recommendation on each; and the sixth is my
view on the pass mark, written deliberately before anyone has seen an
agreement number.

## 5. Value objects — mine, and the answer is yes with one hold

Agreed on both counts, with a caveat on the third.

**Tighten `ProcessGap`.** Require `gap_type` and `proposed_change` when
`present`. No objection — a gap you cannot route and cannot act on is not a
finding.

**Switch both to `ValidationError`.** Agreed, and overdue. `domain/errors.py`
defines it and these two are the odd ones out raising a bare `ValueError`.

**Hold on requiring `correct_statement` on `KnowledgeFailure`.** The module's
own docstring says D7 is open with Karim and "do not label it an agent error,
and do not add a correction or a heuristic". Requiring a correction may cut
against that. Tighten the other two now and let this one wait for D7 to close.

One thing to check before merging: stricter constructors mean stored rows
written under the looser rules can now raise on read. Anything rehydrating
these from the database — including the insights corpus source added in
`infrastructure/persistence/repositories/insights_source.py` — would fail on
that data rather than skip it. Worth counting the existing rows first.

## 6. What is good enough — the shape, before the numbers

No numbers here, deliberately. But the shape is worth agreeing first, because
it is the part that stops being an honest choice the moment we see results.

1. **Set the bar per insight, not per field.** A field at 70% might be fine
   behind a ranking and unacceptable behind a flag. `insight_dependencies.py`
   already maps field to insights, so the machinery exists.
2. **Two bars, not one.** A floor below which we do not build the screen, and
   a band where we build but label the panel. A single number forces every
   borderline field into a yes/no we will regret.
3. **Coverage counts as much as agreement.** 95% agreement on 20% of calls is
   worse than 80% on all of them. `Agreement` reports both — a high rate on a
   thin comparable set should not clear the bar.
4. **A higher bar where a figure names someone.** Risk flags, broker
   attribution and compliance exposure act on an account or a person.
   Exploratory rankings can run lower.
5. **An insight is only as strong as its weakest field.**
   `LayerAgreement.weakest` already computes this. Make it the gating number
   rather than an average, which hides exactly the field that breaks the
   insight.

## 1. `missing_benefit_disclosure` — recommend (b), keep metric 7 deterministic

Two reasons.

None of the 100 answer-key calls carries this type, so a model detector could
not be validated by Phase 5 at all. We would be shipping an unmeasured
detector into a compliance figure, which is the worst place to have one.

And "Deterministic — no model judgement" is metric-specific and
compliance-facing, where the schema's L1/L3 note is a general statement
covering all three types. The narrower, more specific instruction should win.

**A separate fact, true under either answer.** `control_exceptions` is stored
only on the `ground_truth` table. There is no column for it on
`call_extractions`, and L1 is recomputed on demand rather than persisted, so
anything reading stored extractions cannot see it. Metric 7 needs either a
persisted column or L1 recomputed at read time before it can report anything
— including the two types already detected. That work is needed whichever way
this decision goes.

## 2. `EpistemicClass` — confirm now, and the shape looks wrong

The three values (MEASURED / DERIVED / WITHHELD) were inferred from what the
sources imply; nothing defines them. They are now in the API's wire format and
the generated client, so this is the last cheap moment.

Beyond confirming the values, there is a concrete problem. The enum conflates
two independent things: whether a figure is our composite, and whether it is
published. A **derived** figure that gets withheld comes back as WITHHELD,
losing the fact that it was a composite. The plan says composites must be
labelled "wherever they surface", and a withheld panel is a surface.

Suggested split: `basis` (MEASURED or DERIVED) alongside the `published` flag
and `withheld_reason` the response already carries. Cost today is one enum and
a client regeneration. Cost after the screens are built is every consumer.

This is the only item on the list that creates work rather than closing a
question, so it is a recommendation rather than a request.

## 3. `indicators.min_rate: 0.2` — recommend dropping it unless it can be sourced

The floor (5 employer calls, 2 hits) comes from the prototype. The rate does
not come from anywhere.

At batch-1 volume it also does nothing: 2 hits over 5 calls is 0.4, twice the
threshold. It only starts excluding employers at roughly 10 or more calls
each, which is past this corpus. So it is inert now and will silently begin
filtering later on a number nobody chose — the worst of both.

Either source it or drop it and keep the floor.

## 4. `score` and `escalation.requested_by_caller` — recommend recording, not fixing

`score` is published as metric 12 but is explicitly "never averaged to
employer, product line or broker", and the agents screen is "events, not
scores". If no screen quotes a per-call score then nothing is missing — but
that wants confirming rather than assuming. Either way it stays scored in the
harness, since it measures extraction quality whether or not a screen reads
it.

`escalation.requested_by_caller` reaches the screens only through the
`escalation_missed` signal. If that is intended, then "scored but not read
directly" is a correct state rather than a gap.

Neither blocks anything.

## Still blocked

Item 6 only becomes actionable once we have agreement numbers, and those need
an extraction run over the full corpus — real API spend plus member
conversation data leaving the building. Not yet authorised.

Items 1 to 5 do not depend on it.
