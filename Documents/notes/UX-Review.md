# UX review — NanoVox Insights

**Reviewed:** 2026-10-06, against `main` at `49098cf`, running locally.
**Method:** every screen driven in a real browser at 1440×900 and 375×812. Load timings
from the Performance API, payload sizes from the endpoints, focus behaviour from actual
Tab presses rather than scripted `.focus()` calls, which do not trigger `:focus-visible`
and gave a false reading first time round.

Everything below is a measurement or a line of code, not an impression. Where I did not
test something I say so rather than guessing.

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

**Tooltips carry the definitions.** Moving "what does flagged mean" into an `(i)` rather
than a paragraph of page prose is the right call and matches how people actually read
dashboards.

---

## Findings

### 1. The cold load shows nothing useful for three and a half seconds — HIGH

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

At 1440×900 the page is **6,289 px** — seven viewport heights. The accounts table renders
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

At 375×812 on `/risk`:

- the navigation rail computes to **1,210 px wide inside a 375 px viewport**
- `.nv-foot`, `.nv-themer`, `.nv-footlink` all overflow the viewport
- the page is 8,375 px tall

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

`grep -rn "@media print"` over the frontend returns nothing. The prototype's own README
notes these pages get printed in meetings, and the plan lists it as a Phase 7 item. A
dense analytical page printed without a stylesheet will carry the navigation rail, the
theme switcher and the filter dropdowns onto paper, and break tables mid-row.

**Fix, free:** hide the rail, footer and controls; set `break-inside: avoid` on panels and
table rows; print the active filter set once at the top so a printed page says what it is
a view of.

---

### 7. "Executive overview" is four screens of scrolling — MEDIUM, costs a decision

`/exec` is **3,932 px** at 1440×900. An overview that cannot be taken in at a glance is a
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

Every page puts seven rail links and a theme switcher before the main content. A keyboard
user tabs through all of them on every navigation. One skip link at the top of `Shell.tsx`
fixes it.

---

### 9. No `prefers-reduced-motion` guard — INFORMATIONAL

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

1. **Make the load feel instant** — enable the filter bar as soon as `/filters` lands,
   skeleton the table, paint tiles early. Biggest perceived-quality gain per hour spent,
   and nothing in the prototype argues against it.
2. **Sortable columns on `/risk`**, reusing `/calls`'s own control. Removes the single
   most obvious dead affordance in the product.
3. **A live region on the action board.** Small, and it is the one screen where silence is
   a real failure.
4. **Global `:focus-visible`, and a skip link.** An hour, together.
5. **Print stylesheet.** Named in the plan, genuinely used in meetings.
6. **Decide the mobile question** before building anything for it.
7. **Put the `/exec` length question** to whoever owns the prototype decision.

Items 1–5 are free of prototype conflict and are, between them, perhaps two days. Items 6
and 7 are decisions, not work.
