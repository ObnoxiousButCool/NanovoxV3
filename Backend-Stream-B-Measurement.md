# Backend Stream B — Evidence and measurement

One of two parallel backend streams taking NanoVox Insights from where it
stands today through Phase 6. Stream A is *Extraction pipeline*
(`Backend-Stream-A-Extraction-Pipeline.md`); the two are sized to touch
almost no common files. Read §3.0, §8 Phases 5–6 and §9 of `plan.md` before
starting — this document says who does what and in which order, not what the
metrics mean.

**You own:** the answer key, the thresholds, the aggregations and the read
endpoints — everything that turns extracted facts into a figure someone can
defend.

---

## 1. Where the code stands

Nothing in Phase 5 or 6 exists yet. `Code/Backend/config/` and
`domain/aggregation/` have not been created.

**The answer key is done** (B1, 2026-09-23). Both sides of it now exist: the
PDF's five-field `CALL TAGS` through `PdfAnswerKeySource`, and the workbook's
twenty-four-column Transcript Tracker through `XlsxGroundTruthSource` into
the `ground_truth` table. `ImportAnswerKey` reconciles the two and reports
disagreements rather than resolving them. Phase 5 now has something to score
against.

Phase 1's reference data is complete and verified against the real workbook:
95 employers, 30 brokers, 285 members, 101 contacts, 20 agents, 122 rules, 12
touchpoints, idempotent on re-import. `domain/reference_derivations.py`
already computes participation, fee band, annual fee and COBRA regime. Reuse
it rather than deriving those again.

---

## 2. Your tasks, in order

Each ▸ is one task and one commit, per the plan's convention.

### ▸ B1 — AnswerKeyImporter and `ground_truth` · Large · **DONE 2026-09-23**

Done. `ground_truth` (revision `20260923_0905`) holds all 24 tracker
columns; `ImportAnswerKey` reconciles them against the PDF and the CLI exits
2 when they disagree. The cross-check passes on the real corpus — all five
shared fields agree across all 100 calls. **B2 is the next task.**

Originally: do this first, because Phase 5 cannot start without it and
Phase 5 is the gate that releases Phase 8.

Read the workbook's **Transcript Tracker** sheet into a `ground_truth` table,
then cross-check it against the `CALL TAGS` block that `PdfAnswerKeySource`
recovers from the PDF, and **report any disagreement** rather than silently
preferring one source.

Two things to respect while you are in here:

- **The import-linter contract.** `pyproject.toml` declares "Extraction
  cannot read the answer key" as a *forbidden* contract — extraction modules
  structurally cannot import `answer_key_source`, `pdf_answer_key_source` or
  `domain/entities/answer_key.py`. Your importer is allowed to; nothing on
  Stream A's side ever is. Do not relax the contract to make something
  import, and do not put shared helpers where extraction can reach them.
- **Use the matched pair.** Workbook `_2` with PDF `_1`, no other pairing.
  The 17 Sep 2026 re-issue reassigned the caller on all 100 calls, and a
  tracker from one revision against transcripts from another misattributes
  every call *silently*, because either combination is internally
  consistent. `tests/integration/test_real_corpus_regression.py` guards this.

### ▸ B2 — `config/dashboard.yaml` · Medium · **DONE 2026-09-23**

Done. `config/dashboard.yaml` holds the thresholds, `domain/dashboard_config.py`
holds their shape and the decisions made from them (withheld, size band,
eligible/flagged/quotable, quality band), and
`infrastructure/config/dashboard_config.py` loads it strictly — an absent key
is an error, never a default. `settings.dashboard_config_path` points at it.

`tests/integration/test_dashboard_config_matches_workbook.py` reads the real
workbook and fails if any shipped value has drifted from the Metrics, Call
Quality Framework or Questions Worth Asking sheets, **including when a metric
is added to a sheet and not to the config**. That is what makes the file a
transcription rather than a second definition. **B3 is the next task.**

Two things found while transcribing, neither of which changes what B2 built:

- **The plan's §8 list is incomplete, as it says it is.** It names ten values;
  the sheet has fourteen rows. Missing from the plan: metric 11 (commercial
  intent capture, min n 10) and both base measures — call volume (no
  threshold) and AHT (4wk, 30). All fourteen are configured. Treat the sheet
  as the source, which is what §3.0 already says.
- **The Questions Worth Asking sheet is a scheduled capability nobody has
  scheduled.** Ten trigger rules with explicit thresholds, and the sheet
  closes by insisting they are configuration rather than code. Only rule 2
  (the broker pattern test) appears anywhere in the plan. The other nine are
  not in B2's scope and are not built; they need a decision about where they
  land before anyone writes them.

Originally: thresholds are configuration, read from the workbook, not
constants sprinkled through code.

**Minimum n is per metric, from the Metrics sheet — there is no global
number.** The plan's §8 Phase 6 lists the values: contact rate 30, complaint
rate 10 calls, FCR 30, failure-driven repeat 30, self-inflicted demand 60,
escalation integrity 30 triggers, control exceptions 30, knowledge failure
30, cost to serve 30, risk-flag eligibility 3 and quote 10. Take them from
the sheet and treat the plan as a cross-check, not the source.

Also: `cost_per_call: null` (D4 — money stays out), peer size bands (2–24,
25–74, 75–199, 200+ lives), broker ranking floor (150 lives), broker pattern
test (≥3 adverse mentions from ≥2 of that broker's employers), quality bands
(good ≥86, average ≥60).

Two of these have **no prototype counterpart** and are new build rather than
a port: there is no size-band or peer concept anywhere in the prototype, and
no 150-lives floor. The pattern test *is* implemented there — see
`Prototype/hierarchy.html` around the `trigger_broker_pattern` computation,
which also shows the "fired and unfired" presentation §9 insight 13 asks for.
Quality bands match exactly: `NV.QUALITY_BANDS` is GOOD ≥86, AVERAGE ≥60,
POOR below.

### ▸ B3 — `domain/aggregation/` pure functions · Large · **DONE 2026-09-23**

Done. All nine groups, plus the foundation they share: `CallTags` (the
sixteen schema fields), `Figure` (the result envelope), and `patterns.py` —
the Metrics sheet's own "four calculation patterns… rather than twenty-four
reports", three of which are aggregations and the fourth of which is B4's.

Insights 6, 17, 22 and 25 are withheld panels in `withheld.py`, each naming
what would unlock it. No partial versions. **B4 is the next task.**

Three things found while building, all of which affect someone else:

- **Metric 4's repeat linkage is in `repeat_contact.py`, not Stream A.**
  Stream A's A4 owns "repeat contact (metric 4)", but metric 5's first
  component is failure-driven repeats and B3 cannot publish self-inflicted
  demand without it. The two stream documents did not resolve that overlap.
  Stream A should import this rather than write a second 14-day window.
- **Metric 5's middle component is settled.** §9 insight 15 asked for it to
  be checked rather than assumed: "chasing an already-submitted action" is
  the `process_breakdown` signal, "a logged process defect" is
  `process_gap.present`. Two fields, not one. Stream A's A3 was asked the
  same question from the extraction side and the answers have to agree.
- **Insight 18 duplicates insight 16's residual bucket**, as §9 suspected. It
  is an accessor over the touchpoint ranking rather than its own panel.

**`EpistemicClass` needs Minnie.** MEASURED / DERIVED / WITHHELD, inferred —
the plan requires an epistemic class on every response and no source says
what its values are.

Originally: nine groups, all pure, all unit-testable without a database or a
model:

peer contact rate · isolation (region → broker → employer tree, region ×
category matrix, pattern test) · agent events (from the `knowledge_error`
signal) · rules (cited versus failed-to-explain, by rule layer P/A/C,
provenance, area — counts only, never a per-rule rate) · exec scorecard ·
self-inflicted demand, its three components **published separately, never
blended**, with the minutes view from metric 9 · broker book friction from
`broker_named_aloud` · touchpoint ranking coloured by
`complaint.attributed_to` · enrolment promise gap from `process_gap` plus
touchpoint.

**Insights 6, 17 and 25 render withheld panels — there is nothing to
aggregate for them.** Do not build a partial version to fill the space.

### ▸ B4 — Risk flag and indicator families · Medium

Metric 10 is a **yes/no flag, not a band** (D2). This is the largest
deliberate divergence from the prototype, which renders a four-level
High/Elevated/Watch/None band. The workbook wins on definitions.

Eligible at ≥3 calls for that employer in the window; flagged on ≥2 of the
four named conditions; quoted only at ≥10 calls. Never labelled a
prediction. At batch-1 volume most of the 92 employers have a single call, so
most are **ineligible rather than flagged-false** — the page has to say so.

Separately, port the ten indicator families from `NV.INDICATORS` in
`Prototype/app.js` (there are exactly ten). They render as "other conditions
observed", each firing above an absolute floor **and** a rate. They are
informational and **do not set the flag**.

**The churn profile is not an input.** `design_churn_profile` is the label
the corpus was generated from; scoring accounts on it would be circular.
`tests/unit/test_no_circular_scoring.py` fails if any aggregation reads it.

### ▸ B5 — Nine read endpoints · Large

`exec`, `risk`, `accounts/{ref}`, `hierarchy`, `demand`, `actions`, `rules`,
`agents`, `value-pack/{broker_ref}`, all under `/api/v1/insights/`.

Every endpoint takes the filter set plus `source`. Every response carries the
epistemic class, `n`, **the call ids behind each figure**, and withheld
reasons. Regenerate the typed client after each endpoint.

**Hold B5 until after the Phase 5 gate.** Wiring nine endpoints to fields
whose agreement nobody has measured is the rework risk this whole sequence
exists to avoid. B1–B4 can all land before it.

---

## 3. What you are not blocked by

**You do not need Stream A's code.** Write your aggregations against the Call
Tag Schema in the workbook — that is the authority both streams read — and
test them against fixtures derived from it. The schema defines the field
shapes; Stream A stores exactly what the schema says.

If Stream A has to deviate anywhere, they have been asked to tell you,
because you will have written against the schema's version.

`domain/aggregation/` is greenfield with no framework dependencies, and the
architecture contracts make it hard to get wrong: the domain layer may not
import FastAPI, SQLAlchemy, Alembic, Pydantic, httpx or uvicorn, and
`lint-imports` enforces it.

---

## 4. Rules that shape every figure you produce

These are the practices §9 lists as applying everywhere. They are not polish;
several of them are the reason a figure is defensible.

| Practice | What it means here |
|---|---|
| Epistemic class on every panel | A field in every response, not a UI decoration |
| Withheld ≠ zero | Suppress below min n and say why; zero reads as good news when it is actually absence |
| Every figure opens its evidence | Call ids in every response |
| Filters slice, never hide | The applied-filters row always shows scope and count |
| Computed caveats | Caveat text generated from the numbers, never hand-written |
| No circular scoring | Enforced by test — see B4 |

Two specific framings worth getting right the first time, because both were
settled deliberately:

- **Escalation integrity is handled ÷ triggered.** Never escalations ÷ all
  calls. Against all calls a rate of zero reads as good news; against
  warranted calls it reads as the control failure it is. Show both side by
  side, labelled — the prototype's `exec.html` already does.
- **Lives and revenue at risk is exposure, never expected loss.** There is no
  probability to apply to it.

---

## 5. Coordination rules

These three apply to both streams and exist because `scripts/check.sh` will
fail the second person to merge otherwise.

**Migrations — single head.** The gate enforces exactly one Alembic head —
as of 2026-09-23 it actually does. It previously ran a bare `alembic heads`,
which prints both heads and exits 0, so it reported rather than gated.
Your `ground_truth` table and Stream A's extraction storage are separate
revisions. Two branches each generating one produces two heads. Merge
migrations to `main` promptly and rebase before generating yours.

**`container.py` is shared.** B1 and B5 touch it, as do Stream A's A1 and A6.
Theirs lands first and small; keep yours additive and in separate methods.

**Generated API files.** `Code/Frontend/openapi.json` and
`src/shared/api/schema.ts` are regenerated by `npm run generate:api` and the
gate fails on any diff. B5 adds nine endpoints — regenerate **once per PR**,
not once per endpoint, or you will spend the week resolving conflicts in
generated files.

---

## 6. Definition of done

`./scripts/check.sh` from the repo root, green, before every commit. It runs
backend format, lint, strict types, the Clean Architecture import contracts,
tests with coverage, the single-migration-head check, and the frontend gates.
Never commit past a failing gate and never weaken a gate to make it pass.

**A skipped test is a failure.** The corpus lives in `Documents/` and is
tracked, so the three corpus tests run by default. They previously skipped
silently while the gate still printed "all gates passed" — which is exactly
the failure mode your `ground_truth` work exists to prevent elsewhere. If a
skip reappears, treat it as red.

---

## 7. Where this ends

Phase 5 is joint work with Stream A and is a deliberate check-in gate.

Build the per-field agreement comparison — exact match for enums, set overlap
for lists, rule-id match for knowledge failure, target match for complaint
attribution (the Metrics sheet's own term for that dimension is "attribution
target", not "party"; keep that word for it). Then the diagnostics view:
agreement per field and per layer, rejected-evidence counts, unresolved
callers, and the token cost of the last run.

There is **no fault-record labelling tool** and nothing to hand-label —
D5 is unanswered and §7A's v10 schema change is not built, so D10 stays
parked rather than scheduled.

Then both of you take the numbers to Minnie. Screens are built on pipeline
output, so a field with poor agreement means a screen that shows poor data.
Which fields are good enough is decided together, with the numbers in hand.
