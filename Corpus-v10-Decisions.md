# Corpus v10 decisions — consolidated

**Prepared:** 2026-09-25. Two independent analyses of the same bible
revision landed the same day — `Corpus-v10-Schema-Update.md` and
`Corpus-v6-Findings.md` — each raising open questions the other didn't.
This is one place to answer all of them, rather than two documents
drifting apart with half the picture each. Neither source document is
superseded; this only consolidates their **open** items. Read the linked
section for the full evidence behind any row.

**Already decided, not reopened here:**
- `preventable` is a pure function of `root_cause_owner` (CHOICE/SYSTEM →
  Yes, PROVIDER → No, rest → Partly), computed, never model-emitted. Both
  documents concluded this independently.
- The four new corpus files sit alongside the old ones (`Documents/`, old
  files in `Documents/superseded/`) — `Corpus-v10-Schema-Update.md` §9
  item 1.
- `root_cause_owner` is a deterministic derivation, not a new L4 model
  output — `Corpus-v10-Schema-Update.md` §9 item 4. Not yet built.
- Corpus ingestion reads every batch PDF in a directory rather than one
  hardcoded file — shipped, `Corpus-v10-Schema-Update.md` §12.

---

## RESPONSE REQUIRED

Following the convention already in use for `Phase-5-Findings.md` §9 and
`Revised-Implementation-Plan.md` §14: each item names a default that lets
mechanical work continue without stalling on silence, and says plainly
where no default is safe. Answering overrides the default at any point,
including after something built on it.

| # | Question | Owner | Default if unanswered | Answer |
|---|---|---|---|---|
| A | Does a **blameless** call still get a `root_cause_owner`? | Minnie | **No safe default.** This defines what "44% preventable by Choice" means and cannot be deferred into the prompt. | **Yes.** Built as the `MEMBER_MISUNDERSTANDING` fallback — every call gets an owner, blameless ones included. Decided 2026-09-27 under delegated build authority, not by Minnie; hers to override if she'd rather exclude blameless calls from the denominator. |
| B | Does `root_cause_owner` feed the risk flag, or stay informational? | Minnie | **Informational only**, the same ruling the ten indicator families carry (D12). | Followed the default — informational only. Not wired into any risk score; used only by insights 6/17 and by the evaluation harness. |
| C | Does `primary_issue` get a controlled vocabulary? | Ranjit | **Free text, not aggregated** — shown per call, not rolled up, until a vocabulary is defined. | Followed the default — plain string, compared case-insensitively, never aggregated. |
| D | Is `impact_scope`'s number captured, or only the bucket? | Ranjit | **Both** — the bucket as today's enum-shaped value, plus an optional count when the caller's words carry one ("eleven of my people"). | Followed the default — `ImpactScope` carries `bucket` + optional `count`. Ground truth keeps the tracker's own text raw rather than parsing it into the same shape (see `domain/value_objects/impact_scope.py`). |
| E | Is D5 formally closed? | Minnie, with Karim | **Proposed closed**, pending confirmation — `root_cause_owner`'s `EMPLOYER` value is what D5 asked for, but D10's "fault records" framing may not survive contact with four flat fields rather than a table. | **Still open.** Ranjit: please confirm with Karim whether the flat-fields framing satisfies D10, or whether the fault-records table is still wanted. |
| F | Does insight 25 count as partially addressed? | Minnie | **No** — stays WITHHELD. `MEMBER_MISUNDERSTANDING` is adjacent, not the `PLAN_AS_DESIGNED`/`MEMBER_COMPREHENSION` pair the insight specifies. | Followed the default — insight 25 stays in `WITHHELD_INSIGHTS`. |
| G | When does Phase 5's evaluation re-run? | Minnie | **A separate check-in**, after the four fields are built and every available batch is ingested — running now would only re-measure the same 100 calls. | **In progress, blocked on Ranjit.** The fields are built and merged; a full 200-call run was started 2026-09-27 and every call failed on `HTTP 401` — the `OPENAI_API_KEY` in `Code/Backend/.env` is being rejected, apparently since Ranjit last changed it. Ranjit: please provide a working key; the run resumes as soon as one lands. |

---

## Status — 2026-09-27

All four v10 fields are built, tested, and merged to `main` (PR 23457, on
top of PR 23449's corpus plumbing and the run-safety work in PR 23448).
Gate green twice over, independently re-verified both before and after
merge: import-linter (5 kept, 0 broken), ruff, mypy, full backend and
frontend test suites, migration heads.

**Shipped:**
- `root_cause_owner` / `preventable` — computed server-side in L4 from
  `complaint` + `signals`, never sent to the model
  (`domain/derivations/root_cause.py`).
- `primary_issue` / `secondary_issues` / `impact_scope` — extracted by L2,
  prompt bumped to `1.1.0`.
- Storage on both `call_extractions` and `ground_truth`, one migration
  (`20260927_0900_add_v10_schema_fields`).
- Answer-key parsing for the five new tracker columns, and evaluation
  comparators for all five new fields (`domain/evaluation/field_map.py`).
- Insights 6 and 17 moved off `WITHHELD_INSIGHTS` — the field they were
  missing now exists.

**Left — see the Answer column above for detail, repeated here as a
punch list:**
1. **E** — Ranjit to confirm with Karim whether D5/D10 are satisfied by
   four flat fields, or still want the fault-records table.
2. **G** — Ranjit to supply a working `OPENAI_API_KEY`; the 200-call
   Phase 5 re-run is built and ready, just blocked on this. Everything
   else needed for the run — the corpus, the pipeline, a local
   backend + frontend to view the results — is in place and tested.

## Full context per item

### A — Does a blameless call get an owner?

`root_cause_owner` closes a gap the sheet names directly: "a third of calls
carried no owner at all." It is populated on *every* call, and
`MEMBER_MISUNDERSTANDING` — nobody's fault, the member just wasn't told —
is 45% of the sample, the single largest bucket.

If a resolved, blameless call still carries an owner, "preventable by
Choice" is a share of *all* contact volume including calls nobody would
call a failure. If it doesn't, the field stops closing the gap it was
added for. This is the headline number the field exists to produce, so it
has to be answered before extraction, not discovered from whatever the
prompt happens to do.

*Source: `Corpus-v6-Findings.md` §4, D-a.*

### B — Does it feed the risk flag?

A per-call "Choice is at fault" is exactly the shape that grows into a
second scoring system alongside metric 10's flag — precisely what D12
spent a decision removing. Recommendation: informational only, matching
the ten indicator families' own treatment.

*Source: `Corpus-v6-Findings.md` §4, D-b.*

### C — Does `primary_issue` need a vocabulary?

It's the only categorical field in the twenty with no enum —
`{primary: string}` against closed vocabularies everywhere else.
Unconstrained, "missing ID card," "ID card not received" and "no card"
become three categories that never group. Either it gets a vocabulary, or
it's shown per call and never aggregated — building it as if it will
aggregate, then discovering it doesn't group, is the expensive order.

The sheet also warns it must not be conflated with commercial intent —
worth a specific test once this is built, since the two will look similar
to a model.

*Source: `Corpus-v6-Findings.md` §4, D-c. Ranjit's to decide; listed here
so Stream A knows which shape to build before starting.*

### D — Is `impact_scope`'s count captured?

The four allowed values mix a category (`1 member`, `1 group`) with an
unspecified N (`N employees`, `N members + dependents`). The sheet's own
example for why the field matters — "eleven of my people cannot find a
provider" — loses the eleven if only the bucket is stored.

*Source: `Corpus-v6-Findings.md` §4, D-d. Ranjit's to decide.*

### E — Is D5 formally closed?

`root_cause_owner` carries `EMPLOYER`, which is exactly the value D5 was
missing. But D10 — downstream of D5 — was framed around "fault records," a
party/role/fault_type/confidence table `plan.md` §7A proposed for a v10
schema change. What actually shipped is four flat fields, not a table.
Worth Karim confirming the framing survives before `plan.md` records
D5/D10 as closed on this basis.

*Source: `Corpus-v10-Schema-Update.md` §9 item 3.*

### F — Insight 25

Needs `PLAN_AS_DESIGNED` and `MEMBER_COMPREHENSION`; neither arrived.
`MEMBER_MISUNDERSTANDING` is adjacent in spirit but is one value of a
different field at a different grain. Recommend leaving it WITHHELD rather
than reinterpreting the insight to fit what shipped.

*Source: `Corpus-v10-Schema-Update.md` §9 item 5.*

### G — Re-running Phase 5

The four new fields and the two new batches both change the numbers a
re-run would produce. Running before either is ready re-measures a corpus
that's about to change again. Recommend treating it as its own check-in
once both land — same shape as the first one, not a continuation of it.

*Source: `Corpus-v10-Schema-Update.md` §9 item 6.*
