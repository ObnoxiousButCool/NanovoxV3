# Workbook `_6` and the rev2 corpus — what changed, and what it costs

**Date:** 2026-09-25 · **Status:** findings; four decisions open, none taken here
**Sources compared:** `nanovox_corpus_v9_build_bible_2.xlsx` against `_6`, and
`nanovox_v9_transcripts_batch1_001-100_1.pdf` against `batch1_rev2_001-100`

The new corpus is committed (`f010772`). Nothing in the code points at it yet,
and one of its changes is a **schema expansion**, not an import. This records
what is actually different, what it breaks, and what has to be decided before
anyone spends money re-extracting.

---

## 1. The pair is sound, and the reconciliation still exits 2

`plan.md` §11 warns that the workbook and the PDF must be a matched pair, and
that both pairings are internally consistent so nothing else gives it away.
Checked, by running the free half of the pipeline against `_6` + rev2:

| Step | Result |
|---|---|
| `import_reference` | 30 brokers · 95 employers · 285 members · 101 contacts · 20 agents · 122 rules · 12 touchpoints |
| `ingest_transcripts` | **100 calls, 100 resolved** — no caller-unresolved, agent-unknown or speaker-unresolved |
| `import_answer_key` | **exit 2 — NOT RECONCILED** |

**The exit 2 is right to fire and wrong about why.** Its message says *"most
likely the workbook and the transcripts PDF are different revisions"*. They are
not. The 100 unmatched rows are **C-0101–C-0200**: workbook `_6`'s Transcript
Tracker covers 200 calls, and only batch 1 was ingested. For batch 1 the
reconciliation is clean — 100 calls, 100 ground-truth rows all joined, **zero
disagreements on the five shared fields**.

So the check cannot distinguish *wrong revision* from *partial ingest*, and it
reports the first when it sees the second. A pipeline that treats exit 2 as a
hard stop — which is the point of it — now stops on a corpus that is fine.
**Worth fixing before batch 2a and 3 are ingested**, because after that this
particular false alarm disappears and the weakness stays.

---

## 2. Reference data: same rows, cells that were blank are now filled

Every master sheet differs while the row counts are identical — **105 of 109**
Employer Master rows, **33 of 36** Broker Master rows. Columns were **appended,
not inserted** (shared headers are in the same order), so the importer cannot
misread a field.

What changed is that `_2` left cells empty where `_6` has values: participation,
fee band, COBRA regime, calls-per-100-lives, brokers' groups-in-book and their
two computed ratios. Plus five new employer columns — **Dental / Vision / Life /
Chiro carrier, Ortho available**.

This is not cosmetic. Those cells feed contact rate per 1,000 lives, the
exposure total, and the broker book-size floor that insight 10's ranking rests
on. **A re-import is worth doing on its own**, and it costs nothing.

> Row counts matching is not evidence the data matches. This was nearly recorded
> as "reference data unchanged" on that basis; hashing each sheet is what caught
> it.

---

## 3. The Call Tag Schema grew from **16 fields to 20**

This is the largest change in `_6` and it is not an import at all. Four new
tags, two from L2 and two from L4, so **both prompts change and every call must
be re-extracted**. There is no incremental path.

| # | Tag | By | What it is |
|---|---|---|---|
| 17 | `root_cause_owner` | L4 | Who could have prevented the call. CHOICE · BROKER · CARRIER · PROVIDER · EMPLOYER · SYSTEM · MEMBER_MISUNDERSTANDING. **On every call**, not only complaints — the sheet names the gap it closes: *"a third of calls carried no owner at all."* |
| 18 | `preventable` | L4 | Yes · Partly · No |
| 19 | `primary_issue` / `secondary_issues` | L2 | `{primary: string, secondary: [string]}` |
| 20 | `impact_scope` | L2 | `1 member · 1 group · N employees · N members + dependents` |

### Already answered by the sheet — do not re-litigate

**`preventable` is a pure function of field 17.** CHOICE and SYSTEM → Yes;
PROVIDER → No; the rest → Partly. It should be **computed, never emitted by the
model**: asking for a value that is derivable from its own input is a way to get
one that disagrees with it.

**The three buckets are reported separately.** The sheet is explicit — *"a
blended 'preventable' percentage invites an argument about the middle."*

---

## 4. The four decisions, with owners

### D-a · Does a blameless call get an owner? — **Minnie**

The sheet says populate field 17 on **every** call. `MEMBER_MISUNDERSTANDING` is
45% of the corpus, so the commonest answer is "nobody did anything wrong, they
just were not told". If a resolved, blameless call still carries an owner, then
*"preventable by Choice"* counts calls nobody would describe as a failure. If it
does not, the third-of-calls gap the field exists to close comes back.

This defines the headline metric the field was added for. It cannot be deferred
into the prompt.

### D-b · Does field 17 feed the risk flag? — **Minnie**

A per-call "CHOICE is at fault" is exactly the shape that grows into a second
scoring system, which is what **D12** spent a decision removing.

**Recommendation: informational only**, the same ruling the ten indicator
families carry, written down before anything is built on it. `dashboard.yaml`
already warns where two scoring systems on one page lead.

### D-c · Does `primary_issue` get a vocabulary? — **Ranjit**

It is the only categorical field in the schema with no enum — `{primary: string}`
against closed vocabularies everywhere else. Unconstrained model output will not
group: "missing ID card", "ID card not received" and "no card" become three
categories.

**Either it gets a vocabulary, or it is never aggregated and only ever shown per
call.** That decides whether the field is worth extracting at all.

The sheet also warns it must not be conflated with commercial intent. Worth a
test — they will look similar to a model.

### D-d · Is `impact_scope`'s N captured? — **Ranjit**

The allowed values mix a category and a number: the first two are categories,
the last two carry an unspecified N. The sheet's own example of why the field
matters is *"eleven of my people cannot find a provider"* — and the eleven is
lost if only the bucket is stored.

One field or two (scope + count)?

---

## 5. Three new sheets, and one may close an open conflict

**Account Risk Design** is a per-account test oracle: which accounts must flag,
why, and from which callers. Its column is headed **"Flag or control"**, and
Cedar Point is marked *"CONTROL — volume must not predict a flag"*. That is
independent support for **D12** (a flag, not a band) and it gives the risk
screen something it has never had: accounts that *must not* flag.

**Worth taking to Minnie alongside C1.** It may close it.

It also explains the empty screens: the corpus is designed for **600 calls**,
with roughly nine written per account so far. Most employers being ineligible is
the design, not a defect.

**Root Cause** publishes the expected distribution for field 17 —
MEMBER_MISUNDERSTANDING 45%, CHOICE 43%, BROKER 5%, PROVIDER 3%, CARRIER 3%,
SYSTEM 1%. That is a **free check on the prompt**: a run far from this shape
means the prompt is wrong rather than the corpus surprising.

**Coverage Matrix** is outcome × fault, marking red cells as the batch-3 brief.

---

## 6. Two defects found while running this

### The extraction run exited **0** having failed 94 of 100 calls

`6 completed, 94 failed, 0 skipped` and `Run 1 finished: COMPLETED`, exit code
0. Anything automating this — CI, a scheduled run — reads that as success. The
run *finished*; almost nothing was *extracted*. Those are different facts and
the exit code should say which.

### The run left the SQLite database **corrupt**

`PRAGMA integrity_check` afterwards: invalid page numbers, rowids out of order,
pages referenced twice, indexes missing rows — and a subsequent query died with
`database disk image is malformed`. Tables were reading each other's pages:
`employers` returned member rows, `calls` returned turn rows.

A backup taken immediately **before** the run is clean, and the only writes
between the two were the run's. The failure pattern fits — 6 completed, then
failures in bursts — so the file most likely became malformed early in the run
and everything after it failed against broken indexes.

**This is a bug, not bad luck.** A run that writes concurrently to SQLite and
leaves the file malformed will do it again, and the next time it may be a
database somebody cares about. It wants an owner before the next re-extraction,
which will write far more than six rows.

Recovery costs nothing: the corpus sources are intact, and
`alembic upgrade head` → `import_reference` → `ingest_transcripts` →
`import_answer_key` rebuilds everything except the extractions.

---

## 7. `paths.py` still points at the old pair

`DEFAULT_WORKBOOK_PATH` is `_2` and `DEFAULT_TRANSCRIPTS_PATH` is `_1`. The new
corpus is committed but nothing reads it without `WORKBOOK_PATH` and
`TRANSCRIPTS_PATH` set.

**Deliberately not changed here.** Those defaults are what the corpus tests read,
including the label-leak proof §6.3 calls the single most important safety
property. Switching them is a one-line change and a full test run, and it should
land with the decision to move to `_6` rather than ahead of it.

---

## What this costs, in order

1. **Rebuild the database** — free.
2. **Re-import reference from `_6`** — free, and fixes figures resting on blank cells.
3. **Decide D-a to D-d.** Extraction is the only step that bills, and the four
   fields change both prompts, so running before they are settled spends the
   whole corpus cost on a schema about to change.
4. **One breaking release** for the four fields — four wire fields, the response
   schemas, a migration, a regenerated client. Land them together, once, as D13
   was.
5. **Then extract**, and check the result against Root Cause's distribution.
