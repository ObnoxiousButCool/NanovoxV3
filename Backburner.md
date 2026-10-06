# Backburner — what is left of the Revised Implementation Plan

**Checked:** 2026-10-06, against `main` at `f18ff62`.
**Method:** every one of the 32 insights in `plan.md` §9 walked against what actually
renders — the reconciliation `Revised-Implementation-Plan.md` calls **Checkpoint I5**.
Nothing here is read from a checklist; each line was verified in the code.

Phases 0–5 of the revised plan are done. What follows is **Phase 6** (the screens V2
dropped, plus the remainder) and **Phase 7** (hardening), with one piece of finished
work that fell off the branch list.

---

## 1. Finished work that was never merged

### `cost-to-serve` — insight 15, view 2

A local branch, `2cb54e1`, 579 lines across eight files, with tests. It wires metric 9
into the exec scorecard and screen, which is where `exec.html` has always had it.

Its own commit message states the problem it fixes, and the problem is still live:

> Metric 9 was built in the domain, tested, and wired into no endpoint at all, so
> insight 15's minutes view rendered nowhere.

`cost_to_serve` is on `main` today at `domain/aggregation/demand.py:117` and nothing
reads it. The remote branch is gone and the commit is **not** an ancestor of `main`.
It no longer merges cleanly — `git merge-tree main cost-to-serve` conflicts, five days
of drift.

Cheapest item on this list by a distance: resolve the conflict, re-run the gates, raise it.

---

## 2. Phase 6 — close scope

### `/demand` — insights 15 (view 1), 16, 18

The endpoint is built and its figures were verified against the corpus call by call on
2026-10-05: all 144 touchpoints, the self-inflicted components, the complaints cut.
**There is no route for it.** `App.tsx` has nine screens and `/demand` is not one.

This is the largest gap: a correct, tested endpoint whose every figure renders nowhere.

Insight 19 (compliance exception exposure) is unaffected — it renders on `/actions` and
`/agents` already.

### `/value-pack` — insights 30 and 32

Neither endpoint nor screen. Insight 30 is PARTIAL by `plan.md` §9 (the "what we caused"
figure needs D5's party field; until then the complaint-based figure, labelled). Insight
32 (ancillary attach opportunity) has no code anywhere — `grep` finds nothing.

Insight 31 is **not** blocked: commercial intent renders on `/exec`, and its `routed`
facet is correctly withheld with `NO_FIELD` rather than defaulted to false.

### `/catalogue` — all 32 insights with screen and origin

Not built. This is the page that makes scope provable rather than asserted, and it is
what turns this document into something that maintains itself.

### `/diagnostics`

`container.diagnostics_source` exists and the evaluation CLI reads it — markers raised,
rejection rate, last run cost, unresolved callers, each distinguishing its own kind of
nothing from a zero. No endpoint exposes it, and `/status` is still the Phase 0
placeholder: a single `<h1>` and nothing else.

### Withheld panel for insight 26

`WITHHELD_PANELS` carries 9 (band calibration), 22 (did-it-work) and 25 (plan-design
confusion). **26 — the carrier service scorecard — has no panel.** `plan.md` §9 says to
show `complaint.attributed_to = CARRIER` counts, labelled, and say plainly that no
carrier entity exists in v9. Nothing renders it today, which is the silent absence the
withheld-panel mechanism exists to prevent.

Insights 6 and 17 were promoted from WITHHELD to BUILD by the v10 `root_cause_owner`
change, so 26 is the only one outstanding. Insight 17 renders in the call drawer as a
chip; whether that satisfies "proximate vs root cause" as §9 describes it is worth a
second look.

---

## 3. Phase 7 — hardening

Verified absent:

- **No print stylesheet.** `grep -rn "@media print"` over the frontend returns nothing.
  The plan calls for one explicitly, because the prototype's own README says these pages
  get printed in meetings.
- **No 320px breakpoint.** The CSS has 700, 720, 760, 1100, 1180 and 1320; the plan asks
  for verification at 320 / 768 / 1440.
- **README is 59 lines and two sections** — Setup, and Before every commit. The plan wants
  the three import commands, running an extraction, and an architecture diagram. The
  README itself says the diagram "will follow as the codebase is built".

Not audited, so not claimed either way: the accessibility pass (focusable rows, Enter and
Space, keyboard-reachable tooltips, shape-coded rather than colour-coded band pills),
query performance on the paged call list and trend rollups, caching for
recomputed-per-request figures, and Postgres verification of the date boundaries that
SQLite tolerates and Postgres does not.

---

## 4. Two things about the plan documents themselves

**`plan.md`'s progress checklist is stale and misleading.** It currently reads:

```
[~] Phase 4 — Extraction stages (L3, L4, the derivations and the pipeline use case not started)
[ ] Phase 5 — Evaluation harness
[ ] Phase 6 — Aggregations and read endpoints
[ ] Phase 8 — Screens
```

All of those are substantially built — the harness runs against the real corpus in CI,
seventeen insight endpoints are live, and nine insight routes render. Anyone reading that file to find
out where the project stands would be badly misled. It needs a pass against reality, or
it needs to stop claiming to be a progress record.

**`plan.md` says it is never committed, and it is committed.** Its header says "This file
is never committed and never pushed… If `git status` ever lists `plan.md`, stop and fix
that before doing anything else." It was added deliberately on 2026-09-29 in `1c0ac83`,
"Pushing plan doc", and is not in `.gitignore`. The tracking looks like the decision and
the header looks like the stale part — but the two disagree in writing, and the header is
the one that tells a reader to stop work.

---

## Suggested order

1. **`cost-to-serve`** — finished and tested; only a conflict resolution stands in the way.
2. **`/demand` screen** — the biggest gap, and the endpoint behind it is already verified.
3. **Insight 26's withheld panel** — small, and it closes the withheld set.
4. **`plan.md` checklist** — cheap, and it stops the next person being misled.
5. **`/catalogue`** — makes scope provable, and keeps this list honest afterwards.
6. **Print stylesheet and the 320px pass** — small, self-contained, and named in the plan.
7. **`/value-pack`, `/diagnostics`, README** — larger, and `/value-pack` is partly blocked
   on D5.
