# Phase 5 — the check-in with Minnie

The agenda for the conversation Phase 5 exists to make possible, and the
record of what it decides. Screens are built on pipeline output, so a field
with poor agreement means a screen that shows poor data — confidently, with
a call-id drawer behind it. **Which fields are good enough is decided here,
together, with the numbers in hand.**

**Status: the numbers are in (run 1, 2026-09-24).** §2 has them, with a
recommendation per field and per insight for Minnie to accept or replace.
§9 lists every issue the run exposed, each with a proposed fix and the steps
to make it, **for Ranjit to decide on**. Nothing in §9 has been changed yet.

---

## 1. What is being decided

Three things, and only the first needs the numbers.

1. **Per field: build on it, build on it with a caveat, or do not build on
   it yet.** The harness applies no pass mark, deliberately — a harness that
   graded its own subject would be the last place to notice it had the bar
   wrong. The bar is Minnie's.
2. **`EpistemicClass`** — MEASURED / DERIVED / WITHHELD. The plan requires an
   epistemic class on every response and no source defines its values: not
   the workbook, not the prototype (whose `confidence` chip is the *rule's*
   VERIFIED/SECONDARY/UNVERIFIED grade, a different thing about a different
   object). Inferred, and now threaded through eleven modules. Cheap to
   change now, expensive once B5's endpoints serialise it.
3. **`indicators.min_rate`** — 0.2, with no source at all. The prototype
   gates the ten indicator families on neither a floor nor a rate;
   `plan.md` §8 asks for both. The floor has a source (the prototype's own
   five-call floor); this does not. It is the weakest number in
   `config/dashboard.yaml` and says so in the file.

---

## 2. The numbers

### Run 1

| | |
|---|---|
| Date | 2026-09-24 |
| Provider / model | OpenAI `gpt-4o-mini` |
| Calls | 100 of 100 completed, 0 failed, 0 skipped (about 9 minutes) |
| Tokens | 1,153,685 in, 48,265 out — every call reported usage, so this is a cost, not a floor |
| Coverage | 100 of 100 calls have an answer key; 0 unresolved callers |
| Evidence | 315 markers raised, 3% refused (9 × `quote_not_in_turn`) |
| Produced by | `python -m frameworks_drivers.cli.evaluate_extraction`, see §6 |

**By layer:** L1 95% over 200 comparisons · L2 68% over 628 · L3 38% over 208
· L4 19% over 221. The facts of a call (escalation, complaint, control
exceptions, outcome) are close to usable; the model's judgement calls
(signals, process gap, quality score, touchpoint) are not yet.

### Per field

**The recommendation column is a proposal, not a pass mark.** It applies
these provisional bars, which are Minnie's to accept or replace:

- **Build** — at least 90% agreement on at least 30 comparable calls.
- **Caveat** — 70–89%, or 90%+ on fewer than 30 comparable calls. Build,
  and label the panel.
- **Not yet** — under 70%, or a known defect in §9 makes the number
  unreliable in either direction.

Worst first, as the CLI prints them.

| Field | Layer | Agreement | Comparable / calls | Holds up | Recommendation | Decision (Minnie) |
|---|---|---|---|---|---|---|
| `broker_named_aloud.broker_ref` | L1 | — | 0 / 100 | 7, 10, 13 | **Not yet** — never resolved to a broker id (§9 F3) | |
| `score` | L3 | 0% | 100 / 100 | nothing | **Not yet** — systematically high (§9 F7). Derived from the markers, and gates no insight | |
| `touchpoint` | L2 | 0% | 100 / 100 | 10, 11, 16, 18, 23 | **Not yet** — invented labels, not Touchpoints-sheet references (§9 F1, F2) | |
| `signals` | L4 | 2% exact set; 18% precision, 68% recall | 100 / 100 | 15, 20, 21, 27, 28 | **Not yet** — over-emitted and duplicated (§9 F4, F5) | |
| `process_gap.present` | L4 | 22% | 100 / 100 | 11, 15, 20 | **Not yet** — present on 90 calls against 12 (§9 F6) | |
| `knowledge_failure.rule_id` | L3 | 38% | 8 / 100 | 23, 24 | **Not yet** — too few calls to judge (§9 F9) | |
| `intent` | L2 | 43% | 7 / 100 | 1, 3, 31, 32 | **Not yet** — too few calls to judge (§9 F9) | |
| `category` | L2 | 68% | 100 / 100 | 13, 27 | **Not yet** — just under the bar; nearest candidate for Caveat | |
| `escalation.trigger_type` | L4 | 70% | 10 / 100 | 5 | **Caveat** — thin sample | |
| `product_line` | L2 | 74% | 73 / 100 (27 with no pipeline value) | 32 | **Caveat** — empty on 27 calls (§9 F8) | |
| `knowledge_failure.present` | L3 | 75% | 100 / 100 | 23 | **Caveat** | |
| `outcome` | L2 | 78% | 100 / 100 | 1, 4, 15, 29, 30 | **Caveat** | |
| `complaint.attribution_target` | L2 | 84% | 37 / 100 | 1, 16 | **Caveat** | |
| `complaint.present` | L2 | 84% | 100 / 100 | 1, 16, 18, 30 | **Caveat** | |
| `escalation.requested_by_caller` | L2 | 91% | 11 / 100 | nothing | **Caveat** — thin sample; gates no insight | |
| `broker_named_aloud.present` | L1 | 94% | 100 / 100 | 10 | **Caveat** — the 94% is the absent calls; the pipeline found 0 of the 6 named brokers (§9 F10) | |
| `control_exceptions` | L1 | 96% | 100 / 100 | 19 | **Build** — two of three types; `missing_benefit_disclosure` not measured (§8 #1) | |
| `escalation.triggered` | L2 | 97% | 100 / 100 | 5, 29 | **Build** | |
| `escalation.handled` | L4 | 100% | 11 / 100 | 5 | **Caveat** — perfect, but on 11 calls | |

### Per insight — gated on its weakest field (§8 #6)

A higher bar applies where a figure names an account or a person: 1, 3, 7,
10, 13, 19 and 28.

| Insight | Screen | Weakest field | Recommendation | Decision (Minnie) |
|---|---|---|---|---|
| 19 Compliance exception exposure | /actions | `control_exceptions` 96% on 100 | **Build** | |
| 4 Failure-driven repeat contact | /accounts | `outcome` 78% on 100 | **Caveat** | |
| 5 Escalation integrity | /exec | `escalation.trigger_type` 70% on 10 | **Caveat** — triggered 97% and handled 100% are strong; the trigger-type breakdown is thin | |
| 29 Member effort and complexity | /agents | `outcome` 78% on 100 | **Caveat** — and labelled derived, as our composite | |
| 30 Quarterly value pack (partial) | /value-pack | `outcome` 78% on 100 | **Caveat** | |
| 1 Account risk flag | /risk | `intent` 43% on 7 | **Not yet** — names an account, and intent is too thin to judge | |
| 3 Authority-weighted exit language | /risk | `intent` 43% on 7 | **Not yet** | |
| 31 Commercial intent routing (partial) | /value-pack | `intent` 43% on 7 | **Not yet** | |
| 32 Ancillary attach opportunity | /value-pack | `intent` 43% on 7 | **Not yet** | |
| 7 Broker-of-record drift | /accounts | `broker_ref` — no comparison | **Not yet** — §9 F3 | |
| 10 Broker book friction, split by cause | /hierarchy | `broker_ref` — no comparison | **Not yet** — §9 F3 | |
| 13 Isolated or systemic | /hierarchy | `broker_ref` — no comparison | **Not yet** — §9 F3 | |
| 11 Enrolment promise gap (partial) | /demand | `touchpoint` 0% on 100 | **Not yet** — §9 F1 | |
| 16 Touchpoint defect ranking (partial) | /demand | `touchpoint` 0% on 100 | **Not yet** — §9 F1 | |
| 18 The unattributed bucket | /demand | `touchpoint` 0% on 100 | **Not yet** — §9 F1 | |
| 23 Rules we fail to explain | /rules | `touchpoint` 0% on 100 | **Not yet** — §9 F1 | |
| 24 Rule provenance and confidence | /rules | `knowledge_failure.rule_id` 38% on 8 | **Not yet** — thin | |
| 15 Self-inflicted demand, costed | /demand | `signals` 2% on 100 | **Not yet** — §9 F5, F6 | |
| 20 The action centre | /actions | `signals` 2% on 100 | **Not yet** — §9 F5, F6 | |
| 21 Where the work came from | /actions | `signals` 2% on 100 | **Not yet** — §9 F5 | |
| 27 Network adequacy clusters (partial) | /demand | `signals` 2% on 100 | **Not yet** — §9 F5 | |
| 28 Agent conduct against expected band | /agents | `signals` 2% on 100 | **Not yet** — names a person; §9 F5 | |
| 2, 8, 12, 14 | /accounts, /risk | reference data only | Unaffected by extraction agreement | |

**Most "Not yet" rows trace to a handful of fixable causes in §9, not to the
model being generally poor.** If Ranjit approves F1, F3, F4, F5 and F6, a
second run would re-test insights 7, 10, 11, 13, 15, 16, 18, 20, 21, 23, 27
and 28 before anyone decides against them.

---

## 3. What is already known, without a run

These do not depend on the numbers and will not change when they arrive.

### Three answer-key columns cannot be scored at all

| Column | Why |
|---|---|
| `rule_refs` | The rules a call *cited*. Nothing in the pipeline produces them — and this is **not** `knowledge_failure.rule_id`, which is the rule the agent got *wrong*. Comparing the two would score the pipeline against the wrong answer and read as catastrophic failure. |
| `archetype` | The tracker's own summary label. No layer produces one. |
| `aht_seconds` | Telephony, not extraction (schema field 12). There is nothing for the pipeline to get right. |

### `control_exceptions` is scored on two of its three types

Stream A closed the storage gap: L1's greeting check is now saved with each
call and scored as a set, so metric 7 can be measured at this check-in.

It covers `no_recording_disclosure` and `disclosure_before_verification`.
**`missing_benefit_disclosure` is not measured, by decision** (§8): metric 7
stays deterministic, and this type needs a model's judgement. It is left out
of the comparison and listed as unscored rather than counted as a miss. The
answer key carries it on none of the hundred calls.

### Two scored fields no insight rests on

`score` and `escalation.requested_by_caller`. Each is one of two things and
they need different answers:

- **`score` may be correct.** The prototype's agents screen is explicitly
  "events, not scores", and §9 insight 28 reads agent conduct from the
  `knowledge_error` signal rather than from metric 12. If no screen quotes a
  call score, its agreement gates nothing.
- **`escalation.requested_by_caller`** reaches the screens only through the
  `escalation_missed` signal ("an explicit escalation request went
  nowhere"), so it is scored but never read directly.

A field nobody depends on is either a field the screens do not need or an
insight nobody has mapped. Only Minnie can say which.

### The six WITHHELD insights are not in scope here

6, 9, 17, 22, 25 and 26 are withheld because a field does not exist, not
because it might score badly. No agreement figure unlocks them, and they
need the v10 schema conversation instead — §7A, and decisions D5 and D10.

---

## 4. How to read an agreement figure

Two things the report does that are worth knowing before anyone quotes a
number from it.

**Agreement never appears without coverage.** A field the pipeline answered
on four calls and got right four times reads as 100%, and it is — of four
calls out of a hundred. Both numbers are on every line, because 100% on four
and 100% on ninety-eight are the same number and different findings, and
whichever a reader assumes is the one that will mislead them.

**"Not comparable" is its own verdict.** Folding it into *disagreed* would
understate the pipeline on every field the tracker leaves blank, which is
most fields on most calls. Folding it into *agreed* is worse: a pipeline
that produced nothing at all would score 100%. So a missing value names
which side was missing — the tracker never recorded it, or the pipeline
never answered — and those have different owners.

---

## 5. Diagnostics to read alongside

Three things that make the agreement numbers weaker than they look, printed
by the same command:

- **Rejected evidence**, by reason and as a share of markers raised. A score
  built on markers that failed verification is not a score.
- **Unresolved callers.** Counted, never dropped — but they can never be
  linked to a follow-up, so they silently weaken repeat contact and
  first-contact resolution wherever they appear.
- **The last run's cost**, and whether it is a cost or a **floor**. Some
  providers do not report usage; the tokens were still spent.

---

## 6. Producing the numbers

From `Code/Backend`, with the three imports already run:

```bash
python -m frameworks_drivers.cli.evaluate_extraction
```

It needs a completed extraction run to score. That run sends all 100
transcripts to the configured provider, three layers per call — real money
and real member conversations leaving the building, so it is a decision
someone takes deliberately rather than a step in a script.

Exit codes: `0` scored something, `2` nothing was comparable (the pipeline
has not run — not a bad score, the absence of one), `1` the harness failed.

**Do not tune against these numbers in the same change that measures them.**
Measuring and improving together means never knowing which of the two moved
the figure. Fixes the numbers justify are their own commits, after this
conversation.

---

## 7. What this releases

- **B5**, the nine read endpoints, held precisely for this.
- **Phase 8**, the screens.

Phase 7, the frontend design system, is not blocked by any of it and can run
in parallel — it needs no API at all.

---

## 8. Decisions taken

*Each entry: what was decided, by whom, and the number it was decided on —
so that a later reader can tell a judgement from an assumption.*

Taken 2026-09-24 by Minnie, accepting the recommendations in
`Open-Decisions.md`. None rests on an agreement number; the run had not
happened.

| # | Decision | Owner of the work | State |
|---|---|---|---|
| 1 | **`missing_benefit_disclosure` is not produced.** Metric 7 stays deterministic: its build note ("no model judgement") is narrower and compliance-facing, and a model detector could not be validated here — the answer key carries the type on no call. | Stream A | Done — excluded from scoring and listed as unscored; `domain/layers.py` has metric 7 on L1 alone |
| 2 | **`EpistemicClass` is split.** `basis` (MEASURED / DERIVED) alongside the existing `published` flag and `withheld_reason`, so a withheld composite is still labelled a composite. | Stream B | To do, before B5's endpoints ship |
| 3 | **`indicators.min_rate` is dropped** unless someone can source it; the five-call floor stays. | Stream B | To do |
| 4 | **`score` and `escalation.requested_by_caller` are recorded, not fixed.** Both stay scored. No screen quotes a per-call score ("events, not scores"); `requested_by_caller` reaches the screens only through `escalation_missed`. | — | Recorded |
| 5 | **Value objects tightened** — `ProcessGap` requires `gap_type` and `proposed_change`; both raise `ValidationError`. `KnowledgeFailure.correct_statement` stays optional until D7 closes. | Stream A | Done (PR 23393) |
| 6 | **The pass mark's shape**, agreed before any number is seen: set per insight, not per field; a floor (do not build) and a band (build, labelled); coverage counts as much as agreement; a higher bar where a figure names an account or a person; an insight gates on its weakest field. | Minnie | Shape agreed; the bars themselves are set with the numbers |
| — | **The dashboard reads the stored control exceptions.** `insights_source.py` now reads `call_extractions.control_exceptions`, and still reports the field unavailable while any row in the slice predates the column (NULL is unknown, not zero). | Stream B | Done (PR 23398) |
| — | **Provider for the corpus run: OpenAI**, the D1 default. | Minnie | Done — run 1, 2026-09-24, `gpt-4o-mini` (§2) |

---

## 9. Issues found by run 1 — for Ranjit to decide

> **RESPONSE REQUIRED — Ranjit.** Every row below needs an answer in the
> *Ranjit's answer* column: **make**, **don't make** (with a reason), or
> **other** (say what). This is blocking: Stream A's extraction fixes wait
> on it, and `Revised-Implementation-Plan.md` R1 says the V2 screens lean on
> exactly these fields.
>
> **Default if unanswered.** Following the convention in
> `Revised-Implementation-Plan.md` §14, silence does not stop work: an item
> left blank proceeds on its default, and is recorded here as **taken by
> silence**, not as a decision anyone made. Answering overrides the default
> at any point, including after the fix has landed.

| Item | Summary | Owner | Default if unanswered | Ranjit's answer |
|---|---|---|---|---|
| F1 | Touchpoint chosen from the Touchpoints sheet | Stream A | Make, as recommended | |
| F2 | Read the tracker's "—" as no touchpoint | Stream B | Make, as recommended | |
| F3 | Resolve a named broker to its id — option (a) or (b) | Stream A | Make, option (b) | |
| F4 | One signal per type per call | Stream A | Make, as recommended | |
| F5 | Signal over-emission; is `process_gap_proposed` redundant with `process_gap`? | Stream A (the question is joint) | Make steps 2–4. Keep `process_gap_proposed` until the question is answered | |
| F6 | Tighten the process-gap definition; require a quoted turn | Stream A | Make, as recommended | |
| F7 | Quality score too high | Stream A | Make, after F1–F6 | |
| F8 | No product line on 27 calls | Stream A | Investigate, then fix if a pattern shows | |
| F9 | Thin samples treated as provisional | — | Record as provisional; no code | |
| F10 | Presence fields report precision and recall | Stream B | Make, as recommended | |
| F11 | CLI prints precision and recall for set fields | Stream B | Make, as recommended | |
| F12 | Leave derived fields out of "weakest field" | Stream B | Make, as recommended | |
| F13 | Run CLI flushes its progress lines | Stream A | Make, as recommended | |
| F14 | README note for local databases missing `ground_truth` | Both | Make, as recommended | |
| F15 | Prompt changes justified from workbook definitions, not tracker rows | Both | Adopt as a rule | |

A default only ever moves the owner's own code. Stream A will not change
Stream B's modules (F2, F10–F12) on a default — those wait for Ranjit either
way.

The full evidence, fix and steps for each item follow.

Every issue the run exposed, whether in the pipeline, the harness, the answer
key import or the process. **Nothing here has been changed.** Each needs a
decision: make the fix, do not make it, or do something else. Each fix, if
made, is its own commit, followed by a re-run of the evaluation (§6 — never
in the same change that measures).

Owner is whose code it is, not who must decide. Evidence comes from run 1's
stored output, the stage cache and the answer key.

**Cost of re-measuring.** A fix that changes a prompt changes its version, so
every call misses the stage cache and a re-run costs about what run 1 did
(~1.2M tokens). A fix that changes only code (F2, F3 option b, F4, F10–F12)
re-uses the cached model answers and can be re-measured for free.

### F1 — Touchpoint is invented, not chosen from the Touchpoints sheet

- **Owner:** Stream A (L2 and L4 prompts and use cases).
- **Evidence:** 0% agreement on 100 calls. The pipeline returns labels such as
  `enrollment`, `member_inquiry`, `billing_statement` and `call`; the tracker
  uses the sheet's references (`invoice_statement`, `denial_letter_eob`,
  `agent_conversation`, …). Neither prompt is given the 12 references, and
  nothing checks the answer against them. `process_gap.touchpoint` has the
  same problem but is not scored.
- **Proposed fix:** show L2 and L4 the Touchpoints sheet's references and
  accept only those.
- **Steps:**
  1. Add `list_touchpoints()` to the `ReferenceLookup` port and its SQL
     adapter (the `touchpoints` table is already imported), and read it in L2
     and L4 the way L3 and L4 already read rules.
  2. Render them into `l2_classification.md` and `l4_signals.md` (reference and
     one-line description), and bump both prompt versions.
  3. In `_to_domain` (L2) and the L4 validation, treat any value not in the
     list as no touchpoint, the same way an unknown broker or rule id is
     refused.
  4. Apply the same check to `process_gap.touchpoint`.
  5. Tests with a recorded response carrying an invented touchpoint, then
     re-run.
- **Recommendation:** make it. It blocks five insights, and it is a
  vocabulary gap rather than model judgement.
- **Decision (Ranjit):**

### F2 — The answer key stores the tracker's "—" as a touchpoint

- **Owner:** Stream B (`infrastructure/reference/xlsx_ground_truth_source.py`).
- **Evidence:** 19 `ground_truth` rows have touchpoint `—`. The importer
  already has `_NONE_MARKER = "—"` but does not apply it to this column, and
  `field_map._blank` only treats an empty string as blank. So 19 calls are
  compared against a literal dash. No other column is affected.
- **Proposed fix:** read `—` as no value for the touchpoint column.
- **Steps:**
  1. Apply `_NONE_MARKER` to the Touchpoint column in the importer.
  2. Add a test with a `—` cell.
  3. Re-import the answer key (idempotent) and re-evaluate. Code only, so
     free.
- **Expected effect:** touchpoint's comparable count falls from 100 to 81.
  It does not change the conclusion, since F1 is the larger cause.
- **Recommendation:** make it.
- **Decision (Ranjit):**

### F3 — A named broker is never resolved to a broker id

- **Owner:** Stream A (L2 prompt and `classify_call_l2.py`).
- **Evidence:** the tracker has a broker named on 6 calls; the pipeline
  resolved none. L1 spotted the right broker on 5 of the 6 (C-0008, C-0021,
  C-0064, C-0069, C-0090). The model also noticed a broker on 8 calls, but
  answered `broker_ref` with an empty string (6) or the person's name (2),
  never a `BRK-xx` id. The L2 prompt asks for the id but is only ever given
  the transcript, never the broker list. Validation then correctly refused
  every answer.
- **Proposed fix, two options:**
  - **(a)** Render the broker list (reference and name) into the L2 prompt.
    Costs tokens on every call, and bumps the prompt version.
  - **(b)** When the model says a broker was named and L1 has exactly one
    candidate, take the id from L1; the model supplies only the sentiment.
    Deterministic, costs nothing, and re-uses the cached answers.
- **Steps for (b):**
  1. In `_validate_broker_mention` (`classify_call_l2.py`), when `present` is true and
     `broker_ref` is empty or is a name, fall back to L1's single candidate.
     Refuse when L1 has zero or several candidates.
  2. Tests for zero, one and two candidates.
  3. Re-run; free.
- **Separate question for the answer key:** on C-0092 the caller describes a
  broker-of-record change to an unknown agency and never says a broker's
  name, yet the tracker records BRK-03 as named aloud. Worth checking whether
  the tracker is right before counting it against the pipeline.
- **Recommendation:** make it, with option (b).
- **Decision (Ranjit):**

### F4 — The same signal is stored more than once on a call

- **Owner:** Stream A (L4 validation and persistence).
- **Evidence:** 237 signal rows, 21 of them duplicates across 10 calls
  (C-0005 has `member_communication_gap` five times). The Data Model sheet
  says signal density counts *distinct types*, not occurrences.
- **Proposed fix:** keep one signal per type per call.
- **Steps:**
  1. In the L4 validation, keep the first accepted quote per signal type.
  2. Consider a unique constraint on `signals (call_id, type)`, with a
     migration.
  3. Tests, then re-run; free.
- **Recommendation:** make it.
- **Decision (Ranjit):**

### F5 — Signals are heavily over-emitted

- **Owner:** Stream A (L4 prompt), plus a vocabulary question for both
  streams.
- **Evidence:** 18% precision, 68% recall (38 matched, 178 spurious, 18
  missed). Two types account for most of the false ones:
  `member_communication_gap` (11 matched, 69 spurious) and
  `process_gap_proposed` (0 matched, 55 spurious). **The tracker never uses
  `process_gap_proposed` on any of the 100 calls.**
- **Question first:** is `process_gap_proposed` a signal the tracker
  represents through the `process_gap` field instead? If so, it should not be
  asked of the model separately.
- **Proposed fix:**
  1. Settle the question above. If it is redundant, derive it from
     `process_gap.present` rather than asking for it, or drop it from the L4
     signal list.
  2. Tighten `member_communication_gap` in `l4_signals.md` to the Signal
     Taxonomy sheet's own definition, with what does not count.
  3. Consider requiring every signal's quote to pass evidence checking, as
     markers already do, so a signal without a genuine supporting turn is
     refused.
  4. Bump the prompt version; tests; re-run.
- **Caution:** write the tightening from the workbook's definitions, not from
  the tracker's rows, or the next run measures how well the prompt was fitted
  to the answer key (see F15).
- **Recommendation:** make it. Five insights depend on signals.
- **Decision (Ranjit):**

### F6 — A process gap is reported on almost every call

- **Owner:** Stream A (L4 prompt).
- **Evidence:** present on 90 of 100 calls against 12 in the tracker (78 false
  presences, 0 missed). The prompt accepts a gap "proposed or clearly
  implied", which the model reads as any complaint.
- **Proposed fix:** tighten the definition to the Call Tag Schema's field 15
  ("a structural improvement proposed or implied inside a call… distinct
  from process_breakdown") and require a quoted turn as evidence.
- **Steps:**
  1. Rewrite the `process_gap` section of `l4_signals.md` with the sheet's
     definition and the process_breakdown distinction spelled out.
  2. Add a quote and turn to the process-gap response, checked like other
     evidence; refuse a gap whose quote is not in the transcript.
  3. Bump the prompt version; tests; re-run.
- **Recommendation:** make it. Insights 11, 15 and 20 depend on it.
- **Decision (Ranjit):**

### F7 — The quality score is systematically too high

- **Owner:** Stream A (L3 prompt); the rubric arithmetic is not at fault.
- **Evidence:** pipeline mean 95 against the tracker's 73; 71 calls score a
  perfect 100 (the tracker has 5 at 90 or above). The median gap is 20
  points, and only 6 calls are within 10. The model raised 250 positive and
  56 negative accepted markers. The rubric starts at 100 and only negative
  markers subtract, so the model is under-reporting shortfalls.
- **Proposed fix:** have L3 assess every one of the six dimensions for
  shortfalls explicitly, rather than listing what went well.
- **Steps:**
  1. Compare `l3_quality.md` with the NanoVox marker prompt it was ported from
     ("port unchanged", plan §7) and restore anything lost.
  2. Ask for at least one assessment per dimension, and allow "none found"
     explicitly so the model is not pushed into inventing a negative.
  3. Bump the prompt version; tests; re-run.
- **Priority:** lower. §8 #4 records that no screen quotes a per-call score,
  and it gates no insight. But metric 12 is published, so it should not stay
  inflated.
- **Recommendation:** make it after F1–F6.
- **Decision (Ranjit):**

### F8 — No product line on 27 calls

- **Owner:** Stream A (L2 prompt).
- **Evidence:** the pipeline returned no product line on 27 calls; the
  tracker names one on every call. Where the pipeline did answer, it agreed
  74% of the time.
- **Proposed fix:** ask for at least one line whenever the call concerns a
  product, and look at the 27 empty calls for a pattern (for example, billing
  calls where the line is implied rather than named).
- **Steps:** review the 27 calls; adjust the product-line instruction in
  `l2_classification.md`; bump the version; re-run.
- **Recommendation:** investigate first; fix if a pattern shows.
- **Decision (Ranjit):**

### F9 — Several fields rest on too few calls to judge

- **Owner:** none; a limit of batch 1.
- **Evidence:** `intent` 7 comparable calls, `knowledge_failure.rule_id` 8,
  `escalation.trigger_type` 10, `escalation.handled` and
  `escalation.requested_by_caller` 11 each. The answer key has these on few
  calls, so no fix raises the count.
- **Proposed approach:** treat these as provisional until batch 2 is scored,
  rather than tuning on seven calls.
- **Recommendation:** no code change. Record as provisional.
- **Decision (Ranjit):**

### F10 — A presence field's agreement hides what matters on rare positives

- **Owner:** Stream B (evaluation harness).
- **Evidence:** `broker_named_aloud.present` reads 94%, because 94 calls have
  no broker and the pipeline said no broker on all 100. It found 0 of the 6
  that did. The same shape affects every rare presence field.
- **Proposed fix:** for presence fields, also report how many of the
  answer key's positives were found (recall) and how many of the pipeline's
  positives were right (precision).
- **Steps:** add both to the per-field report and the CLI output; tests.
  Code only.
- **Recommendation:** make it. Without it a presence field can look strong
  while missing every case that matters.
- **Decision (Ranjit):**

### F11 — The CLI prints only exact-set agreement for set fields

- **Owner:** Stream B (`frameworks_drivers/cli/evaluate_extraction.py`).
- **Evidence:** `signals` prints as 2%, which only says that almost no call's
  set matched exactly. `SetComparison` already computes precision and recall
  (18% and 68% here), and E1's own rule is to report the two separately.
- **Proposed fix:** print micro precision and recall for `signals` and
  `control_exceptions` alongside the exact-set figure.
- **Recommendation:** make it.
- **Decision (Ranjit):**

### F12 — L3's "weakest field" is the derived score

- **Owner:** Stream B (evaluation harness).
- **Evidence:** the report names `score` as L3's weakest field, although
  `field_map` flags it `derived` — downstream of the markers, not a separate
  measurement. That sends the reader to the score instead of to the markers
  or `knowledge_failure`.
- **Proposed fix:** leave derived fields out when naming a layer's weakest
  field, or name them separately.
- **Recommendation:** make it; small.
- **Decision (Ranjit):**

### F13 — The run CLI shows no progress when its output goes to a file

- **Owner:** Stream A (`frameworks_drivers/cli/run_extraction.py`).
- **Evidence:** during run 1 the log stayed empty until the process ended,
  because output is buffered when redirected. Progress was only visible in
  the database.
- **Proposed fix:** flush after each progress line.
- **Recommendation:** make it; one line.
- **Status:** made by Stream A ahead of an answer (Minnie's call — it is
  Stream A's own CLI and changes no output). Say "don't make" and it is
  reverted.
- **Decision (Ranjit):**

### F14 — Local databases from before the stream merge have no `ground_truth` table

- **Owner:** both streams (setup documentation).
- **Evidence:** the merge placed the `ground_truth` migration ahead of Stream
  A's migrations. A local database that had already applied Stream A's
  migrations is past that point, so `alembic upgrade head` never creates
  `ground_truth`, and the evaluation has no answer key. Run 1's database was
  rebuilt for this reason (the old file is kept as
  `data/db/nanovox_insights.db.bak`).
- **Proposed fix:** a short note in the README's setup section: if
  `ground_truth` is missing, move the database aside, run
  `alembic upgrade head`, then the three imports.
- **Recommendation:** add the note.
- **Decision (Ranjit):**

### F15 — The calls that measure the fixes are the calls that showed the problems

- **Owner:** process, both streams.
- **Evidence:** batch 1 is the only answer key. Any prompt change judged on
  the same 100 calls risks fitting the prompt to them, so a second run
  scoring better would not prove the pipeline improved.
- **Proposed approach:** justify every prompt change from the workbook's
  definitions, not from individual tracker rows. Record in each fix's commit
  which definition it follows. Treat any run-2 gain as provisional until
  batch 2 is scored.
- **Recommendation:** adopt as a rule for F1, F5, F6, F7 and F8.
- **Decision (Ranjit):**
