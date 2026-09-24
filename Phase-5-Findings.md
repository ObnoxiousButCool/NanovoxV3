# Phase 5 — the check-in with Minnie

The agenda for the conversation Phase 5 exists to make possible, and the
record of what it decides. Screens are built on pipeline output, so a field
with poor agreement means a screen that shows poor data — confidently, with
a call-id drawer behind it. **Which fields are good enough is decided here,
together, with the numbers in hand.**

**Status: the numbers are not in it yet.** Everything below that does not
depend on a pipeline run is complete and is worth reading before the run
happens; §2 is empty until one does. See §6 for how to fill it.

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

*Pending a pipeline run. Produced by `python -m frameworks_drivers.cli.evaluate_extraction`
— see §6.*

| Field | Agreement | Comparable / calls | Holds up | Decision |
|---|---|---|---|---|
| | | | | |

Two columns that will not be filled in by the tool, on purpose:

- **Holds up** comes from `domain/evaluation/insight_dependencies.py` and is
  printed by the CLI, but it is listed here per field so a reader can see
  the blast radius of a decision without cross-referencing.
- **Decision** is the whole point of the meeting and is written by hand.

---

## 3. What is already known, without a run

These do not depend on the numbers and will not change when they arrive.

### Four answer-key columns cannot be scored at all

| Column | Why |
|---|---|
| `rule_refs` | The rules a call *cited*. Nothing in the pipeline produces them — and this is **not** `knowledge_failure.rule_id`, which is the rule the agent got *wrong*. Comparing the two would score the pipeline against the wrong answer and read as catastrophic failure. |
| `archetype` | The tracker's own summary label. No layer produces one. |
| `aht_seconds` | Telephony, not extraction (schema field 12). There is nothing for the pipeline to get right. |
| `control_exceptions` | **A gap, not a category error.** Schema field 7 says L1/L3 emit these and the answer key records them, but `CallExtraction` has no such field. |

**`control_exceptions` needs a decision of its own.** Metric 7 — the control
exception rate — has an answer key and no pipeline output to score against,
so it cannot be measured at this check-in whatever the other numbers say.
Either Stream A closes the gap, or metric 7 goes to Phase 8 unmeasured, and
the second should be a choice rather than something nobody noticed.

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

*To be filled in at the check-in. Each entry: what was decided, by whom, and
the number it was decided on — so that a later reader can tell a judgement
from an assumption.*
