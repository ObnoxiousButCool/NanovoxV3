# UX review — NanoVox Insights

**Reviewed:** 2026-10-06, against `main` at `49098cf`, running locally.
**Re-checked:** 2026-10-08, against `main` at `c1c3332` — 38 commits later — on the
deployed app at `nanovox-insights-a4cxfre7bmg3fghd.westus3-01.azurewebsites.net`.

**Method:** every screen driven in a real browser at 1440×900 and 375×812. Load timings
from the Performance API, payload sizes from the endpoints, focus behaviour from actual
Tab presses rather than scripted `.focus()` calls, which do not trigger `:focus-visible`
and gave a false reading first time round.

Everything below is a measurement or a line of code, not an impression. Where I did not
test something I say so rather than guessing.

---

## Status at the re-check

| # | Finding | 2026-10-06 | 2026-10-08 |
|---|---|---|---|
| 1 | Cold load shows nothing useful | HIGH | **stands** — payload unchanged |
| 2 | `/risk` is seven screens, no sort | HIGH | **stands** — now 6,500 px, still 0 sortable |
| 3 | No mobile layout | MEDIUM | **largely fixed** — rail now fits; page still tall |
| 4 | Action board announces nothing | MEDIUM | **stands** — still 0 live regions |
| 5 | No global `:focus-visible` | LOW | **stands** |
| 6 | No print stylesheet | LOW | **stands** |
| 7 | `/exec` is four screens | MEDIUM | **fixed** — 3,932 px → **2,129 px** |
| 8 | No skip link | LOW | **stands** |
| 9 | No `prefers-reduced-motion` | INFO | **stands**, still nothing to reduce |

**One item moved the wrong way**, and it is in "what is working" rather than in the
findings: the `(i)` tooltips were removed wholesale on 2026-10-07 (PR 23765, 443 lines
deleted). The definitions they carried went with them rather than moving anywhere else.
See the amended entry below.

---

## A note on the constraint this review works inside

`plan.md` §3.0 gives the prototype authority over presentation. Several things that would
look like defects in a general audit are deliberate ports, and I have marked those where
I found them. The recommendations are split into three kinds:

- **Free** — no conflict with the prototype; the prototype has no opinion.
- **Costs a decision** — improves the experience but departs from the prototype, so
  someone has to agree to the departure.
- **Already in the plan** — Phase 7 items that are simply not done yet.

---

## What is working, and should be protected

A review that only lists faults will get the good parts refactored away by accident. These
are the things I would defend in a redesign.

**The flag pills encode three ways at once.** `.nv-pill` renders a triangle for flagged, a
filled circle for not-flagged and a hollow circle for ineligible, each with its own colour
*and* a text label (`primitives.css:98–141`). That is the shape-not-colour requirement from
Phase 7 already met, and met better than most products manage. Nobody needs to see colour
to read this table.

**Ineligible is a visible third state.** Forty-four accounts have too few calls to assess,
and the interface says so rather than folding them into "not flagged". Most dashboards
would show 13 of 95 and let the reader draw the wrong conclusion. This one shows 13 of 51
assessed and names the other 44. That discipline is rare and it is the product's main
credibility asset.

**The epistemic chips.** Marking a figure observed vs derived, at the point of reading, is
a design decision most teams never make. Keep it.

**The rail labels are questions, not nouns.** "What are the risks?", "Isolated or
systemic?", "What should we do next?" — each with a one-line sublabel. For an occasional
executive reader this is materially better than Risk / Hierarchy / Actions. See the
trade-off in finding 7.

**Screen-level loading and error are announced.** `Screen.tsx:111` carries `role="alert"`
for failures and `:125` `aria-live="polite"` for loading. The common omission is absent here.

**~~Tooltips carry the definitions.~~ — removed 2026-10-07, and worth a second look.**

The original entry praised moving "what does flagged mean" into an `(i)` rather than into
page prose. PR 23765 removed every tooltip in the product: the `Tooltip` component is
deleted, there are zero imports, and 443 lines went with it.

The definitions did not move anywhere. Searching the frontend for an on-screen
explanation of *flagged*, *quotable*, *derived* or *assessed* now finds only a native
`title=` attribute on `IndicatorCount` — which is mouse-only, invisible to a keyboard
user, and not a substitute.

This is not a defect to reverse on my say-so. It bought a real improvement, and finding 7
is the evidence: `/exec` went from 3,932 px to 2,129 px, and the tooltip removal is a
large part of that. **The question it leaves open is where a first-time reader learns what
"flagged" means.** The product's main credibility asset is that it distinguishes *not
flagged* from *could not be assessed*; a reader who does not know that distinction exists
cannot credit it.

Worth deciding deliberately rather than by omission: a short glossary on `/exec`, a
definition line under each table, or an accepted "the audience already knows these terms".

---

## Findings

### 1. The cold load shows nothing useful for three and a half seconds — HIGH

> **Payload unchanged on 2026-10-08**: `/risk` 204 KB, `/exec` 72 KB, `/rules` 34 KB,
> `/hierarchy` 32 KB, `/filters` 24 KB. The timings below were measured locally and have
> **not** been re-measured — the app is now behind a network, which would compare two
> different things. The structural point stands: the filter bar is still gated on the
> slowest request, and there is still no skeleton.

Measured on `/risk`, locally, with a warm backend:

| | |
|---|---|
| DOM ready | 251 ms |
| `/insights/risk` | **3,507 ms** |
| `/insights/filters` | 3,057 ms (parallel) |
| first table row painted | ~3.5 s |

For that whole period the screen is a heading, a disabled filter bar, and the word
"Loading…" repeated seven times — once in the body and once in each of the six filter
dropdowns. There is no skeleton, no partial render and no progress.

`/insights/risk` is **209 KB**, the largest response in the application by a factor of
three (`/exec` 71 KB, `/rules` 35 KB, `/hierarchy` 33 KB). Stripping `callIds` and
`evidence` only recovers 12%, so the bulk is the 51 assessed accounts with their
conditions and observations, the three thirteen-week strips, and the drivers.

**Why it matters more than the number suggests:** three and a half seconds is past the
point where attention goes elsewhere, and the filter bar being disabled means the first
thing a returning user wants to do — narrow to their region — is the thing they cannot do
until the whole payload lands.

**Fix, free:**
- Render the filter bar enabled and populated from `/filters` the moment it arrives,
  rather than gating it on the slowest request on the page.
- Replace the repeated "Loading…" with a skeleton of the table and tile row. The layout is
  known before the data is; drawing it stops the page reflowing under the reader.
- Paint the KPI tiles as soon as their figures are available instead of waiting for the
  accounts list.

**Fix, costs a backend decision:** split `/insights/risk` so the table's rows arrive
separately from the weekly strips and drivers, or move `callIds` and `evidence` behind a
per-account request. The screen does not need 51 accounts' evidence arrays to paint.

---

### 2. `/risk` is seven screens tall, with 51 rows, no sort and no pager — HIGH

> **Still true on 2026-10-08**, and slightly worse: **6,500 px** (7.2 screens), 51 rows,
> `table th[scope="col"] button` still **0**.

At 1440×900 the page was **6,289 px** — seven viewport heights. The accounts table renders
all 51 rows at once, and:

- `table th[scope="col"] button` → **0**. No column is sortable.
- No pagination.

`/calls` — the same product, two clicks away — has **six sort controls** and a pager with
rows-per-page at 25/50/100. So the application already contains the better pattern and the
risk screen does not use it.

The table is ranked server-side by D12's order (flag, then indicator count, then soonest
renewal), which is the right default. But a reader who wants "biggest books first" or
"renewing this month" has to scroll and scan, and the Lives and Renews columns are sitting
right there inviting a click that does nothing.

**Fix, free:** make the existing columns sortable, reusing the `/calls` sort control. The
server already accepts ordering parameters for the calls table; the same treatment here is
mostly frontend.

**Fix, costs a decision:** paginate at 25 like `/calls`. The counter-argument is real —
this is a ranked list and the ranking is the point, so a pager hides the tail. A middle
path is to keep all rows but make the first screen complete: sticky table header, and the
filter bar sticky so narrowing does not require scrolling back up.

---

### 3. There is no mobile layout — MEDIUM, already in the plan

> **Largely fixed on 2026-10-08.** Re-measured at 375×812 on `/risk`: the rail is now
> **375 px**, `scrollWidth` equals the viewport, and nothing overflows. The measured
> defect is gone. What remains is the page being **8,798 px** tall on a phone, which is a
> question about whether the screen belongs there at all rather than a layout bug.

As measured on 2026-10-06, at 375×812 on `/risk`:

- the navigation rail computed to **1,210 px wide inside a 375 px viewport**
- `.nv-foot`, `.nv-themer`, `.nv-footlink` all overflowed the viewport
- the page was 8,375 px tall

The page itself does not scroll horizontally — overflow is contained — so this is not
broken so much as unconsidered. The smallest breakpoint in the CSS is 700 px; the plan asks
for verification at 320 / 768 / 1440.

**Worth asking before building anything:** who reads this on a phone? If the answer is "a
broker-facing manager checking one account between meetings", the right response is a
single well-made mobile view of `/accounts/:ref`, not a responsive pass over seven dense
analytical screens. If the answer is "nobody", then this finding is a non-issue and the
plan item should be closed as "desktop only, by decision" rather than left open.

---

### 4. The action board does not announce what it just did — MEDIUM

> **Still true on 2026-10-08**: `[aria-live]` on `/actions` returns **0**.

Moving a card between lanes, recording an outcome and logging activity each fire a PATCH
and re-render the board. There is **no `aria-live` region anywhere on the board** — the
only live regions in the application are the two in `Screen.tsx`.

A sighted user sees the card move. A screen-reader user gets silence, and the board is the
one screen in the product that is a workflow rather than a report.

In mitigation, the mutation affordances are good: buttons disable and relabel
(`"Creating…"`, `ActionComposer.tsx:301`) and failures render inline (`:243`). It is
specifically the success path that says nothing.

**Fix, free:** one polite live region on the board, announcing the completed action —
"Moved *Broker conduct* to In progress". About fifteen lines.

---

### 5. No global `:focus-visible` fallback — LOW

> **Still true on 2026-10-08.** `tokens.css` has two `:focus-visible` rules, but both are
> scoped — `select` and `input`. Plain `<a>` elements still match nothing.

Focus styling is defined per component, in 11 rules across 8 files. On `/exec` that covers
the nav, buttons, selects, cards and table rows — but **9 plain `<a>` elements** (8 unclassed
plus `.nv-footlink`) match no rule and fall back to the browser default.

This is not invisible — Chromium draws its own ring — but it is inconsistent, it is not
guaranteed to have contrast against the dark theme, and it will silently regress the first
time someone writes `outline: none` somewhere.

**Fix, free:** one `:focus-visible` rule in `tokens.css` applying the brand ring to
everything focusable, with the per-component rules kept as overrides.

---

### 6. No print stylesheet — LOW, already in the plan

> **Still true on 2026-10-08**: `@media print` across the frontend returns **0**.

`grep -rn "@media print"` over the frontend returns nothing. The prototype's own README
notes these pages get printed in meetings, and the plan lists it as a Phase 7 item. A
dense analytical page printed without a stylesheet will carry the navigation rail, the
theme switcher and the filter dropdowns onto paper, and break tables mid-row.

**Fix, free:** hide the rail, footer and controls; set `break-inside: avoid` on panels and
table rows; print the active filter set once at the top so a printed page says what it is
a view of.

---

### 7. ~~"Executive overview" is four screens of scrolling~~ — FIXED 2026-10-08

> **`/exec` is now 2,129 px at 1440×900 — 2.4 screens, down from 4.4.** A 46% reduction,
> achieved without anyone acting on this finding directly: the tooltip removal and the
> earlier removal of the explanatory paragraph under each page title did it between them.
>
> The panels are now Flagged accounts, Attention insights, What this period means,
> Emerging issues, What is being done. `/actions` came down too, to 2,233 px, helped by
> insight 22's withheld panel being dropped.
>
> The decision this finding asked for — *what are the four things an executive must see* —
> no longer needs taking under time pressure. The paragraphs below are kept because the
> second half is still live.

`/exec` **was 3,932 px** at 1440×900. An overview that cannot be taken in at a glance is a
report, and the product already has reports.

This is the finding I am least certain about, because the page is a faithful port of
`exec.html` and §3.0 gives the prototype the call. But the question is worth putting to
whoever owns that decision: if an executive reads one screen before moving on, what are
the four things they must see? Everything below that line is a different page, or a
progressive disclosure, or an accordion.

Related, and smaller. I expected to find label drift between the rail and the page
headings, and there is none: seven of the eight match word for word, and the eighth
("Isolated or systemic?" in the rail, "Is it isolated or systemic?" as the heading) is a
deliberate pair that an existing test already documents as the prototype's own wording.
That consistency is worth keeping.

The remaining question is whether questions are the right form at all. They are excellent
for a first-time or occasional reader and slower to scan than nouns for someone using this
daily — "How are agents handling calls?" takes longer to find than "Agents" when you
already know what you want. The sublabels mitigate it. This is a genuine trade-off between
two audiences rather than a defect, and the prototype has already chosen; I raise it only
so the choice is a known one.

---

### 8. No skip link — LOW

> **Still true on 2026-10-08**: no skip link in `Shell.tsx`.

Every page puts seven rail links and a theme switcher before the main content. A keyboard
user tabs through all of them on every navigation. One skip link at the top of `Shell.tsx`
fixes it.

---

### 9. No `prefers-reduced-motion` guard — INFORMATIONAL

> **Unchanged on 2026-10-08**: still **0** `transition:` or `animation:` declarations, so
> still nothing to reduce.

There are currently **zero** `transition:` or `animation:` declarations in the frontend, so
there is nothing to reduce and no live problem. I note it only because the first person to
add a transition will not think to add the guard, and adding the empty media query now
costs nothing and makes the omission visible.

---

## Not assessed

I did not test these, and would not want the absence of a finding read as a pass:

- **Colour contrast ratios** against WCAG AA, in either theme.
- **Screen-reader walkthrough** with an actual screen reader. Everything above is inferred
  from markup and live regions, which is not the same thing.
- **Keyboard operation of the action board's modals** — focus trapping, Escape, and
  restoring focus on close.
- **The drawer** (`CallAnalysis`) in any depth.
- **Performance under a corpus larger than 600 calls.** `/risk` at 209 KB is 600 calls;
  the plan targets more, and this is the payload that will degrade first.

---

## What I would do, in order

Revised 2026-10-08. Two items came off the list without being worked on, and one went on.

1. **Make the load feel instant** — enable the filter bar as soon as `/filters` lands,
   skeleton the table, paint tiles early. Biggest perceived-quality gain per hour spent,
   and nothing in the prototype argues against it.
2. **Sortable columns on `/risk`**, reusing `/calls`'s own control. Removes the single
   most obvious dead affordance in the product, and `/risk` is the one screen that did
   not get shorter.
3. **Decide where a reader learns the vocabulary**, now the tooltips are gone. New, and
   ahead of the accessibility items because it affects whether the product's best
   property — distinguishing *not flagged* from *could not be assessed* — lands on a
   first-time reader at all.
4. **A live region on the action board.** Small, and it is the one screen where silence is
   a real failure.
5. **Global `:focus-visible`, and a skip link.** An hour, together.
6. **Print stylesheet.** Named in the plan, genuinely used in meetings.
7. **Decide the mobile question** — cheaper than it was, since the rail now fits and
   nothing overflows. What is left is whether an 8,798 px page belongs on a phone.

~~Put the `/exec` length question to whoever owns the prototype decision.~~ **Closed.**
`/exec` is 2,129 px.

Items 1, 2, 4, 5 and 6 are free of prototype conflict and are, between them, perhaps two
days. Items 3 and 7 are decisions, not work.

---

## Changes since the first review that this document now reflects

Thirty-eight commits. The ones that moved something a reader sees:

| Change | Effect here |
|---|---|
| `(i)` tooltips removed everywhere (23765) | `/exec` and `/hierarchy` much shorter; definitions lost |
| Insight 22's withheld panel dropped from `/actions` (23763) | `/actions` 2,233 px |
| Empty AI surface hidden rather than shown (23767) | no empty card on screens with no insights; **U2 revised** |
| Emerging issues ranked on direction (23733) | `/exec` no longer calls a receding topic "emerging" |
| Account conditions counted against what is checkable (23778) | "1 of 9 (1 not computable)", not "1 of 10" |
| Broker naming caveat reworded twice (23766) | plain-language note under **By broker** |
| Four KPI tiles restyled (23745), Agents insight order (23770) | cosmetic, not re-reviewed |

Deployment also changed: the app now runs on Azure App Service rather than only locally,
which is why the load timings in finding 1 were not re-measured.
