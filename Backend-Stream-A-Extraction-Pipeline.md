# Backend Stream A — Extraction pipeline

One of two parallel backend streams taking NanoVox Insights from where it
stands today through Phase 6. Stream B is *Evidence and measurement*
(`Backend-Stream-B-Measurement.md`); the two are sized to touch almost no
common files. Read §7 and §8 Phase 4 of `plan.md` before starting — this
document says who does what and in which order, not what the layers mean.

**You own:** everything that turns a stored call into extracted facts — the
four extraction layers, the deterministic derivations, the pipeline that
sequences them, and the runner that executes it over a corpus.

---

## 1. Where the code stands

L1 and L2 are built, migrated and tested. They are **not composed in
`frameworks_drivers/container.py`**, so nothing can run them end to end yet.
That is the first thing you fix.

| Piece | File |
|---|---|
| L1 deterministic | `domain/extraction/l1_deterministic.py` |
| L1 evidence helpers | `domain/extraction/evidence.py` |
| L2 use case | `application/use_cases/classify_call_l2.py` |
| L2 response DTO | `application/dto/l2_response.py` |
| L2 prompt | `infrastructure/llm/prompts/l2_classification.md` |
| Storage | `call_extractions` table, revisions `20260923_0517`, `20260923_0520` |
| Repository | `infrastructure/persistence/repositories/call_extraction_repository.py` |

L2 is your size reference: roughly 1,190 lines across use case, DTO, prompt,
repository and tests, with a 423-line test file. Budget L3 and L4 similarly.

Phase 3's infrastructure is all present and working — provider registry,
versioned prompts, JSON-schema validation, retry policy, token and duration
accounting, and the stage-output cache. You should not need to build
anything at that layer; if you find yourself doing so, check whether the
thing already exists before adding a second one.

---

## 2. Your tasks, in order

Each ▸ is one task and one commit, per the plan's convention.

### ▸ A1 — Wire L1 and L2 into the container · Small

Do this first and keep it small. It is the only change that unblocks
everything else, and `container.py` is the one file both streams touch — the
earlier it lands, the less likely a later conflict.

Compose `L1Deterministic` and `ClassifyCallL2` in `build_container`, expose
them as builder methods on `Container` the way `ingest_transcripts()` and
`list_providers()` already are, and add nothing else while you are in there.

**Done when:** a use case can be obtained from the container and run against
an ingested call, and `scripts/check.sh` is green.

### ▸ A2 — L3 quality and knowledge · Large

Prompt file, JSON schema, domain value objects, persistence, validation, and
tests against recorded provider responses. **No live provider calls in
tests** — the existing adapter tests show the recording pattern.

`knowledge_failure` is stored **exactly as schema field 8 defines it** and is
never labelled an agent error. See §4 below: D7 is open and is not yours to
close in code.

### ▸ A3 — L4 signals and gaps · Large

Same shape as A2, including `process_gap`.

**One thing to settle before you write the mapping.** §9 insight 15 proposes
that `process_gap.present` alone covers self-inflicted demand's "calls caused
by a logged process defect" component. §8 explicitly says do not assume that
is final — check it against the Metrics sheet's build note for metric 5.
"Chasing an already-submitted action" and "a logged process defect" may need
two different conditions rather than one field. Whatever you conclude, write
it down in the commit message; Stream B's metric 5 aggregation depends on the
answer.

### ▸ A4 — Deterministic derivations · Medium

Repeat contact (metric 4), member effort, complexity. These are computed, not
extracted — no model involved.

Metric 4's definition is narrower than it looks: the numerator is UNRESOLVED
calls followed by a contact from the same caller within 14 days. **Same
category is not a workbook condition** and was deliberately dropped. The
denominator excludes the last 14 days of the window, because those calls have
no exposure period yet.

Effort and complexity are **our composites, not v9 fields**. They must be
labelled as derived wherever they surface. The prototype's
`Prototype/tools/README.md` documents the formulation it used; the workbook
has no field for either, and nothing stands in for one.

### ▸ A5 — Pipeline use case · Medium

Wires L1 → L2 → (L3 ∥ L4), with the essential-versus-degradable distinction
from `domain/layers.py`. That module already declares which layers each
metric needs and which are essential, and `tests/unit/test_layers.py`
enforces that the two stay consistent — read both before deciding what
"degradable" does at runtime.

### ▸ A6 — Run orchestration wiring · Medium

`infrastructure/runner/background_runner.py`, `domain/run_progress.py` and
`domain/value_objects/run_status.py` are built and tested, but
`BackgroundRunner` appears outside its own test file nowhere. Compose it,
give it a CLI and an endpoint, and surface progress, per-call status and
resumability.

This is Phase 3's last unfinished task and it lands here because it is what
executes A5.

---

## 3. What you are not blocked by, and what you must not block

**You do not need Stream B for anything in §2.** Their work reads the
workbook and builds aggregations; yours reads transcripts and writes
extractions.

**Stream B does not need your code, but they do need your field shapes.**
They write aggregations against the Call Tag Schema in the workbook, not
against your output. That works as long as you also store exactly what the
schema says. Any place you deviate — a renamed field, a collapsed enum, an
extra nullable — tell them, because they will have written against the
schema's version.

---

## 4. The one question you must not answer in code

**D7 is open with Karim.** The workbook contradicts itself on
`knowledge_failure`: call C-0001 is RESOLVED, scores 91, is archetyped
"Competent and resolved", and still carries `knowledge_failure`.

Store the field exactly as the schema defines it and roll it up by rule ID
and by touchpoint. Do not label it an agent error, and do not add a
correction, a heuristic, or a "probably meant" comment.

The genuine agent-conduct event is a **different signal** — `knowledge_error`,
"an agent stated a published rule incorrectly", MEDIUM, owner Knowledge
Management. The two are independent and can fire with or without each other.
If you find yourself reconciling them, stop and raise it.

---

## 5. Coordination rules

These three apply to both streams and exist because `scripts/check.sh` will
fail the second person to merge otherwise.

**Migrations — single head.** The gate enforces exactly one Alembic head.
Stream B adds a `ground_truth` table; you will add extraction storage. Two
branches each generating a revision produces two heads. Merge migrations to
`main` promptly and rebase before generating yours.

**`container.py` is shared.** A1, A6 and Stream B's B1/B5 all touch it. Land
A1 early and additively so later edits sit in separate methods.

**Generated API files.** `Code/Frontend/openapi.json` and
`src/shared/api/schema.ts` are regenerated by `npm run generate:api` and the
gate fails on any diff. A6 adds an endpoint, so regenerate once in that PR.

---

## 6. Definition of done

`./scripts/check.sh` from the repo root, green, before every commit. It runs
backend format, lint, strict types, the Clean Architecture import contracts,
tests with coverage, the single-migration-head check, and the frontend gates.
Never commit past a failing gate and never weaken a gate to make it pass.

Two things specific to this repo:

- **A skipped test is a failure.** The corpus lives in `Documents/` and is
  tracked, so the three corpus tests — including the 100-call label-leak
  proof — run by default. They previously skipped silently while the gate
  still printed "all gates passed". If a skip reappears, treat it as red.
- **The leak test is the one that matters most.** §6.3 calls label stripping
  the single most important safety property in the system and says every
  Phase 5 evaluation figure is worthless without it. The import-linter
  contract "Extraction cannot read the answer key" is structural, not
  advisory: **add every new extraction module you write to that contract's
  `source_modules` list in `pyproject.toml`.** That is how a leak into a
  prompt becomes a build failure rather than a code-review catch.

---

## 7. Where this ends

Phase 4 complete and Phase 3's runner wired. Then **stop**.

Phase 5, the evaluation harness, is joint work with Stream B and is a
deliberate check-in gate: it compares your pipeline's output against their
`ground_truth`, field by field, and the numbers go to Minnie before anyone
builds screens on them. A field with poor agreement means a screen that shows
poor data, so which fields are good enough is decided together, with the
numbers in hand — not assumed.
