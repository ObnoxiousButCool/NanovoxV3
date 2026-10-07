# Corpus v10 schema update — what changed, what it unlocks, what needs a decision

**Prepared:** 2026-09-25 · **Trigger:** Karim delivered a revised build bible
(`nanovox_corpus_v9_build_bible_6.xlsx`) and three transcript PDFs
(`batch1_rev2` 001–100, `batch2a_rev2` 101–150, `batch3` 151–200) to
`C:\Users\ShlokaKulkarni\Downloads\updateddocs`.
**Status:** §10 step 1 ("corpus plumbing") is done — see §12. Steps 2–4 (the
four new fields, end to end, and a second evaluation run) are still ahead
and still gated on §9's decisions. More batches are still coming: the
workbook's own control totals target 600 calls; we have 200.

**Governing documents unchanged:** the v9 workbook still wins on definitions
(`plan.md` §3.0). This update *is* a workbook revision, so where it speaks,
it settles things previous versions left open — most importantly D5.

---

## 1. Executive summary

**The v10 schema has arrived, and it answers D5.** The Call Tag Schema grew
from 16 fields to 20. The four new ones — `root_cause_owner`, `preventable`,
`primary_issue`/`secondary_issues`, `impact_scope` — are exactly the "v10
schema change" that `plan.md` §7A, D5 and D10 have been waiting on since
Phase 1. `root_cause_owner` carries an `EMPLOYER` value, which is precisely
what insight 6 was withheld for lack of. Insight 17 is very likely unblocked
too. This is real, working-through-the-decisions material, not aspirational.

**A real parsing bug would corrupt the new batches if ingested as-is.**
`infrastructure/corpus/pdf_text.py`'s page-furniture regex is hardcoded to
one exact footer string from batch 1's first issue. Each new PDF uses a
different footer format, so today's code would leave PDF page-number
furniture glued onto 134 of the ~1,700 dialogue turns in `batch1_rev2`
alone. Found, root-caused, and a fix verified against all four documents —
see §4. Not applied yet, pending your go-ahead (§9, item 1).

**The corpus is growing past what several places assume is fixed.**
`transcripts_path` and `workbook_path` are single-`Path` settings; the
`TranscriptSource` port takes one path. Five tests assert exactly 100 calls,
including the 100-call label-leak proof by name. None of this is wrong
today — it's wrong the moment we point at more than one PDF, which we now
need to.

**Everything we already built still stands.** Every sheet that defines a
metric, a signal, a rule, an escalation type or a touchpoint is
**semantically identical** to the version we built against — verified
cell-by-cell, not just by row count. Batch 1's answers for all 16 original
fields are **byte-identical** between the old PDF and `batch1_rev2`; the
revision only appended the five new tag lines. Our own derived reference
fields (`participation`, `fee_band`, `cobra_regime`, `annual_premium`,
`calls_per_100`) now have a real check: the new workbook populates the same
cells with its own computed values, and **all 95 employers match ours
exactly.** Nothing here says "go back and fix Phase 1–3."

**Recommended shape:** treat this as an interlude, not a new phase number —
a short, decision-gated task list that both streams pick up pieces of,
sized like the Open-Decisions.md / D14 exchanges already in this repo, not
like a new multi-week phase.

---

## 2. What arrived

| File | What it is | Calls |
|---|---|---|
| `nanovox_corpus_v9_build_bible_6.xlsx` | Revised build bible. We're on `_2`. | — |
| `nanovox_v9_transcripts_batch1_rev2_001-100.pdf` | Batch 1, reissued | C-0001–C-0100 |
| `nanovox_v9_transcripts_batch2a_rev2_101-150.pdf` | New batch | C-0101–C-0150 |
| `nanovox_v9_transcripts_batch3_151-200.pdf` | New batch | C-0151–C-0200 |

The workbook's own README states the target plainly: **"600 calls · 12
weeks · 95 employers · 122 verified rules."** We now have 200 of 600. The
Batch Coverage sheet already carries a "batch 2 brief" of what's
under-produced (compliance exceptions, escalation refusals, broker mentions,
commercial intent) — more batches are coming, and each will likely arrive
with its own footer-format quirk, per §4.

---

## 3. The v10 schema: four new fields, and what each is

The Call Tag Schema sheet went from 16 rows to 20 (row 0's own title now
reads "Call tag schema — 20 fields"). All four are marked "NEW" and none of
the original 16 changed — same tag, same type, same allowed values, same
notes, verified line by line.

| # | Field | Type | Values | Emitted by | What it is |
|---|---|---|---|---|---|
| 17 | `root_cause_owner` | enum | `CHOICE · BROKER · CARRIER · PROVIDER · EMPLOYER · SYSTEM · MEMBER_MISUNDERSTANDING` | L4 | Who could have prevented this call. Populated on **every** call, not only where a complaint exists — the sheet calls this closing a real gap, "a third of calls carried no owner at all." "Derived from complaint attribution first, then the dominant signal's owner." |
| 18 | `preventable` | enum | `Yes · Partly · No` | L4 | Pure function of `root_cause_owner`: CHOICE and SYSTEM → Yes, PROVIDER → No, the rest → Partly (with the lever named). Report the three buckets separately — "a blended percentage invites an argument about the middle." |
| 19 | `primary_issue` / `secondary_issues` | object | `{primary: string, secondary: [string]}` | L2 | What the call is fundamentally about, versus everything else raised in it. Explicitly **not** the same axis as `category` or commercial `intent` — a call can be primarily about a denial and secondarily about a card and a dependent. |
| 20 | `impact_scope` | string | `1 member · 1 group · N employees · N members + dependents` | L2 | How many people the caller says are affected — what turns "one member confused" into "eleven of my people can't find a provider." |

**Sample values, from `batch1_rev2`'s own CALL TAGS block for C-0001** (a
RESOLVED, score-91 claims call): `root_cause_owner CHOICE` ·
`preventable Yes` · `primary_issue claims & eob` · `secondary_issues none` ·
`impact_scope 1 member`.

Three new sheets back these fields:

- **Root Cause** — the distribution across the 150 calls it was computed
  against: `MEMBER_MISUNDERSTANDING` 45%, `CHOICE` 43%, the rest single
  digits. Headline: **"44% of contact volume traces to a root cause Choice
  owns outright."**
- **Coverage Matrix** — outcome × fault-type combination coverage (the
  corpus is judged on *which combinations exist*, not call count alone),
  plus a "closed / open / thin" tracker for cross-cutting targets
  (multi-intent calls, source contradictions, carrier variation, repeat
  journeys).
- **Account Risk Design** — see §6.

Both Root Cause and Coverage Matrix say "counted from the 150 written
calls" — they're a snapshot from before batch 3 landed and are stale by 50
calls' worth. The per-call Transcript Tracker data (200 rows) is
authoritative; the summary sheets' percentages are approximately, not
exactly, current.

### What this settles

| Item | Before | Now |
|---|---|---|
| **D5** — "Employer as a responsible party. STILL OPEN." | No value existed for "the employer caused this" anywhere in the schema. | `root_cause_owner` has `EMPLOYER`. This is the v10 schema change D5 was waiting on. |
| **Insight 6** — Employer-caused member confusion. WITHHELD: *"No EMPLOYER value exists anywhere in `complaint.attributed_to`, and none is proposed short of the v10 schema change."* | Withheld, no path forward. | Unblocked. Field exists, is populated on every call (not just complaint calls), and the value distribution shows it fires (1% of the 150-call sample; expect more at 600). |
| **Insight 17** — Proximate vs root cause. WITHHELD: *"one touchpoint and one complaint target per call today, no second (root) record."* | Withheld, "this *is* the v10 schema change." | Very likely unblocked. `root_cause_owner` is the second, root-level record the insight was missing, distinct from `touchpoint` (where it surfaced) and `complaint.attributed_to` (who the caller blamed). |
| **D10** — Attribution release gate, downstream of D5. | Parked, "nothing to gate." | D5 closing reopens D10, but D10 was framed around "fault records" (§7A's v10 *proposal*), and this schema doesn't build a fault-record table — it builds four flat fields. Whether D10 as originally framed still applies, or needs restating around `root_cause_owner`/`preventable` directly, is worth a line to Karim rather than assuming. |
| **Insight 25** — Plan-design confusion index. WITHHELD: needs `PLAN_AS_DESIGNED` and `MEMBER_COMPREHENSION`. | No path. | Still no exact match — `MEMBER_MISUNDERSTANDING` is adjacent in spirit but is one value of a different field, not the same pair the insight specifies. Recommend leaving WITHHELD rather than reinterpreting the insight to fit what arrived. |
| **C8a** — `archetype`, not a schema field. | Dropped, no source. | Unchanged. `archetype` is still tracker-only descriptive text (the Distribution Targets sheet lists its five values), not one of the 20 schema fields the pipeline emits. D14's decision to drop it stands. |

### The open design question this raises

`root_cause_owner` is marked "Emitted by: L4" — the same column used for
signals, `escalation.handled` and `process_gap`, all genuine model
judgements. But the sheet's own note gives an **algorithm**: *"Derived from
complaint attribution first, then the dominant signal's owner."* That reads
like a deterministic rule over fields we already extract
(`complaint.attributed_to`, `signals` with their taxonomy owners), in the
same shape as metric 4's repeat-contact or member-effort-complexity —
**"computed, not extracted."**

`preventable` is unambiguous: it's a pure enum mapping off
`root_cause_owner`, with no judgement involved. That one should be a
deterministic derivation regardless of how `root_cause_owner` is decided.

**This needs a decision, not an assumption** — it changes whether we write
an L4 prompt addition or a `domain/aggregation`-style pure function, and it
changes whether the field can ever disagree with the complaint/signal fields
it's built from (a deterministic derivation can't; a second LLM judgement
could). See §9, item 4.

`primary_issue`/`secondary_issues` and `impact_scope` are both "Emitted by:
L2" with no algorithm given — these read as genuine new model outputs,
the same shape as `category` and `intent` are today.

---

## 4. A parsing bug, found and fixed (not yet applied)

`infrastructure/corpus/pdf_text.py` strips running page furniture with:

```python
_PAGE_FURNITURE = re.compile(r"NanoVox — Corpus v9 · transcripts batch 1\n\d+\n?")
```

This is an exact, hardcoded match for batch 1's *original* footer. Every
document since has a different one:

| Document | Footer text |
|---|---|
| `batch1` (tracked today) | `NanoVox — Corpus v9 · transcripts batch 1` |
| `batch1_rev2` | `NanoVox — Corpus v9 · transcripts batch 1 rev-2` |
| `batch2a_rev2` | `NanoVox — Corpus v9 · transcripts batch 2a` |
| `batch3` | `NanoVox — Corpus v9 · batch 3 (C-0151 to C-0200 of 600)` |

None of these match the hardcoded regex. Worse, in `batch1_rev2`, most
pages render the footer and the page number **on the same line** with no
intervening newline (`...batch 1 rev-2 2`), which the current pattern
(expecting `\n\d+`) never catches either way.

**Verified impact.** Parsing `batch1_rev2` with today's code leaks page
furniture into **134 of 1,713 dialogue turns** (a caller's or agent's last
line before a page break gets `NanoVox — Corpus v9 · transcripts batch 1
rev-2 7` appended to it). That's furniture text landing inside what would
be sent to an LLM as the transcript — not an answer-key leak (§6.3's
concern is different and unaffected), but a real transcript-quality defect
that would silently degrade every extraction over the new batches.

**The bible itself confirms nothing else changed**: batch 1's cover page
states *"Dialogue unchanged from the first issue. Five tags are new in this
revision."* I verified this independently — with a fix applied, every one
of `batch1_rev2`'s 100 calls parses to **byte-identical dialogue** against
the currently-tracked PDF. The apparent "134 calls differ" from a naive
text diff is entirely this footer artifact, not a real content change.

**Fix, verified against all four documents (zero residual furniture, zero
unresolved calls, zero missing calls):**

```python
_PAGE_FURNITURE = re.compile(r"^NanoVox — Corpus v9 ·.*$\n?(?:^\d+$\n?)?", re.MULTILINE)
```

Line-anchored rather than content-anchored: it removes any line starting
with the constant `"NanoVox — Corpus v9 ·"` prefix, plus a following
page-number-only line if there is a separate one — so it survives whatever
batch label, revision suffix or parenthetical range each new PDF's
generator decides to print, including future batches. Tested against
`batch1` (old), `batch1_rev2`, `batch2a_rev2` and `batch3`: zero residual
`"NanoVox"` text in any of them afterward, and the one-line cover-page
title (a different string, `"...Transcripts, batch N ..."`, capital T) is
already excluded from every call block by the existing block-splitting
logic, so it needs no special handling.

**Applied**, in §12's PR, once §9 item 1 was answered.

---

## 5. Reference data: enriched, and independently validated

Several sheets show most or all rows "differing" between old and new. Cell
by cell, this is **not** new entities or reassigned data — it's
previously-blank computed columns getting populated, plus five genuinely
new columns on Employer Master:

- **Employer Master** gained `Dental carrier`, `Vision carrier`, `Life
  carrier`, `Chiro carrier`, `Ortho available` — real new reference data,
  currently read by nothing (our `Employer` entity and
  `XlsxReferenceSource` resolve columns by name, so this is additive and
  non-breaking; nothing is unread that used to be read).
- **`Participation`, `Fee band`, `COBRA regime`, `Calls per 100 lives`,
  `Annual premium ($)`, `Threshold status`, `Tier`** are now populated with
  real values, where the old workbook left them as blank formula cells —
  which is exactly why `domain/reference_derivations.py` exists: our own
  code computes these from `Eligible employees` / `Enrolled lives` /
  `Planned calls` rather than trusting an empty cell.

**I checked our derivation against Karim's now-authoritative numbers for
every one of the 95 employers: zero mismatches, across all five derived
fields** (`participation`, `fee_band`, `cobra_regime`, `annual_premium`
using the workbook's own `$486`/enrolled-life lever, `calls_per_100`). This
is a genuine, independent validation of `reference_derivations.py` that we
didn't have before — nothing needs to change here, and it's worth recording
as evidence the formulas are right, not just documented as intent.

**Member Master and Employer Contacts: same entities, same employer
mapping.** Row counts are unchanged (285 members, 101 contacts); I checked
every member's and contact's `Employer ID` individually against the old
workbook and found zero reassignments. This matters specifically because
`plan.md` §11 already documents a historical trap — *"the 17 Sep re-issue
reassigned the caller on all 100 calls... either mismatched pairing is
internally consistent, so nothing errors."* That trap does **not** recur
here: this revision doesn't move anyone.

**Product & Carrier, Weekly Volume, Distribution Targets, Batch Coverage,
Agent Roster:** same pattern — previously-blank `TOTAL`/`CHECK`/share
columns now computed and populated (Distribution Targets' check row now
reads "OK — caller mix, outcomes and archetypes each sum to 600"). No
column removed, no row's identity changed.

---

## 6. Account Risk Design: the corpus is now deliberately concentrated

A new sheet, and a real change of allocation strategy, stated plainly:

> *"Do NOT spread evenly across employers — an even distribution makes
> account-level risk undetectable by construction, which is what happened
> in batches 1 and 2a before this sheet existed."*

Six named anchor accounts (Bellwether Restaurant Group, Cedar Point
Workforce Partners, Meridian Industries, Drummond Associates, Fontaine
Dental Partners, Park Mechanical) are designed to each carry a recurring
signal pattern across several calls from more than one caller — the shape
`domain/aggregation/risk_flag.py`'s metric 10 (≥3 calls, ≥2 of 4 conditions)
actually needs to fire meaningfully. Cedar Point is a deliberate **control**
— high volume, low severity — specifically so raw call count doesn't
predict a flag.

**This is good news for testing, not a required code change.** Nothing in
`risk_flag.py`, `indicators.py` or D2/D12's "flagged means metric 10"
ruling needs to move. What changes is that once we ingest batches with this
design (2a onward), account-level risk assessment finally has real signal
to be tested against, rather than batch 1's "85 of 92 accounts have one
call" thinness (§11's own "batch 1 is thin" trap). Worth knowing before
anyone reads too much into risk-flag results computed only against the
current 100-call answer key.

---

## 7. What did not change

Verified cell-by-cell, not by row count alone — only a trailing-cell
padding artifact differs (Excel widening a row to match the sheet's new
overall width), never the content:

**Data Model · Outcomes · Escalation Logic · Call Quality Framework ·
Signal Taxonomy · Touchpoints · Metrics · Intelligence Register · Questions
Worth Asking · Rules — Program/Administration/Carrier · Corrections &
Sources.**

Every metric formula, every signal type and its owner/severity, every
escalation trigger type, every touchpoint, every rule and its confidence —
all identical. Nothing here invalidates Phase 1–4 work; the extraction
layers, the aggregation modules, the dashboard config and the Phase 5
harness are all still built against a current definition of the workbook.

---

## 8. What needs to change, and where

| Area | What | Owner |
|---|---|---|
| `infrastructure/corpus/pdf_text.py` | Generalise `_PAGE_FURNITURE` (§4, fix verified) | Stream A |
| `infrastructure/config/paths.py`, `settings.py` | Single `workbook_path`/`transcripts_path` → something that can name several PDFs (a list, or a directory glob) | Stream A |
| `application/ports/transcript_source.py`, `PdfCorpusSource` | Read across multiple PDFs, not one | Stream A |
| `application/ports/answer_key_source.py`, `PdfAnswerKeySource` | Same, for the answer-key side | Stream A |
| `domain/entities/call_extraction.py`, `application/ports/call_extraction_repository.py`, `infrastructure/persistence/tables.py` + migration | Storage for `root_cause_owner`, `preventable`, `primary_issue`, `secondary_issues`, `impact_scope` | Stream A |
| L2 prompt/use case | `primary_issue`, `secondary_issues`, `impact_scope` as new outputs | Stream A |
| L4 prompt/use case, or a new `domain/aggregation`-style derivation | `root_cause_owner` (pending §3's open question) and `preventable` (deterministic either way) | Stream A |
| `domain/entities/ground_truth.py`, `infrastructure/reference/xlsx_ground_truth_source.py`, migration | Five new tracker columns (`Root cause owner`, `Preventable`, `Primary issue`, `Secondary issues`, `Impact scope`) currently read by nothing | Stream B |
| `domain/evaluation/field_map.py`, `insight_dependencies.py` | New comparisons once the fields exist on both sides; insight 6 and 17 move off WITHHELD in `plan.md` §9 once built | Stream B |
| `tests/integration/test_real_ingest.py` (the **named** 100-call label-leak proof), `test_real_answer_key.py`, `test_ingest_endpoint.py`, `test_evaluate_extraction_cli.py` | Hardcoded to exactly 100 calls; must generalise to "however many the corpus holds" rather than a bumped literal, since more batches are still coming | Both, whoever touches ingestion next |
| `plan.md` §5, §9 | Record the decision once made; move insights 6/17 off WITHHELD; D5/D10 updated | Whoever closes the decision |
| `Documents/` vs a new location | Where the new files land — see §9, item 1 | Minnie |

**Not affected:** Phase 4's action centre work (playbook catalogue,
lifecycle, write endpoints) — none of it touches the corpus, the schema or
reference data. Nothing here blocks finishing or merging that PR.

**Phase 5 run 1 is not invalidated, but it is now partial.** Run 1 scored
the old batch 1 against the old answer key. Since batch 1's dialogue and
original 16 fields are unchanged, run 1's numbers still describe the
pipeline honestly for those 100 calls and those 16 fields — nothing needs
retracting. But it says nothing about the four new fields, and nothing
about calls 101–200. A second run, after the fields above are built, would
be the first one to speak to `root_cause_owner`/`preventable` agreement and
to the newly-concentrated account risk design.

---

## 9. Decisions needed

Following the convention already in use for `Revised-Implementation-Plan.md`
§14: each item names a default that lets the mechanical work start without
stalling, and flags genuinely open questions with no safe default.

| # | Question | Default if unanswered | Owner | State |
|---|---|---|---|---|
| 1 | **Where do the new corpus files live, and do they replace or sit alongside the old ones?** `Documents/` is git-tracked; four PDFs plus the workbook is more surface than the current one-workbook-one-PDF layout was built for. | Add alongside (don't delete the old batch1 PDF — its dialogue is a subset, but keeping it costs nothing and losing it loses a known-good regression fixture); apply §4's fix in the same change that adds the files, since there's nothing to verify it against until then. | Minnie | **DECIDED 2026-09-25 — add alongside.** Old files moved to `Documents/superseded/`, new ones added to `Documents/`. See §12. |
| 2 | **Multi-batch architecture**: a list of paths in settings, or a directory glob (`Documents/*.pdf`, sorted)? A glob is friendlier to "more batches are still coming" but is less explicit about which files are in scope. | Directory glob over `Documents/`, matching the existing "found by default" philosophy in `paths.py`'s own comment. | Stream A | **DONE**, on the default — see §12. |
| 3 | **Is D5 formally closed?** The schema change exists and root_cause_owner carries EMPLOYER, which is exactly what D5 asked for — but D5 says "confirm with Minnie" per its own heading, and D10's "fault records" framing may not survive contact with what actually shipped (four flat fields, not a fault-record table). | Hold as proposed-closed here; record formally in `plan.md` once Minnie/Karim confirm the framing, rather than assume. | Minnie, with Karim | Still open. |
| 4 | **`root_cause_owner`: a new L4 LLM output, or a deterministic derivation** from `complaint.attributed_to` and the signal taxonomy's owners (the algorithm the schema itself gives)? Changes whether this is a prompt change or a pure function, and whether the field can disagree with the fields it's built from. | Deterministic derivation, following the precedent of metric 4 and member-effort-complexity ("computed, not extracted") and because the schema names the exact rule to apply. `preventable` is unambiguously deterministic either way. | Minnie | **DECIDED 2026-09-25 — deterministic derivation.** Not yet built (§10 step 2). |
| 5 | **Insight 25** — does `MEMBER_MISUNDERSTANDING` partially address it, or does it stay WITHHELD as specified (`PLAN_AS_DESIGNED`/`MEMBER_COMPREHENSION`, neither of which arrived)? | Stays WITHHELD; don't reinterpret the insight to fit what shipped. | Minnie | Still open. |
| 6 | **Do we re-run Phase 5's evaluation** once the new fields and batches are ingested, or treat it as a separate, later check-in? | Separate check-in, after the fields are built and at least one full ingest of all available batches — re-running now would only re-measure the same 100 calls with nothing new to show. | Minnie | Still open. |

---

## 10. Suggested shape, not a phase number

Given the size of what's needed (§8) versus how much of it is mechanical
once the four decisions above are made, I'd size this as a short run of
small, separately-reviewable PRs rather than a new numbered phase:

1. **Corpus plumbing** — apply §4's fix, land the new files, generalise
   `transcripts_path`/`workbook_path` to multiple documents, update the
   hardcoded-100 tests. Nothing about the schema yet; this alone lets
   `import_reference` / `ingest_transcripts` / `import_answer_key` run
   against all 200 calls.
2. **The four new fields, extraction side** — entity, table, migration,
   repository; L2 prompt additions for `primary_issue`/`secondary_issues`/
   `impact_scope`; `root_cause_owner`/`preventable` per decision #4.
3. **The four new fields, answer-key side** — `GroundTruth` columns, tracker
   import, field-map comparisons, `plan.md` §9 reclassification of insights
   6 and 17.
4. **A second corpus run and evaluation**, once 1–3 land and all available
   batches are ingested — decision #6.

Steps 2 and 3 can run in parallel once step 1 is done, matching the
Stream A/B split already in use.

---

## 11. What's paused

Phase 4's actions PR (`phase4-actions`) is untouched and unaffected by any
of this. Steps 2–4 of §10 wait on §9's remaining open items (3, 5, 6).

---

## 12. Step 1 shipped: corpus plumbing

On branch `corpus-v10-plumbing`, off `main`. Everything below is applied
and gate-verified (`scripts/check.sh` green, full backend suite passing,
97% coverage, all five import-linter contracts kept).

**Files.** The four new documents are in `Documents/`; the superseded bible
and batch-1 PDF moved to `Documents/superseded/` (`git mv`, history kept).

**§4's footer fix**, applied as written there.

**Multi-file ingestion.** `transcripts_path` (one `Path`) is now
`transcripts_dir` (one directory); `PdfCorpusSource` and
`PdfAnswerKeySource` both take a directory and read every `*.pdf` in it,
non-recursively — `discover_batch_pdfs`/`extract_call_blocks_across`, new
in `pdf_text.py`. A call reference appearing in more than one file is
refused with both filenames named, not silently taken from whichever file
happened to be read last. `workbook_path`'s default now points at
`nanovox_corpus_v9_build_bible_6.xlsx`.

**The hardcoded-100 tests** (§8's table) now assert a floor (`>= 100`)
rather than an exact count, except the two tests that specifically
cross-check figures the prototype's own tooling published for batch 1
alone (`Prototype/tools/README.md`) — those now filter to `C-0001`–`C-0100`
explicitly, so a later batch's mix can't silently change what they check.

**A second parsing gap, found by these tests, not by reading — fixed.**
Running the real corpus through the newly-generalised ingestion surfaced
one row the answer-key importer couldn't parse:
`xlsx_ground_truth_source.py`'s `_escalation` method recognised exactly two
shapes — `"triggered false"` bare, or a full `"triggered true|<type>|
requested_by_caller <bool>|handled <bool>"` — and warned on anything else.
C-0120 (batch 2a) is a third shape the corpus hadn't written before: an
escalation *nothing warranted*, that happened anyway —
`"triggered false|none|requested_by_caller false|handled true —
OVER-ESCALATION"`. The `GroundTruth` entity already has independent
`escalation_triggered`/`escalation_handled` fields, so this needed no new
field — only the parser taught to read the fourth shape, dropping the
trailing `" — OVER-ESCALATION"` annotation once it's done its job (the
combination `triggered=False, handled=True` is already the anomaly; the
label names it, it doesn't add a fact). Scoped narrowly to this one call
site — a generic "strip after em dash" rule would misread the tracker's
other use of `—` as its blank-cell marker. Verified against the real
workbook (the warning is gone) and locked in with a fixture case
(`C-9005` in `tests/fixtures/tracker_sheet.py`) plus two unit tests.

**Not touched**: nothing about the four new v10 fields. `GroundTruth`,
`CallExtraction`, the L2/L4 prompts and the evaluation harness are
unchanged — that's §10 steps 2–3, still ahead.
