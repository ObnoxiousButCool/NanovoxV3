# Corpus update, 2026-09-28 — the corpus completing to 600 calls

**Analysis only — nothing in this repo has been changed as a result of it.**
No files moved, no settings pointed at the new folder, no code touched.

## What arrived

In `C:\Users\ShlokaKulkarni\Downloads\updateddocs\updatedAsOf28th`:

- `nanovox_corpus_v9_build_bible_3.xlsx` — an updated build bible.
- Eleven transcript batch PDFs, `batch1` through `batch9c`, covering calls
  001–600. Six of these (`batch4` through `batch9c`, 201–600) are new; the
  first three cover the same 001–200 range already in `Documents/`.

The README both workbooks share says the corpus was always scoped at 600
calls (its own opening line: *"600 calls · 12 weeks..."*). What we've had
so far — `Documents/`'s three batches, ~200 calls — was batch 1 of an
explicitly "expected six batches of 100," per `Batch Coverage`'s own note.
This delivery is that plan finishing, not a new plan.

## Schema comparison: old workbook vs. new

Compared `Documents/nanovox_corpus_v9_build_bible_6.xlsx` (currently
configured, `DEFAULT_WORKBOOK_PATH`) against the new `_3.xlsx`, sheet by
sheet:

| Sheet | Result |
|---|---|
| `Call Tag Schema` | **Byte-identical.** |
| `Root Cause` | **Byte-identical.** |
| `Weekly Volume` | **Byte-identical.** |
| `Transcript Tracker` | **Same 29 columns, same order, same names** — including all five v10 fields (`Root cause owner`, `Preventable`, `Primary issue`, `Secondary issues`, `Impact scope`). Row count grew 206 → 607 (205 → 606 calls). |
| `Batch Coverage` | Same structure (same measures, same targets). Every "Written (at 200)" column became "Written (at 600)", and every actual/target pair that was running at roughly one-third now reads at or near its full 600 target. This is a progress sheet reporting the same plan further along — not a changed plan. |
| `README` | Same eleven sections verbatim, plus five new rows appended: a "CORPUS CALIBRATION AT 600" summary (see below). |
| Every other sheet (`Data Model`, `Outcomes`, `Escalation Logic`, `Call Quality Framework`, `Signal Taxonomy`, `Touchpoints`, `Metrics`, `Intelligence Register`, `Questions Worth Asking`, the three `Rules —` sheets, `Corrections & Sources`, `Employer Master`, `Member Master`, `Employer Contacts`, `Broker Master`, `Product & Carrier`, `Agent Roster`, `Distribution Targets`, `Coverage Matrix`, `Account Risk Design`) | Identical row/column counts in both. Not diffed cell-by-cell beyond that — no reason to suspect drift given every sheet checked so far matches, but flagging that this wasn't exhaustive. |

**No schema change of any kind.** The v10 fields shipped this week —
`root_cause_owner`, `preventable`, `primary_issue`, `secondary_issues`,
`impact_scope` — are the same four fields, same shapes, same enum values,
in both workbooks.

## Ground truth is populated for the new calls, not just headroom

Spot-checked `Root cause owner` / `Preventable` / `Primary issue` /
`Impact scope` at rows 200, 201, 300, 450 and 600 of the new tracker —
every new call has real values, not blanks:

```
C-0197  CHOICE   Yes                       dependent terminated in error       1 dependent
C-0198  CHOICE   Yes                       no in-network specialist within...  1 member
C-0297  CHOICE   Yes                       invoice layout query                1 group
C-0447  CARRIER  Partly — carrier mgmt     assigned dentist retired            1 member
C-0597  BROKER   Partly — broker enable.   assigned dentist rule               1 member
```

The tracker's own new calibration section (`README`, appended) states:
root cause traces to a Choice-owned or Choice-system cause on **266 of 600
calls (44%)** — directly the number our `preventable_of()` mapping
(CHOICE/SYSTEM → `Yes`) is meant to produce once this corpus is run.
Outcome mix: resolved 368, partially resolved 73, escalated 34, unresolved
125 (61% resolved). Product mix runs slightly program-level-heavy against
target (83 vs. 67), dental/vision/chiro each a little under.

## Compatibility check: does today's code read this, unmodified?

Ran the existing corpus reader against the new folder directly, nothing
written anywhere:

```
discover_batch_pdfs(new_folder)  → all 11 PDFs found
extract_call_blocks_across(...)  → 600 call blocks parsed, zero errors
```

The ingestion code added for v10 (`discover_batch_pdfs` / the
directory-based `PdfCorpusSource`/`PdfAnswerKeySource`) already reads
every batch PDF in a directory rather than one hardcoded file — built
for exactly this kind of expansion. It parses all 600 new-batch calls
without modification.

## Conclusion

**This is a pure data-completion delivery, not a schema change.** Nothing
about the pipeline, the domain model, the repository, the prompts, or the
evaluation harness needs to change to support it. The only "backend
change" this implies is operational, not structural:

1. The new batch PDFs (`batch4`–`batch9c`) would need to join
   `Documents/` alongside the existing three (or replace them, since
   `batch1`/`batch2a`/`batch3` here are `_rev2`/newer revisions of the
   same 001–200 range already present — worth a byte-level check before
   assuming they're drop-in identical to what's already in `Documents/`,
   which this analysis did not do).
2. `DEFAULT_WORKBOOK_PATH` would need to point at whichever workbook is
   chosen as canonical going forward — the new `_3.xlsx` naming doesn't
   follow the existing `_N` revision sequence (`_6.xlsx` was the most
   recent before this), so which file is actually newer/canonical is worth
   confirming with Ranjit rather than inferred from the filename alone.
   Everything in this analysis compares them by content, not by name, and
   by content the new file is a strict superset of the old one.
3. A fresh extraction run over all 600 calls, once the above two are
   settled — the current run in progress covers only the existing
   ~100-call corpus in `Documents/`.

No code changes are proposed or required. This is a go/no-go on **when**
to bring the remaining 400 calls in, not **whether** anything needs to be
rebuilt.
