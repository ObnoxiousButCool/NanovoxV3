# Cross-screen data consistency and reconciliation audit

**Scope:** Executive Overview, Risks, All Calls, plus Hierarchy, Rules, Agents,
Actions, and `/insights/filters` as supporting ground truth.

**Method:** Read-only. No files changed, no commits beyond this report, nothing
pushed until explicitly approved. Audited against `main` at commit `a9c3d6b`
("Merged PR 23608: V2 prototype parity review"), on a dev server running that
exact commit against the current database. Ground truth was pulled live and
unfiltered from every relevant endpoint (`/insights/filters`, `/exec`, `/risk`,
`/calls`, `/hierarchy`, `/agents`, `/rules`, `/actions/board`, `/actions`) and
cross-checked against the backend source (`domain/aggregation/*`,
`application/use_cases/read_insights.py`, `application/use_cases/list_calls.py`,
`frameworks_drivers/api/v1/insights/*`) and the frontend screens that render
them. The corpus is static: 600 calls, 95 employers, dated 2026-07-06 to
2026-09-25. "Today" in this environment is 2026-10-01.

Per the brief: production is treated as authoritative throughout. No attempt
was made to match production numbers to the Prototype's illustrative figures.

---

## A. Confirmed consistent

1. **Escalation figures tie exactly between Exec and Risk.** Exec's
   `escalation_integrity` (`handled/triggered = 40/73 = 0.5479`) and Risk's
   `escalationsTriggered: 73` / `escalationsMissed: 33` (73 − 33 = 40 handled)
   describe the identical set of escalations, over the identical population.
   Not independently recomputed on either screen.

2. **Hierarchy's region rollups reconcile exactly with Risk's totals**, all
   over the same windowed population:
   - `regions[].calls` sums to 562 — the same windowed call count Risk and
     Exec report (see B1 for what "windowed" means here).
   - `regions[].flagged` sums to 12 — matches Risk's `exposure.employers`
     (12) and the 12 `flagged: true` rows in Risk's `assessed[]`.
   - `regions[].unresolved` sums to 106 — matches Risk's `outcomes`
     `UNRESOLVED` count (106) exactly.
   - `regions[].accounts` sums to 95 — matches Risk's
     `assessedCount(50) + ineligibleCount(45)`, which in turn matches the
     total employer count from `/insights/filters` (95).

3. **Risk's own internal arithmetic is sound.**
   - `assessedCount (50) + ineligibleCount (45) = 95` = total employers.
   - `outcomes` breakdown: `326 + 101 + 29 + 106 = 562` = the windowed call
     population (see B1).
   - `flaggedShare.value (0.24)` = `12 flagged / 50 eligible` exactly,
     consistent with both `exposure.employers` (12 refs) and the 12
     `flagged: true` rows in `assessed[]`.
   - The `unresolved` driver (106 calls) matches the `outcomes` `UNRESOLVED`
     count (106) exactly — same definition, same number, two places.

4. **Rules screen reconciles exactly.** `overallRate` (`40/141 = 0.2837`)
   matches both `byLayer` (18 + 7 + 15 = 40) and `byProvenance`
   (34 + 6 + 0 = 40), over the same 4-week/141-call window Exec's
   `first_contact_resolution` and `knowledge_failure_rate` also use
   (both `n = 141`).

5. **Exec and Risk render the same fields, not parallel calculations.**
   `ExecScreen.tsx:392-393`'s "Needs attention" risk strip and
   `RiskScreen.tsx:206-207`'s headline both read `flaggedShare`,
   `assessedCount`, and `exposure.lives` straight off the same `/insights/risk`
   response shape. No duplicated client-side math, no divergent rounding.

6. **All nine endpoints report the identical corpus reference data** — same
   `corpusPeriod` (2026-07-06 → 2026-09-25), same 600-call / 95-employer
   totals in `scope`. No drift in what "the corpus" means between screens.

7. **Calls page's definitions of "unresolved" and "escalation missed" match
   Risk's conceptually.** Both use `Outcome.UNRESOLVED` for unresolved, and
   both use "escalation triggered and not handled" for escalations missed
   (`list_calls.py:231-234` vs. the `Escalation.missed` logic behind
   `read_insights.py`'s `escalations_missed=len(missed)`). The only
   difference between the two screens' counts is population — see B1.

8. **No hardcoded Prototype values were found in production code.** Grepped
   the screens and their tests for the pattern the brief warned about
   (prototype sample numbers leaking into production); found the opposite —
   explicit tests asserting the UI draws lanes/labels from the server
   response rather than a hardcoded list (`ActionsScreen.test.tsx:453`,
   `:461`).

---

## B. Legitimate differences

1. **"All calls" (600) vs. the 12-week windowed population (562) is an
   intentional per-metric design, not a bug by itself.** The Calls screen
   defaults to no period filter, so it shows the full static corpus (600
   calls — confirmed via `scope.considered: 600, matched: 600` with no
   filters applied). Risk's `account_risk_flag` metric and three of Exec's
   five scorecard metrics (`escalation_integrity`, `failure_driven_repeat_rate`,
   `commercial_intent_capture`) are configured with `window_weeks: 12` in
   `dashboard.yaml`, which is a deliberate recency window, not a mistake.
   Examples of the resulting, individually-legitimate gaps:
   - Calls page `escalationsMissedCount: 34` (over 600) vs. Risk
     `escalationsMissed: 33` (over 562).
   - Calls page `unresolvedCount: 115` (over 600) vs. Risk `outcomes`
     `UNRESOLVED: 106` (over 562).

   These are not arithmetic errors — same definition, different population,
   by design. **However**, see C1: the mechanism that produces "562" is
   itself drifting in a way that was only partially disclosed, and the size
   of this "legitimate" gap will keep growing for a corpus that will never
   grow to match it.

2. **`flaggedShare` is deliberately divided by *eligible* employers (50), not
   all employers (95).** This is explicit and tested
   (`risk_flag.py:204-209`'s own docstring, `test_risk_flag.py`'s
   `test_the_flagged_share_divides_by_eligible_employers_not_all_of_them`,
   and `test_insights_endpoints.py`'s
   `test_flagged_share_divides_by_the_eligible_not_the_book`). The UI states
   the denominator in words ("{share} of {assessedCount} assessed") on both
   Exec and Risk, so this is correctly disclosed, not just correctly coded.

3. **Exec's headline `calls: 562` is documented as "calls in the longest
   window on the screen," not "calls in the corpus."** Per
   `exec_scorecard.py:188-191`: "Never the sample behind any one figure —
   read that figure's own `n`." This is legitimate by its own definition. The
   risk is purely one of a reader conflating it with the corpus total shown
   elsewhere (Calls page, filter bar) — see C1.

4. **`newlyFlagged`'s 4-week window trails past the corpus's actual end
   date, but loses nothing.** `since: 2026-09-03` (today minus 4 weeks) runs
   to 2026-10-01, six days past the corpus's last call (2026-09-25). Unlike
   the 12-week window (C1), this only adds empty trailing days — it doesn't
   exclude any calls that exist, since its start date is still inside the
   corpus. Harmless.

---

## C. Genuine inconsistencies / bugs

### C1. The 12-week window is anchored to real "today," not the corpus's end date — and the resulting data loss is broader than previously tracked

- **Screens/components affected:** Risk (`account_risk_flag` / "Metric 10" —
  every figure on the page derives from it: `assessed`, `outcomes`, `drivers`,
  `exposure`, `flaggedShare`, `escalationsTriggered/Missed`), Exec (headline
  `calls`, plus `escalation_integrity`, `failure_driven_repeat_rate`,
  `commercial_intent_capture`), and Hierarchy (every region/broker/employer
  call count in `tree`, `matrix`, and `regions`).
- **Displayed value:** 562 calls (today, 2026-10-01).
- **Expected/reconciled value:** 600 — the full corpus — if the window is
  meant to represent "the corpus's own recent activity," since the corpus
  itself spans only 12 weeks and 3 days (2026-07-06 to 2026-09-25).
- **Source:** `domain/aggregation/patterns.py::window_for()` computes
  `Window(as_of - timedelta(weeks=12), as_of)`; `as_of` comes from
  `request.as_of or self._clock.now().date()` — i.e., it defaults to the
  real wall-clock date, not the corpus's last call date. Called from
  `GetAccountRisk.execute()` (`read_insights.py` ~line 544) for Risk, and
  from `exec_scorecard()`/the metric-threshold loop for Exec's 12-week
  metrics, and from the hierarchy use case for the drill tree.
- **Likely cause:** the corpus is a fixed, non-growing demo dataset, but the
  window that's supposed to describe "the last 12 weeks of it" is anchored to
  the real calendar instead of the corpus's own last date. As real time
  advances past the corpus's 90-day span, the window keeps sliding forward
  and excludes progressively more of the earliest calls (2026-07-06 to
  2026-07-08 today — 38 of 600). This will keep worsening daily and, once
  "today" passes roughly 2026-12-18 (12 weeks after the corpus's last call),
  the window will stop overlapping the corpus at all, at which point every
  one of these metrics would go from "562 of 600" straight to withheld/empty
  for a dataset that still has 600 calls in it.
- **Already partially known, but undersold:** PR 23608's merge commit
  explicitly names this for the Risk screen only ("The risk screen drops 38
  of 600 calls without saying so... the 6–9 July calls f[all outside it]"),
  flagged "Open, and not for this branch." This audit confirms the exact
  mechanism and the exact number (38/600, matches), but found the same
  mechanism also drives Exec's own headline call count and three of its five
  scorecard metrics, and the entire Hierarchy drill tree — none of which were
  named in that commit's list of open items. Risk's screen does disclose the
  window in words ("Metric 10 over 12 weeks, as at 2026-10-01," per
  `RiskScreen.tsx:195`), but never states that real calls are being excluded,
  nor by how many. Exec and Hierarchy disclose no window caption at all for
  this reason.
- **Severity:** High, and actively worsening. This is not a one-time
  rounding artifact; it's a monotonically growing, silent exclusion of real
  data affecting the two highest-traffic screens in the app plus the
  drill-down hierarchy, on a corpus that will never grow to catch up with it.

### C2. `flaggedShare`'s sample-size field doesn't mean what every other figure's sample-size field means

- **Screen/component:** `/insights/risk`'s `flaggedShare` (consumed by both
  `RiskScreen.tsx` and `ExecScreen.tsx`).
- **Displayed value:** `n: 54`, with a 54-entry `callIds` list.
- **Expected/reconciled value:** every other `Figure`-shaped metric checked in
  this audit has `n` equal to its own denominator (`first_contact_resolution`
  n=141 = the 4-week window's call population; `overallRate` n=141 likewise;
  `escalation_integrity` n=73 = its own denominator). By that convention, a
  reader would expect `flaggedShare.n` to equal its real denominator —
  eligible employers (50) — not 54.
- **Source:** `domain/aggregation/risk_flag.py::flagged_share()` (lines
  204–225) builds the figure's call-id list from
  `tuple(sorted(ref for a in flagged for ref in a.evidence))` — the union of
  evidence call IDs across the 12 flagged *employers*, not the 50 eligible
  employers that actually form the ratio's denominator.
- **Likely cause:** `Figure` is a generic call-evidence container built for
  call-level rates; it was reused here for an employer-level ratio without a
  separate "how many employers" field, so `n`/`callIds` quietly mean
  something different for this one figure than for every other figure on the
  app.
- **Severity:** Low today. `FigureSample` — the only component that renders
  `.n` as visible text ("N calls") — is never used for `flaggedShare` on
  either screen (`RiskScreen.tsx` and `ExecScreen.tsx` both use only
  `<FigureValue>` for it). So nothing on screen is currently wrong because of
  this. It is a latent trap for the next engineer or API consumer who
  assumes the "n = denominator" convention holds everywhere, as it does for
  every other figure checked.

No further arithmetic (rounding-only) discrepancies were found beyond the
above; C2 is a definitional mismatch, not a rounding error.

---

## D. Unable to verify

1. **A full call-by-call outcome-mix reconciliation between the Calls page
   and Risk's `outcomes` breakdown.** `/insights/calls` doesn't expose an
   outcome-breakdown aggregate over its full matched population — only
   `unresolvedCount`, `escalationsMissedCount`, and `averageQuality`. A
   precise comparison would require paginating all 6 pages (100 rows × 6) and
   summing outcomes client-side. Not done, because the ~38-call gap between
   the two screens' populations is already structurally explained by C1; a
   manual sum would only re-confirm the same gap, not surface a new fact.

2. **Whether Exec's trend/movement arrows share the same drift problem as
   C1.** `_exec_trends()` uses a separate windowing mechanism
   (`domain/aggregation/trends.py`'s `as_of_window`/`preceding`), distinct
   from `window_for()`. The raw `trends` payload (57KB) was pulled but not
   walked line-by-line against that module in this pass. Not assumed
   consistent or inconsistent — flagged as unchecked.

3. **Whether Actions board/findings figures reconcile with Risk's drivers or
   Exec's escalation counts.** Both were fetched (`actions_board.json`,
   `actions_findings.json`) but not cross-checked against `drivers[].calls`
   or the escalation figures in this pass.

4. **The Demand screen (`/insights/demand`) was not fetched at all** in this
   pass — any touchpoint/complaint-attribution totals there were not checked
   against Hierarchy's `complaints` field or Risk's `complaint_choice` driver
   (80 calls).

5. **Agents screen's per-band quality figures vs. the Calls page's
   `averageQuality` (93.74 over 600) or Rules' 141-call population.** Whether
   the agent-quality floor (`minCallsForARate: 30`) creates yet another
   distinct population from the 141/562/600 ones already traced was not
   verified.

---

## Final summary

- **Confirmed inconsistencies (bugs): 2** — one high-severity and actively
  worsening (C1), one low-severity and currently latent/not user-visible (C2).
- **Legitimate differences: 4** (B1–B4).
- **Unable to verify / unknown: 5** (D1–D5).

**Five most important discrepancies:**

1. **(C1)** The 12-week window behind Risk's Metric 10 is anchored to the
   real calendar date rather than the static corpus's own end date, silently
   excluding 38 of 600 calls today — a gap that grows every day and was
   known only for the Risk screen (per PR 23608), not for Exec or Hierarchy,
   which this audit found are driven by the identical mechanism.
2. **(C1, continued)** Exec's own headline "calls" figure (562, not 600) is
   affected by the same drift, with no window caption disclosing it the way
   Risk's does.
3. **(B1)** Calls page vs. Risk page "escalations missed" (34 vs. 33) and
   "unresolved" (115 vs. 106) differ only by population today — legitimate
   now, but the gap will widen as C1 worsens, making two correctly-defined
   screens look increasingly inconsistent to a reader who doesn't know why.
4. **(C2)** `flaggedShare`'s sample-size field breaks the "n = denominator"
   convention every other figure on the app follows — not yet shown on any
   screen, but a trap for future work.
5. **(D1)** A full outcome-by-outcome reconciliation between the Calls page
   and Risk's outcome breakdown could not be completed without paginating
   all 600 calls; not attempted because the gap is already explained
   structurally by C1, and manufacturing a number here would risk inventing
   a reconciliation the data doesn't yet support.

**Is the Prototype v2 frontend faithfully displaying production data?**
Yes, with one caveat. Every value checked in this audit (Exec, Risk, Rules,
Hierarchy) traces directly to its own API response field — no hardcoded
numbers, no stale fallbacks, no duplicated client-side recomputation, and no
leftover Prototype sample values were found anywhere in production code.
Exec and Risk in particular share the exact same `flaggedShare`/
`assessedCount`/`exposure` fields rather than each computing its own version.
The one place the frontend could still mislead a reader is passive, not
active: neither Exec nor Hierarchy states that its 562-call figure is
excluding real corpus calls, so a faithful rendering of a quietly-drifting
backend number is still a number a reader could reasonably misread. That is
a backend/data-pipeline issue (C1), not a frontend-parity issue.
