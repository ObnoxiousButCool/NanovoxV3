# Phase 5 — Evaluation harness

Joint work between the two backend streams, and the deliberate check-in gate
both stream documents stop at. It compares the extraction pipeline's output
against the `ground_truth` answer key, field by field, and the numbers go to
Minnie before anyone builds a screen on them.

Read §8 Phase 5 and §6.3 of `plan.md` first. This document says what to
build and in which order; it does not restate what the fields mean.

**Why this is a gate and not a task.** Screens are built on pipeline output.
A field with poor agreement means a screen that shows poor data, confidently,
with a call-id drawer behind it. Which fields are good enough is decided
with the numbers in hand, together — not assumed, and not decided by whoever
writes the endpoint.

---

## 1. Where the code stands

Both halves finally exist, which is what makes this possible at all.

| | |
|---|---|
| Pipeline output | `call_extractions`, `signals`, `score_markers` — L1 through L4 (Stream A, A1–A6) |
| Answer key | `ground_truth`, 24 tracker columns, reconciled against the PDF (Stream B, B1) |
| Run records | `runs`, `run_items` — status, provider, model, timings (A6) |
| Comparison precedent | `compare_shared_fields()` in `application/use_cases/import_answer_key.py` |

That last one is worth reading before writing anything. B1 already compares
the tracker against the PDF across five fields and reports disagreements
rather than resolving them. This phase is the same shape over a wider field
set and a different second source.

---

## 2. Before you start — two duplicates left on main

Stream A merged as PR 23373 (`8d3d5e5`). Main is green: 781 tests pass, mypy
clean, one migration head.

**Two of the four prerequisites are already closed.** The five text
conflicts were resolved in the merge, and the forked migration chain was
straightened — `alembic heads` reports one head, which is what
`scripts/check.sh` gates on.

Note how the value objects landed, because it is not what the merge notes
proposed: Stream B's `process_gap.py` won, with `ProcessGapStatus` and
`RaisedBy` inlined, and Stream A's L4 code was adapted to import from it.
That is coherent and it typechecks — but two invariants were loosened in the
process. A present knowledge failure no longer has to carry a
`correct_statement`, a present process gap no longer has to carry
`gap_type`, `proposed_change` or `raised_by`, and both raise `ValueError`
rather than the domain `ValidationError` the delivery layer maps to a
problem response. Worth a look before E1 relies on either field being
populated.

**Both duplicates are closed too** — see P3 and P4 below, done in the commit
beneath this one. The cross-stream cleanup is finished and E1 can start.

**▸ P3 — One signal vocabulary. DONE.** `SignalType` survives and
`signal_code.py` is gone. Stream A's naming won because the Signal Taxonomy
sheet's own column header is "Signal type", and because theirs was already
wired into persistence (`signals.type`), the L4 response DTO and the L4
prompt. Stream B's owner-team map and severity ordering were carried across:
the sheet calls owner mandatory because it drives routing, and nothing else
held it.

**▸ P4 — One repeat-contact derivation. DONE.**
`domain/aggregation/repeat_contact.py` survives;
`domain/derivations/repeat_contact.py` is gone. The two agreed on every rule
that matters — the 14-day window, that same-category is deliberately *not* a
condition, and the excluded exposure period — and Stream A's had no
production caller. Two things were salvaged from it: the warning that this
must never read the tracker's "Repeat of" column, because that is answer-key
material and using it would have Phase 5 measuring the agreement of a value
with itself; and its nine test cases, including the two a second
implementation would most likely get differently — that the fourteenth day
is inclusive, and that an *earlier* contact is not a repeat.

---

## 3. The tasks, in order

Each ▸ is one task and one commit, per the plan's convention.

### ▸ E1 — Field comparators · Medium · **DONE**

Pure functions, one per comparison kind, in `domain/evaluation/`. No I/O.

- **Exact** for enums and booleans: outcome, category, touchpoint,
  complaint presence, escalation's four fields, knowledge-failure presence,
  process-gap presence, broker-named presence and sentiment.
- **Set overlap** for lists: signals, control exceptions, intent types.
  Report precision and recall separately, never one blended F-score — a
  pipeline that finds half the signals and invents none is a different
  problem from one that finds them all and invents four, and the fix is
  different in each case.
- **Rule-id match** for knowledge failure.
- **Attribution target** for `complaint.attributed_to`. The Metrics sheet's
  own word for this dimension is **attribution target**, not "party". Keep
  that word: "party" is §7A's v10 fault-record vocabulary, which does not
  exist in v9, and using it here will have someone looking for a field that
  was never built.

**Agreement is reported three ways, never one.** Agreed, disagreed, and
*not comparable* — where one side has no value. Folding "not comparable"
into "disagreed" understates the pipeline on every field the tracker leaves
blank for most calls, which is most of them.

### ▸ E2 — Four traps in the field mapping · Small · **DONE**

Settle these before writing E1's mapping table, and write the conclusions
into the commit message. Each one produces a plausible number if got wrong.

1. **`rule_refs` is not `knowledge_failure_rule_ref`.** The tracker's
   `rule_refs` is every rule the call *cited*; the knowledge-failure rule id
   is the one the agent got *wrong*. Comparing them scores the pipeline
   against the wrong answer and will look like a catastrophic failure rate.
2. **`product_line` is singular in the tracker, plural in the schema.**
   Schema field 3 is an array and warns that shares over it exceed 100%;
   the Transcript Tracker column is one value. Decide whether the tracker's
   single value is compared against the pipeline's primary line or against
   membership in the set, and say which.
3. **`aht_seconds` is telephony, not extraction.** Schema field 12 is
   emitted by the phone system. There is nothing for the pipeline to get
   right, so it is not scored — it is a join key at most.
4. **`score` is not an independent measurement.** The rubric is
   deterministic given the markers, so score agreement is a *derived* view
   of marker agreement, not a second opinion about it. Report it, and label
   it as downstream of the markers rather than as evidence about them.

Check `archetype` too: if nothing in the pipeline produces it, it is
answer-key-only and belongs in neither column.

### ▸ E3 — Persist the run's token cost · Medium, not Small · **DONE**

§8 asks the diagnostics for "token cost of the last run", and **nothing
stores it.** `runs` carries status, provider, model and timings; `run_items`
carries status and error. Phase 3's adapters account for tokens and duration
per call, but the numbers are not written down.

**This was estimated Small and was not.** The numbers were not merely
unwritten — `StructuredResult` carries `usage`, and each layer *discarded*
it before returning, so there was nothing at the run boundary to write down.
It took threading usage from the adapters through the three layer results
and the pipeline result to the runner, plus `TokenUsage` moving into the
domain so a cost roll-up could reach it.

The roll-up is **computed from the items rather than stored on `runs`**,
against what this plan originally said. A stored total is a second copy of a
number, and a resumed run, a retried item or a backfill each give it a
chance to disagree with the items beneath it, with nothing to say which is
right. Summing a hundred rows is cheap.

A zero turned out to be three different things, and only one of them is
free: a cached stage (genuinely nothing, and we know it), a provider that
did not report (tokens spent, nobody counted — every total above it is a
**floor**), and nothing having run. `TokenUsage.reported` carries the
distinction through addition and `RunCost.summary` says "At least" when it
must.

### ▸ E4 — The evaluation use case and its CLI · Medium · **DONE**

`EvaluateExtraction` in `application/use_cases/`, plus a CLI beside the
other three. It loads the pipeline's output and the answer key for a run,
applies E1's comparators, and returns a report. It resolves nothing and
corrects nothing — like `ImportAnswerKey`, it reports disagreement and
stops.

Exit codes matter here, as they did for the answer-key CLI: a failure to run
and a run that scored badly are different conditions, and whatever runs this
in a pipeline needs to tell them apart.

**Label-leak containment.** The harness reads the answer key, so it belongs
firmly on the answer-key side of the import-linter contract "Extraction
cannot read the answer key". Add every module you write here to that
contract's **`forbidden_modules`** list in `pyproject.toml` — extraction
must not be able to import the harness, because the harness can reach the
answers. §6.3 calls label stripping the single most important safety
property in the system, and this is the phase that gives an extraction
module something new and dangerous to import.

### ▸ E5 — Diagnostics · Medium · **DONE**

Four views, all of which the plan names explicitly:

- **Agreement per field, and per layer.** Per layer is the one that tells
  you what to fix: L2 disagreeing is a classification prompt problem, L4
  disagreeing is a signal-taxonomy problem, and a per-field list alone does
  not separate them.
- **Rejected-evidence counts**, by `EvidenceRejection` reason —
  `missing_turn`, `quote_not_in_turn`, `empty_quote`. The Call Quality
  Framework treats these as a measurable property of the model rather than
  an invisible error in the score, so they are a headline, not a footnote.
  `unknown_dimension` did not exist and now does. Not reachable from a
  hallucination — `MarkerResponse.dimension` is a Literal of the six, so an
  invented name fails schema validation at the provider boundary — but
  reachable from **drift**: the rubric is data (`config/rubric.yaml`,
  versioned) and the Literal is code, so a rubric that drops or renames a
  dimension still admits it through the schema and then hits
  `Rubric.dimension()`, which raises and fails the whole L3 pass. L3 now
  filters unknown dimensions into a marker-level refusal, as the Call
  Quality Framework describes.
- **Unresolved callers.** Calls where `caller_ref` could not be resolved.
  These silently weaken repeat contact and first-contact resolution, since a
  call that cannot be linked to a caller can never be found to have a
  follow-up.
- **Token cost of the last run**, from E3.

### ▸ E6 — The numbers, written up for Minnie · Small · **STARTED — blocked on a run**

Not a formality and not a status update. It states, per field: agreement,
the sample it rests on, and a recommendation to build on it, build with a
caveat, or not build on it yet. §9's insight table is the checklist — every
BUILD insight depends on named fields, and this is where each one either
earns its place or does not.

**The checklist is built; the numbers are not.** `Phase-5-Findings.md` is
the check-in document, and everything in it that does not need a pipeline
run is written: what is already unscoreable and why, the two scored fields
no insight rests on, how to read an agreement figure, and the three
decisions the meeting has to take.

§9's checklist is now data rather than prose —
`domain/evaluation/insight_dependencies.py` maps each BUILD and PARTIAL
insight to the scored fields behind it, and the report prints what each
field *holds up*, so a weak field names its own blast radius instead of
being an abstract percentage. It carries no threshold: the bar is Minnie's.

**What is blocked.** The numbers need a completed extraction run over the
corpus — all 100 transcripts to a live provider, three layers each. That is
real spend and real member conversations leaving the building, so it is a
decision someone takes deliberately rather than a step in a script.

---

## 4. What this phase must not do

**No fault-record labelling tool.** §8 is explicit. There is nothing to
hand-label: D5 (whether the employer is a responsible party) is unanswered
and §7A's per-fault record is a v10 *proposal* rather than a built thing, so
D10 stays parked rather than scheduled here.

**No tuning to the answer key inside this phase.** Measuring and improving
in the same change means never knowing which of the two moved the number.
Fixes that the numbers justify are their own commits, after the check-in.

**No threshold for "good enough" invented here.** The harness reports; it
does not judge. What counts as acceptable agreement is Minnie's call, taken
with the numbers in front of her.

---

## 5. Definition of done

`./scripts/check.sh` from the repo root, green, before every commit. Never
commit past a failing gate and never weaken a gate to make it pass.

Two specific to this repo:

- **A skipped test is a failure.** The corpus is tracked in `Documents/`, so
  the corpus tests run everywhere by default. If a skip appears, treat it as
  red — that exact failure mode once hid the 100-call label-leak proof while
  the gate still printed "all gates passed".
- **The single-head check is a gate now, not a report.** It previously ran a
  bare `alembic heads`, which prints both heads and exits 0. The Stream A
  merge forked the chain exactly as it exists to catch, and was straightened
  before landing — expect the same on the next parallel branch.

### Met, for E1–E5 · verified 2026-09-24 at `a766612`

All three checked directly rather than inferred from the per-task runs,
which had been backend-only:

| | |
|---|---|
| `./scripts/check.sh`, repo root | `RESULT: all gates passed` — backend format, lint, strict types, the four import contracts, the single-head check, and the frontend gates including the typed-client no-diff check |
| Tests | 873 passed, **0 skipped**; 95.73% coverage against an 85% floor |
| Migration heads | 1 |

**This is the DoD for the work, not for the phase.** E6 is outstanding and
cannot be closed by a gate: it needs a real pipeline run over the corpus,
which needs a live provider, and then the numbers written up. Phase 5 ends
at the check-in with Minnie (§6), not here.

---

## 6. Where this ends

Phase 5 ends at the check-in, and the check-in releases two things that are
deliberately blocked on it:

- **B5**, the nine read endpoints, held because wiring endpoints to fields
  whose agreement nobody has measured is the rework this sequence exists to
  avoid.
- **Phase 8**, the screens.

**Phase 7, the frontend design system, is not blocked by any of this** and
can run in parallel from now — it needs no API at all.

Two open decisions should be settled at the same check-in, because both get
more expensive the moment endpoints serialise them:

- **`EpistemicClass`** — MEASURED / DERIVED / WITHHELD. The plan requires an
  epistemic class on every response and no source says what its values are;
  the workbook does not, and the prototype's `confidence` chip is the
  *rule's* grade, a different thing about a different object. Inferred, and
  now threaded through eleven modules.
- **`indicators.min_rate`** — 0.2, with no source at all. The prototype
  gates the indicator families on neither a floor nor a rate; plan §8 asks
  for both. The floor has a source; this does not.
