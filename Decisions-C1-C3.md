# C1 and C3 — decision brief

**For:** Minnie (owner of both) · **Copied:** Karim (C3, item 2 of `Open-Decisions.md`)
**Date:** 2026-09-25 · **Status:** **DECIDED** — Phase 2's four screens are unblocked
**Source:** `Revised-Implementation-Plan.md` §5.1, §14.1

> **Decided 2026-09-25 by Ranjit**, adopting the recommendations below in full.
> Recorded as **D12** (C1) and **D13** (C3) in `plan.md` §5, with the rejected
> alternatives and the accepted costs.
>
> Minnie owns both conflicts and may overturn either. This is recorded as *decided*
> rather than *defaulted by silence* so nobody reads it later as nobody's choice —
> but it was taken on this brief, not in session, and that is the residual risk (R2).
> An overturn is cheap now and stops being cheap once the four screens are built on it.
>
> **One question is deliberately left open:** C3's question 2 — whether a recommendation
> must be labelled on the wire. It is a compliance judgement rather than an engineering
> one, so it is carried as **C3a** in §14.2 against Phase 4 rather than closed by default.
>
> The rulings in `plan.md` also settle the C1 sub-questions below: the risk list sorts by
> **indicator count, then soonest renewal**; the filter offers **`flagged`** and
> **`minIndicators`**, not `band=High`; and **ineligible is its own visual state**.

Both are breaking API changes. §9's checkpoint I1 requires them to ship in **one** backend
commit, because two breaking releases cost twice as much and the second lands while a
frontend branch is mid-screen.

What follows is what the code and the prototype actually do today, what the choice is, what
we recommend, and what only you can answer.

---

## C1 — what "flagged" names

### The collision, precisely

Three different things currently wear two words between them.

| Word | Where | What it selects |
|---|---|---|
| **flagged** | `domain/aggregation/risk_flag.py` (metric 10, decision D2) | Employers with **≥3 calls** in the window meeting **≥2 of metric 10's four named conditions** |
| **flagged** | `Prototype/v2/nv2.js:373` — `NV.isFlagged`, off `NV.bandFor` in `Prototype/app.js:356` | Employers whose `scoped_band` is High or Elevated — i.e. **≥2 of ten indicator families** fired |
| **band** | `frameworks_drivers/api/v1/insights/accounts.py:76` | The employer's **size band in lives**, the peer-comparison denominator |

"Flagged" already names two different populations, and "band" is already taken by a third
thing that is not about risk at all. `config/dashboard.yaml` predicted exactly this: *"Two
scoring systems on one page, one of which quietly feeds the other, is how a yes/no flag turns
back into a band."*

### The two populations are not nested

They disagree in both directions, which is why one word for both is not survivable:

- An employer with **one call** raising three indicator families is **High** in the prototype
  and **not eligible** under metric 10. At batch-1 volume most of the 92 employers with calls
  have exactly one call, so this is the *common* case, not an edge case.
- An employer meeting two of metric 10's four conditions may fire only one indicator family.
  The four conditions and the ten families read different fields.

### What already exists, so this is mostly naming

Nothing has to be computed that is not computed already:

- `RiskAssessment.flagged` — the boolean (metric 10)
- `RiskAssessment.conditions_met` — 0–4
- `RiskAssessment.eligible` / `.quotable` — the two floors, kept separate on purpose
- `domain/aggregation/indicators.py` — the ten families, gated, with `observed` per family and
  `available=False` for `high_effort`, which has no v9 field

The API returns all of it already: `AccountRiskResponse` carries `flagged`, `conditions_met`,
the four `ConditionResponse`s **including the ones that did not fire**, and ten
`ObservationResponse`s likewise. The dependency runs one way only — `risk_flag.py` does not
import `indicators.py`, and a test fails if it ever does.

### Recommendation

**Hold D2 for the flag. Render the indicator count beside it. Give the two different words,
and stop using "band" for either.**

| Concept | Word on screen | Source |
|---|---|---|
| Metric 10 | **Flagged** / **Not flagged** / **Not eligible** | `RiskAssessment.flagged`, `.eligible` |
| Ten families | **"3 indicators"** — a count, never a level | `indicators.observe` |
| Lives | **Size band** | unchanged |

The prototype's four-level pill is ~6 cosmetic uses; the boolean (~11) and the count (~18) are
what the pages actually compute with. Dropping the pill costs least and removes the second
scoring system.

### Outstanding questions — C1

1. **Does the four-level pill survive anywhere?** If not, the risk list still needs a sort
   order. We propose sorting by indicator count, then soonest renewal — the prototype's own
   order — **without naming the result a band**. Confirm, because it is what a reader sees
   first.
2. **What does the risk filter offer?** The prototype filters by band (`S.band`). If bands go,
   we propose `flagged=true|false` plus `minIndicators=N`. This is a URL contract, so it is
   hard to change after the screens ship.
3. **How do ineligible accounts appear in the list?** The prototype has no concept of
   ineligibility at all — every employer gets a band. Metric 10 makes most employers *not
   assessable* at batch-1 volume. Proposal: a third visual state, never folded into "not
   flagged". Confirm its wording.
4. **Does anything outside the risk screen keep the word "flagged"?** Exec, hierarchy and the
   action centre all count flagged accounts today. If the word changes, it changes in four
   places at once.

---

## C3 — epistemic vocabulary

### The finding that reframes this

It is **not three values versus six.** The two vocabularies are attached to different objects
at different granularities.

- The API's `EpistemicClass` (MEASURED / DERIVED / WITHHELD) is a property of a **figure** —
  one number, its `n` and its evidence.
- The prototype's chip is a property of a **panel** — `NV.clsChip(kind)` sits in a section
  header, above a whole block of copy.

A panel can hold several figures of different standing, and a panel labelled `inference` holds
no figure at all — it holds a sentence.

### What the prototype actually uses

Six are defined in `CLS_TIP` (`Prototype/v2/nv2.js:158`). Across all seven v2 pages:

| Chip | Uses |
|---|---|
| `observed` | 12 |
| `pattern` | 4 |
| `recommendation` | 3 |
| `inference` | 1 |
| `derived` | 1 |
| `reference` | **0** — defined, explained in the `index.html` legend, never applied |

That legend explains only three of the six to the reader.

### Where the line actually falls

- **OBSERVED, REFERENCE, DERIVED** are statements about *where a number came from*. They can be
  a property of a figure, and two of the three already are.
- **PATTERN, INFERENCE, RECOMMENDATION** are statements about *what a claim asserts*. The server
  does not author claims today — there is no narrative, headline or insight text in any of the
  eight responses. Panel copy lives in the frontend.

So on today's architecture, three of the six are backend vocabulary and three are frontend
authoring. `Frontend/src/shared/design/primitives/epistemic.ts` already carries all six and
maps the API's values onto them; the other four are unreachable from the API.

### The cost, measured

`epistemic` is defined in exactly **one** place — `FigureResponse` in `envelope.py:86` — and
is referenced ~49 times across nine API modules plus the generated TypeScript client. Changing
the enum today is one definition, one mapping function and a client regeneration. After the
four screens exist, it is every consumer.

### Recommendation

**Split the two concepts rather than widening one enum.**

1. **Figure-level `basis`: OBSERVED · REFERENCE · DERIVED.** Rename MEASURED to OBSERVED to
   match the prototype's word and the reader's. Add REFERENCE for workbook account facts, which
   today are indistinguishable from counted figures. `WITHHELD` leaves the enum — `published`
   and `withheldReason` already carry suppression, and keeping it in both places puts the reason
   in neither.
2. **Panel-level PATTERN / INFERENCE / RECOMMENDATION stays frontend copy** — with one exception,
   below.

This is the cheapest shape that is still honest, and it keeps `Figure.__post_init__`'s invariant
that a withheld figure cannot carry a value.

### Outstanding questions — C3

1. **Is `basis` per figure or per panel?** Our reading is per figure, with panel chips as copy.
   If the server should state a panel's class, panels become a server-owned object and the eight
   responses grow a narrative layer — materially larger than the change costed above, and better
   decided now than discovered in Phase 6.
2. **Must a RECOMMENDATION be labelled in the response, not only in the UI?** `/insights/actions`
   returns recommended actions today with nothing on the wire saying they are recommendations. If
   there is an audit or compliance expectation that a suggested action is machine-labelled as
   such, that is a backend field and belongs in this release. This is the one place we think the
   answer may be yes.
3. **Does REFERENCE earn its place?** The prototype defines it, explains it, and never uses it.
   Adding it means auditing which existing figures are account facts rather than counts. Worth
   doing, but it is real work and the only part of C3 that is not naming.
4. **Is MEASURED → OBSERVED acceptable?** A breaking rename with no behavioural change. Cheap
   now, not cheap later, and it removes a word no reader uses.
5. **How does `confidence` relate?** `RuleConfidence` (VERIFIED / VERIFIED (SECONDARY) /
   UNVERIFIED) is the *rule's* provenance grade — a different thing about a different object. It
   has no chip style anywhere in `app.css`; none of its three states does. Confirm it is a
   separate chip family and not a seventh basis value.

---

## Where this leaves the build

Both conflicts are closed and Phase 2's screens can start. Two things follow from the rulings
that are worth saying plainly, because they are the parts a reader would otherwise discover
late:

1. **`BandPill` should not be built.** D12 leaves no band to render. The component shows the
   flag's three states — flagged, not flagged, **not eligible** — with the indicator count
   beside it, and its name should change along with its contract.
2. **D12 and D13 land in one backend commit**, per checkpoint I1. Both are breaking. Two
   releases cost twice, and the second one arrives while a frontend branch is mid-screen.

The remaining open item is **C3a** (§14.2): whether `/insights/actions` must say on the wire
that a recommended action is a recommendation. It does not block Phase 2. It is cheap while
the write path is being built in Phase 4 and not cheap afterwards, so it wants an answer
before then rather than at it.
