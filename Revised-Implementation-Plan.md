# NanoVox – Revised Implementation Plan

**Prepared:** 2026-09-24 · **Trigger:** new prototype landed on `main` (PR 23411), now at `Prototype/v2/`
**Status:** analysis and planning only. No development has started against this document.
**Governing documents unchanged:** the v9 workbook wins on definitions; the Account Signals
prototype wins on presentation; `Insights-Worth-Building.docx` wins on scope (`plan.md` §3.0).
`Prototype/v2` replaces the *presentation* authority only. It does not overrule a definition.

---

## 1. Executive Summary

**The backend is much further along than the frontend, and the new prototype does not
invalidate it.** Eight of the nine planned read endpoints are built, tested and typed;
the React app is still the Phase 0 skeleton with a single status page. So `Prototype/v2`
arrives at close to the ideal moment: almost nothing in the UI has to be thrown away,
because almost nothing in the UI exists.

Four findings drive this plan.

1. **Roughly 75% of V2 is servable from endpoints that already exist.** Six of V2's seven
   pages map one-to-one onto a built endpoint. The bulk of the new work is React, not Python.

2. **Three backend gaps are real and are on the critical path.** V2 needs (a) a **period
   filter** — week / month / custom date range — and the API today accepts only `asOf`,
   with every window fixed by `dashboard.yaml`; (b) a **call list and call evidence
   endpoint**, which does not exist at all; (c) an **action write path** — V2's action board
   creates, moves, ticks, logs and completes cards, while `GET /insights/actions` returns
   derived findings with no identity and no status, by design.

3. **Two endpoints are now orphaned and two screens are now homeless.** V2 drops `rules.html`
   from the rail entirely and has no demand page — yet `/insights/rules` and `/insights/demand`
   are built and carry insights 15–19 and 23–27. Conversely `/value-pack` (insights 30–32) has
   no V2 page and no endpoint. This is a scope question for Minnie, not a technical one.

4. **The most important conflict is what the word "flagged" names.** V2 calls an account
   flagged when two or more indicator families fired; `config/dashboard.yaml` (decision **D2**)
   says metric 10's flag is two or more of its own four named conditions, and that the families
   are informational and never set it. **These are different populations of accounts sharing one
   word.** V2's four-level band turns out to be a pure presentation of the family count, and what
   V2 actually consumes — a boolean and a count — already exists in `RiskAssessment.flagged` and
   `indicators.observe`. So this is cheaper than a rival risk model but more dangerous than a
   styling choice: it is a vocabulary collision on the one figure that names an account.

A fifth point is not a prototype issue but bounds everything: **Phase 5 run 1 reports L3 at
38% and L4 at 19% agreement.** The fields V2 leans on hardest — signals, touchpoint, process
gap, quality score — are the ones the extraction is currently worst at. The screens can be
built; what they are pointed at in a demo is a separate decision that `Phase-5-Findings.md`
already puts in front of Minnie.

**Recommended shape:** two verticals — **V1 Backend / data / business logic** and
**V2 Frontend / UI** — running in parallel across **seven phases**, with the design system
(zero backend dependency) starting immediately so the frontend is never blocked waiting on
an endpoint. Integration is enforced by an existing gate: the typed client must regenerate
from the backend's own OpenAPI document with **zero diff**, so every contract change is
caught by CI rather than by a developer.

---

## 2. Current Implementation Assessment

### 2.1 What is built

| Layer | State |
|---|---|
| **Domain — entities, value objects** | Complete (Phase 1). Sixteen Call Tag Schema fields modelled, reference data imported from the workbook, counts reconcile (95/30/285/101/20/122/12). |
| **Domain — aggregation** | 20 modules. Figures, filters, indicators, risk flag, contact rate, repeat contact, touchpoints, broker friction, isolation, demand, rules, agent events, actions, exec scorecard, patterns, withheld panels. |
| **Application — ports & use cases** | 24 ports, 13 use cases. `read_insights.py` carries eight insight use cases behind one `InsightsReader.scope()`. |
| **Infrastructure** | Async SQLAlchemy + Alembic (single head), LLM providers (OpenAI / Anthropic / Ollama), corpus readers, `SqlInsightsSource`. |
| **API** | FastAPI. 16 operations: health, ingest, reference import, providers, 4 run operations, **8 insights read endpoints**. camelCase keys, RFC 9457 errors, correlation IDs. |
| **Frontend** | **Phase 0 skeleton only.** Vite + React 18 + TS + React Router + TanStack Query. One route (`/`), one page (`StatusPage`), a typed client generated from OpenAPI, a query client with retry policy. **No design system, no screens.** |
| **Pipeline** | L1 (deterministic) + L2 + L3 + L4 built, orchestrated by `run_extraction_pipeline.py`. Evaluation harness complete; run 1 executed 2026-09-24 over 100/100 calls. |

### 2.2 The eight read endpoints

| Endpoint | Returns |
|---|---|
| `GET /insights/exec` | Scorecard: per-metric `Figure`s with their own `windowWeeks`, escalation pair (integrity + the misleading denominator beside it), intent routed |
| `GET /insights/risk` | Per-employer assessment, conditions met, observations, ineligible list, flagged share, exposure (lives + premium) |
| `GET /insights/accounts/{employer_ref}` | Account facts, contact rate vs size-band peer median, repeat rate, embedded risk assessment |
| `GET /insights/hierarchy` | Region → broker → employer drill tree, region × category matrix, systemic categories, ranked broker friction with the pattern test shown fired **and** unfired |
| `GET /insights/demand` | Self-inflicted demand split three ways (never blended), complaints about us, touchpoint ranking with attribution, unattributed bucket, enrolment promise gaps in minutes |
| `GET /insights/actions` | Derived action items (signal, severity, owner team, call ids), owner workloads, control exceptions, the `didItWork` withheld panel |
| `GET /insights/rules` | Rules we fail to explain, by rule / layer / area / provenance / touchpoint, with "commonly confused with" |
| `GET /insights/agents` | Per-agent events, knowledge error rate, quality range with coverage caveat |

### 2.3 Cross-cutting properties already enforced

These are not aspirations; they are tested and gated in CI.

- **Withheld ≠ zero.** Every figure carries `published`, `n`, `epistemic`, `withheldReason`, `caveats`, `callIds`.
- **Filters slice, never hide.** `FilteredCalls` returns `considered`, `unmeasurable` and `applied` alongside the calls.
- **No circular scoring.** `test_no_circular_scoring.py` fails if any aggregation so much as *names* `design_churn_profile` — including in a comment.
- **Clean Architecture.** Five `import-linter` contracts, including one that keeps `domain.aggregation` from reading `domain.entities` or `domain.extraction`.
- **Computed caveats.** Caveat text is generated from the numbers, never hand-written.
- **Gates.** `ruff format --check`, `ruff check`, `mypy --strict`, `lint-imports`, pytest at 85% branch coverage, single Alembic head; frontend eslint, `tsc`, vitest, and the typed client regenerated with **zero diff**.

### 2.4 What is deliberately not built

| Thing | Why |
|---|---|
| `/value-pack` (insights 30–32) | Ninth endpoint, never started. Insights 30, 31 and 32 are PARTIAL in `plan.md` §9. |
| Insight 7, broker-of-record drift | `CallContext` carries both `broker_named_aloud` and `broker_of_record_ref`; nothing compares them. Left out rather than defined in a router. |
| Action write path (Phase 9, D6) | `ActionItem` has **no status field** on purpose — there is no write path, so a status would be fiction. |
| `/catalogue`, `/diagnostics`, `/calls` | Phase 8 / Phase 10, not started. |
| WITHHELD insights 6, 9, 17, 25, 26 | No gate unlocks them. Only a v9→v10 schema change Karim has not made. |

### 2.5 Open items carried in

From `Open-Decisions.md`, still unresolved: `EpistemicClass` shape (recommendation: split
`basis` from `published`), `indicators.min_rate: 0.2` (recommendation: source it or drop it),
and `caller_type` not being one of the sixteen schema fields. All three now touch V2 directly.

---

## 3. New Prototype Assessment

`Prototype/v2/` is **10 files, 240 KB**, static HTML/CSS/JS. It is a *layer*, not a
replacement: it loads `../data.js`, `../app.js` and `../app.css` from `Prototype/` and adds
only `nv2.js` (742 lines) and `v2.css` (530 lines). **It is not self-contained** — deleting
`Prototype/` breaks it.

### 3.1 The seven pages

| File | Rail label | Sub-label | Purpose |
|---|---|---|---|
| `exec.html` | Executive overview | The period at a glance | Alert feed, 4 tiles, went-well/concern, AI lenses, emerging issues, action progress strip |
| `index.html` | What are the risks? | Accounts, drivers, signals | Accounts at risk, drivers, outcomes, weekly trend, new-or-rising |
| `employer.html` | Insights & patterns around employers | One account at a time | Account facts, indicators, calls, actions for one employer |
| `actions.html` | What should we do next? | Steps, owners, progress | Focus panel, issues list, **Trello board**, card modal, composer |
| `hierarchy.html` | Isolated or systemic? | Region, broker, account | Region table, topic heatmap, broker table |
| `agents.html` | How are agents handling calls? | Conduct events | Events by agent, coach-or-fix-the-rule, experience bands |
| `calls.html` | All calls | Browse, filter, export | **New.** Search, sort, page, select, 26-column CSV download |

`rules.html` **does not exist in V2** and is not referenced from it.

### 3.2 What V2 changes, in its own words

Taken from `Prototype/v2/README.md` and verified against the code:

- Pages are **named as questions**, each with a one-line plain-English subtext.
- Explanations moved into **(i) tooltips**. No table is wider than six columns.
- **The scope line and "Copy link" are gone.** Advanced filters sits next to Reset all.
- **Every red or orange number links to `actions.html?focus=<issue>`** — one click from any
  bad figure to what it means, the recommended steps, a suggested owner, the accounts and
  calls behind it, and any action already in progress.
- **AI insights are one clearly marked surface per page**: a feed on the executive overview
  (cards expand to evidence + "What to do"), and a strip elsewhere.
- **Cost-to-serve is removed.**
- The executive overview no longer repeats the risks page.
- The action board is **Trello-style**, with labels, due badges, owner avatars, a checklist,
  the calls behind the card, an activity timeline and "Move to". Moves are in-memory only.
- Charts are drawn at **real pixel size** (`NV.vbars`, `NV.vline`), so labels stay 12px at any
  width. Weeks with no calls show as **gaps, not zeros**.
- Cards can be **created, ticked off, updated and completed**; changes persist to
  `localStorage` under `nvx-actions-v2`.
- `calls.html` lists every call and downloads a **26-column CSV**.
- Footer source notes moved into each page title's (i) tooltip under "About this data".

### 3.3 The three genuinely new mechanisms

**`NV.PLAYBOOK`** — seventeen named issues, each with `label`, `unit`, `owner`, `sev`,
`meaning`, `why`, recommended `steps`, and a predicate selecting the calls / accounts / actions
behind it. Plus `NV.pb(key)` which *synthesises* a playbook on demand for
`tp_<touchpoint>`, `cat_<category>`, `sig_<signal>` and `pl_<product line>`. This is the
spine of V2: it is what makes every number clickable and every click land on advice.

**AI insight surfaces** — three components: `NV.insightFeed` (executive, expandable),
`NV.insightStrip` (2–4 cards, other pages), and a four-lens grid on the executive page
(Employers · Churn & retention · Product & service · Payer & carrier), three insights each.
All copy is **templated over figures computed in the page**, with `PRODUCTION:` comments
marking where a model call goes. The README is explicit and correct about the contract:
*"Pass it the same computed facts and ask it to summarise, never to calculate"* and
*"If an insight and a figure ever disagree, the figure is right."*

**The action board write path** — `NV.actStore` / `actSave` / `actCreate` persist edits to
browser storage: status moves across seven lanes, checklist ticks, logged updates with
timestamps, owner and due-date edits, `action_taken` and `outcome` text, and a composer that
creates a card prefilled from a playbook with the calls behind it pre-linked.

### 3.4 Data V2 reads

`data.js` (`window.NVX`, 429 KB) carries 15 top-level collections. Several have **no backend
equivalent**: `drivers` (10, with 3 buckets each), `emerging` (14, with delta), `friction`
(7 topics), `qwa` (5 trigger rules), `snippets` (100 transcript extracts), `series`
(10 weekly series), `buckets`, and `actions` (25 seeded workflow items with owner, due,
status, action_taken, outcome).

`calls` carries 48 fields per call, of which several are not among the sixteen schema fields:
`archetype`, `effort` / `effort_band`, `complexity` / `complexity_band`, `turns`, `hour`,
`member_age`, `authority`. `employers` carries `band`, `indicator_families`, `structural`,
`minutes_per_life`, `annual_minutes`, `trend`, and **`design_churn_profile`**.

---

## 4. Current vs. New Prototype Comparison

### 4.1 Page-to-endpoint map — the crux table

| V2 page | Endpoint today | Fit | What is missing |
|---|---|---|---|
| `exec.html` | `GET /insights/exec` | **Partial** | Alert feed, four lenses, emerging issues, drivers, noise test, action progress, went-well/concern |
| `index.html` | `GET /insights/risk` | **Good** | Drivers panel, weekly series, new-or-rising, four-level band |
| `employer.html` | `GET /insights/accounts/{ref}` | **Good** | Per-account calls list, per-account actions, `design_churn_profile` disclosure |
| `hierarchy.html` | `GET /insights/hierarchy` | **Good** | Region summary counts are derivable from the tree |
| `agents.html` | `GET /insights/agents` | **Good** | Experience bands, expected score, coach-or-fix-the-rule rollup |
| `actions.html` | `GET /insights/actions` | **Weak** | Identity, status, owner, due, checklist, activity, outcome — the whole write path |
| `calls.html` | — | **None** | Entire endpoint: list, search, sort, page, evidence, export |
| *(dropped)* rules | `GET /insights/rules` | **Orphaned** | Endpoint built, no screen consumes it |
| *(absent)* demand | `GET /insights/demand` | **Orphaned** | Endpoint built, no screen consumes it |
| *(absent)* value pack | — | **Neither** | Insights 30–32 have no home in either |

### 4.2 UI / UX differences

| Dimension | Prototype V1 | Prototype V2 | Consequence |
|---|---|---|---|
| Page naming | Module names | Questions + subtext | Copy change; rail component |
| Explanations | Inline prose, footer source lines | (i) tooltips, viewport-positioned | New `Tooltip` primitive; `pageHead` carries "About this data" |
| Table width | Unbounded | **≤ 6 columns** | Column budget per screen; some V1 tables must shed columns |
| Scope line | Always shown | **Removed** | Conflicts with a stated safety practice — see §5.1 |
| Copy link | Present | **Removed** | URL should stay the source of truth regardless |
| Bad numbers | Static | **Clickable → `actions.html?focus=`** | Every figure needs a stable issue key |
| Charts | Fixed viewBox, scaled | Real pixel size, redrawn on resize, null = gap | New chart primitives; do not port V1's |
| Sticky behaviour | None | Sticky page head + sticky table header with hysteresis | Layout primitive |
| Theme | 3-way, light default | Unchanged | Reusable as-is |
| Cost-to-serve | `exec.html` §5 | **Removed** | Conflicts with `plan.md` §9 insight 15 — see §5.1 |

### 4.3 New screens and workflows

- **`/calls`** — full corpus browse, search across seven fields, sort on six columns, 25/50/100
  paging, row selection, and CSV export of filtered **or** selected calls with 26 columns.
- **Focused action view** — `actions.html?focus=<issue>[&employer=<ref>]` renders the issue's
  meaning, why it matters, recommended steps, suggested owner, the evidence behind it, and
  actions already in progress against it.
- **Action composer** — creates a card from a playbook with steps and calls pre-linked.
- **Card detail** — always shows *the single next move*; checklist with progress bar; forms for
  "what was done" and "what changed"; activity timeline; "Move to" lane buttons.

### 4.4 Removed or changed functionality

| Removed | Currently built | Recommendation |
|---|---|---|
| Rules page | `/insights/rules` (insights 23, 24, 27) | **Keep the endpoint. Decide the screen.** `plan.md` §8 says rules should be **in the nav, not hidden**. V2 removed it entirely. |
| Cost-to-serve tile | `demand.cost_to_serve`, plan §9 insight 15 View 2 | **Keep on `/demand`, drop from `/exec`.** V2 is the presentation authority; `/exec` placement was Ranjit's own, not the docx's. |
| Scope line | `FilteredCalls.considered` | **Keep the count, drop the row.** See §5.1. |
| Copy link | — | Safe to drop; keep URL-as-source-of-truth. |

### 4.5 Analytics and business-logic changes

| V2 computes | Exists today? |
|---|---|
| 4-week vs prior-4-week comparison with a **z-test for noise** (`noiseTest`) | No. `patterns.normalised_rate` is the nearest building block. |
| **Drivers** — 10 coded drivers with 3-bucket trend, employer count, top category | No |
| **Emerging issues** — rising/easing across touchpoint, category, signal, product line | Partial. `patterns.time_aggregate` exists; the bucket-delta rollup does not. |
| **Friction by topic** — calls, warranted, handled, unresolved per category | Partial, from existing pieces |
| **Archetype split** — Brush-off, Circular, etc., flagged adverse | No. **Not one of the sixteen schema fields.** |
| Industry / sponsorship / caller-type flag-rate comparisons (exec lenses) | No |
| Escalation integrity gauge | **Yes** — `exec_scorecard.escalation_integrity_pair` |
| Peer comparison, repeat rate, contact rate | **Yes** |
| Indicator families per employer | **Yes** — `indicators.observe` |
| Member effort / complexity bands | **Yes** — `domain/derivations/member_effort_complexity.py` |

### 4.6 Reusable without change

The entire domain layer, all 24 ports, all 13 use cases, the 8 routers' internals, the
envelope (`FigureResponse` / `ScopeResponse` / `AppliedFilterResponse` / `UnmeasurableResponse`),
the label map (`labels.py`, 8 enums, completeness-tested), `CamelModel`, the filter model,
error handling, middleware, the SPA mount, the whole gate suite, and every test. Nothing in
this document proposes deleting backend code.

---

## 5. Functional Gap Analysis

### 5.1 Conflicts — decide before building

These are places where V2 and a governing document disagree. Each needs a ruling.

| # | Conflict | V2 says | The build says | Recommendation |
|---|---|---|---|---|
| **C1** | **What "flagged" names** | An account is **flagged** when **two or more indicator families** fired. `NV.bandFor(n)` is a pure function of that count — `0 None · 1 Watch · 2 Elevated · 3+ High` — and `NV.isFlagged` is simply `n >= 2`. | `dashboard.yaml`, decision **D2**: metric 10's flag is **≥2 of its own four named conditions**, and the ten indicator families are **informational and never set it**. | **Not band-versus-flag — a vocabulary collision.** Counting usage, V2 wants a boolean (~11 uses) and a count (~18), which `RiskAssessment.flagged` and `indicators.observe` already provide; the four-level pill is ~6 cosmetic uses. The real problem is that **both systems use the word "flagged" for different populations of accounts**, and a reader cannot tell which. `dashboard.yaml` predicts exactly this: *"Two scoring systems on one page, one of which quietly feeds the other, is how a yes/no flag turns back into a band."* **Hold D2 for the flag, render the family count beside it as V2 does, and give the two different words.** Response shapes barely move; the change is mostly naming. |
| **C2** | **Applied-filters row** | Scope line removed. Only removable chips remain. | `plan.md` §9 Practices: *"Filters slice, never hide — the applied-filters row always shows scope and count."* | **Split the difference.** Adopt V2's chip row, and keep the call count in the page head. The practice is about not hiding what was excluded, not about that specific row. |
| **C3** | **Epistemic vocabulary** | Six chips: OBSERVED, REFERENCE, DERIVED, PATTERN, INFERENCE, RECOMMENDATION. | `EpistemicClass` has three: MEASURED, DERIVED, WITHHELD. | **Resolve now, with `Open-Decisions.md` item 2.** V2's AI surfaces need INFERENCE and RECOMMENDATION to label themselves honestly, which makes the existing enum insufficient rather than merely debatable. Recommended shape: `basis` (OBSERVED / REFERENCE / DERIVED / PATTERN / INFERENCE / RECOMMENDATION) alongside the `published` flag and `withheldReason` the response already carries. **This is the last cheap moment** — it is in eight response schemas and the generated client today, and in every consumer once screens exist. |
| **C4** | **`design_churn_profile` on screen** | `employer.html` shows it in a tooltip, correctly labelled as the label the data was generated from and explicitly kept out of the band. | `test_no_circular_scoring.py` fails if any aggregation names the field; `EmployerFacts` deliberately does not carry it. | **Decision needed.** Showing it as a disclosure is defensible; carrying it through the aggregation layer is not. If it ships, it must reach the UI on a path that bypasses `domain/aggregation` entirely and the test's allow-list must be extended deliberately, with the reason recorded. Recommend **not shipping it** for now — the disclosure it makes can be made in prose without the value. |
| **C5** | **Rules screen dropped** | No `rules.html`, not in the rail. | `plan.md` §8: `/rules` is **in the nav, not hidden**; insights 23, 24, 27 live there. | **Minnie's call.** Technically free either way — the endpoint stands regardless. Recommend keeping a `/rules` route reachable from `/agents` ("coach the agent, or fix the rule?" already links that way conceptually) even if it is off the main rail. |
| **C6** | **Demand screen absent** | Content partly folded into exec lenses and index drivers. | `/insights/demand` is built; insights 15–19 live there; §9 records that the docx places insight 15 on "Screen 3 of 7". | **Minnie's call.** Recommend keeping `/demand` as a screen — insight 16's touchpoint ranking and insight 19's compliance exposure have no other home, and the exec lens only summarises them. |
| **C7** | **Cost-to-serve removed** | Gone. | Insight 15 View 2, min n 30, minutes never money. | **Accept the removal from `/exec`; keep it on `/demand`.** |
| **C8** | **`archetype`, `effort`, `complexity`, `caller_type`** | Used as first-class filters and figures. | `archetype` and `caller_type` are **not among the sixteen schema fields**. Effort and complexity exist as *our* derivations and §9 insight 29 requires they always be labelled as our composites. | **Effort/complexity: build, labelled.** **Archetype: needs a source.** If it has none in the workbook it is a new derivation requiring its own definition and its own label, or it is dropped. Do not infer it silently. **`caller_type`: already open** in `Open-Decisions.md`. |

### 5.2 Gaps — build, no conflict

| # | Gap | Size |
|---|---|---|
| **G1** | **Period filter** (week / month / custom range). `InsightsQuery` has `asOf` only; `CorpusQuery` has `since`/`until` but `corpus_query()` does not populate them. Every window comes from `dashboard.yaml`. | **Large.** Touches all 8 endpoints, the query model, the source port and the scope echo. |
| **G2** | **`/calls` list endpoint** — search, sort, page, and a stable projection matching the 26 CSV columns. | Medium |
| **G3** | **Call evidence endpoint** — transcript turns for the drawer (`NV.callEvidence`). Turns are stored; nothing serves them. | Medium. **Carries label-stripping risk** — see §13. |
| **G4** | **Action write path** — persisted actions, seven lifecycle states, checklist, activity log, owner/due, `action_taken`, `outcome`. This is `plan.md` Phase 9 / decision **D6**, already scoped. | **Large** |
| **G5** | **Playbook catalogue** — 17 static issues plus 4 synthesised families. Content, not computation. | Medium. Belongs in `config/`, versioned like `dashboard.yaml`. |
| **G6** | **AI insight generation** — templated today, model call in production. LLM infra, provider registry and prompt loading all already exist and are reusable. | Medium |
| **G7** | **Trend & movement analytics** — weekly series, 3-bucket emerging, drivers, noise test, friction by topic. | Medium |
| **G8** | **CSV export** | Small, once G2 lands |
| **G9** | **`/value-pack`** — the ninth endpoint, insights 30–32, all PARTIAL. Has no V2 page either. | Medium, **and currently unjustified** — see §14 |
| **G10** | **Insight 7, broker-of-record drift** — both fields present, no comparison. | Small |

---

## 6. Technical Gap Analysis

### 6.1 API contract

**Query parameters.** `InsightsQuery` is the single filter model across all eight endpoints —
a deliberate design so nine screens cannot quietly disagree about what a filter means. V2's
filter bar needs additions:

| V2 control | Parameter today | Action |
|---|---|---|
| Period: week / month / custom | **none** | **Add `from` / `to`** (ISO dates). Keep `asOf`. Reject `from > to` at the edge with a 422. |
| Region, broker, employer, agent | ✅ | — |
| Category, product line, touchpoint, outcome, signal, intent, complaint target, quality band | ✅ | — |
| Escalation, repeat, compliance | Partial (`escalated`, `complianceException`) | **Add `repeat`** |
| Risk band | **none** | Depends on **C1** |
| Handling (archetype) | **none** | Depends on **C8** |
| Member effort, complexity | **none** | Add once C8's labelling rule is settled |
| Caller type | **none** | Depends on the open `caller_type` item |
| Action status | **none** | Arrives with **G4** |

**Window semantics.** This needs stating explicitly before anyone writes code, because it is
the single most likely source of two developers building different things: **a period filter
narrows the corpus; it does not redefine a metric's window.** `dashboard.yaml` sets
`window_weeks` per metric — 4 weeks for first-contact resolution, 12 for contact rate, on the
same screen. The plan already fixed a bug where `window_weeks` was parsed and read by nothing.
Adding `from`/`to` must not resurrect it. **Decided 2026-09-24 by Ranjit; recorded as D11 in
`plan.md` §5:**

> `from`/`to` bound which calls enter the corpus slice. Each metric's own `window_weeks`
> then applies within that slice, anchored on `asOf`. Where a metric's window is wider than
> the requested period, the response says so in `caveats` rather than silently truncating.

**Response shape changes.** Two are breaking and should land together in one release, since
both force a client regeneration: **C1** (what "flagged" names) and **C3** (epistemic vocabulary).

### 6.2 Architecture impact

`import-linter` keeps `domain.aggregation` free of `domain.entities` and `domain.extraction`.
Three of the new pieces need placing carefully:

- **Trend analytics (G7)** → `domain/aggregation/trends.py`. Pure, no new dependencies.
- **Playbooks (G5)** → `config/playbooks.yaml` + `infrastructure/config`. They are *content*
  with a predicate; the predicate maps to an existing indicator or filter, so nothing new
  enters the domain.
- **Actions write path (G4)** → new entity + repository port + use cases. This is the first
  **write** path in the insights surface and the first place a user edits state. It belongs in
  `domain/entities` and `application/use_cases`, **not** in `domain/aggregation`, whose
  contract forbids reading entities.
- **AI insight generation (G6)** → an application-layer use case over `LLMProvider`, taking
  already-computed figures as input. **It must never touch the corpus or recompute anything.**
  Recommend a contract test asserting the insight service's only inputs are response DTOs.

### 6.3 Data model

| Need | State |
|---|---|
| Transcript turns | Stored (`CallRow` + explicit turn insert). Not served. |
| `control_exceptions` on extractions | Column shipped (PR 23393). `SqlInsightsSource` reads it. |
| Actions table | **Does not exist.** Phase 9 scope is already written in `plan.md`. |
| Playbook / issue registry | Does not exist. |
| Derived trend series | Compute on read; no new tables. |
| `design_churn_profile` | Stored on the employer entity, deliberately walled out of aggregation. |

### 6.4 Frontend

Everything from §3 of `plan.md` Phase 7 still stands and none of it is built. V2 changes the
*specification* of three items: the filter bar (chips, no scope row, Advanced beside Reset),
the charts (real pixel size, redraw on resize, null as gap), and the tooltip (viewport-positioned
so a scrolling panel cannot clip it). Take V2's versions.

**Do not port `app.js`.** It is 926 lines of imperative DOM string-building against a global
`NV`. Port the *behaviour* — `NV.INDICATORS`, `NV.QUALITY_BANDS`, `NV.ARCHETYPES`,
`archetypeSplit`, `deltaChip`, `bandPill`, `drawer`, `callEvidence`, theme handling — as typed
React modules with tests. The prototype is the specification, not the source.

---

## 7. Reuse vs. Modify vs. New Development

### Reuse unchanged — no work

Entire domain layer (entities, value objects, 20 aggregation modules, derivations, scoring,
evaluation) · all 24 ports · all 13 use cases · the `read_insights` reader · the response
envelope · `labels.py` · `CamelModel` · error handling, middleware, correlation IDs · the SPA
mount · Alembic setup · LLM providers and prompt infrastructure · `scripts/check.sh` and every
gate · the whole test suite · the theme system and design tokens from `app.css`.

### Modify

| Component | Change | Effort |
|---|---|---|
| `frameworks_drivers/api/v1/insights/query.py` | Add `from`/`to`, `repeat`, and whatever C1/C8 settle | S |
| `application/ports/insights_source.py` + `SqlInsightsSource` | Populate `CorpusQuery.since`/`until`; echo the period into scope | S |
| `application/use_cases/read_insights.py` | Thread the period through `scope()`; add the window-vs-period caveat | M |
| `domain/aggregation/figure.py` | Epistemic split, if C3 is accepted | M — touches 8 schemas + client |
| `domain/aggregation/risk_flag.py` + `risk.py` | Whatever C1 settles — mostly naming, since the boolean and the family count both exist | S |
| `exec_scorecard.py` (domain + router) | Add movement, drivers, emerging to the exec payload | M |
| `domain/aggregation/actions.py` | Split derived findings from persisted actions | M |
| `plan.md` §8 screens table, §9 statuses | Reflect the decisions taken here | S |

### New — backend

`domain/aggregation/trends.py` (weekly series, 3-bucket rollup, noise test, drivers, friction) ·
`config/playbooks.yaml` + loader · `GET /insights/calls` · `GET /insights/calls/{id}` (evidence) ·
CSV export · `domain/entities/action.py` + repository + migration · `POST` / `PATCH /insights/actions`
· insight-generation use case + prompt · `GET /insights/value-pack` (if approved) · insight 7.

### New — frontend

Everything. Design system (tokens, theme, shell, ~13 primitives, 6 chart types, tooltip,
drawer, filter bar), then seven screens, the action board and card modal, the calls table and
CSV trigger, and the AI insight components.

---

## 8. Revised Architecture / Component Impact

```
Code/Backend
  domain/
    aggregation/          MODIFY  figure(C3), risk_flag(C1), exec_scorecard(+movement), actions(split)
      trends.py           NEW     weekly series · 3-bucket rollup · noise test · drivers · friction
    entities/
      action.py           NEW     persisted action: lifecycle, checklist, activity, outcome
  application/
    ports/
      insights_source.py  MODIFY  period is populated, not just declared
      action_repository.py NEW
    use_cases/
      read_insights.py    MODIFY  period threading + caveat
      list_calls.py       NEW
      read_call_evidence.py NEW
      manage_actions.py   NEW     create · move · tick · log · assign · complete
      generate_insights.py NEW    figures in, prose out. Never recomputes.
  infrastructure/
    persistence/          NEW     actions table + migration; call list query
    config/               NEW     playbooks.yaml loader
  frameworks_drivers/api/v1/insights/
    query.py              MODIFY  from · to · repeat · (band · handling · effort · complexity · callerType, pending C1/C8)
    calls.py              NEW
    value_pack.py         NEW     (pending §14 approval)
    actions.py            MODIFY  read stays; write added

Code/Frontend/src
  shared/design/          NEW     tokens · theme · 13 primitives · 6 charts · tooltip · drawer
  shared/filters/         NEW     URL-as-truth · chips · Advanced disclosure
  features/exec|risk|account|hierarchy|agents|calls|actions|demand|rules   NEW
  shared/api/schema.ts    REGENERATED on every contract change — zero-diff gate
```

---

## 9. Phase-Wise Implementation Plan

Seven phases. **Phase 0 is decisions and blocks the two breaking changes only.** Vertical 2
starts real work on day one regardless, because the design system has no backend dependency.

Every phase inherits the standing rules from `plan.md` §2: one commit per task, never amend,
never force-push, never commit to `main`, and all gates green before every commit.

---

### Phase 0 — Alignment and decisions
**Objective:** close the eight conflicts in §5.1 so nobody builds twice. **No production code.**

#### Vertical 1 (Backend)
- Prepare a one-page decision brief per conflict: what V2 wants, what the workbook says, the
  cost of each option **now** vs **after the screens exist**.
- Prototype C3 (epistemic split) as a **throwaway branch** to price the change honestly:
  count the schemas, the client diff and the test churn. Do not merge it.
- Count stored rows affected by C4 and by the stricter value-object constructors already
  agreed in `Open-Decisions.md` §5.
- **Deliverable:** decision brief; a costed C3 estimate; a written window-vs-period rule.

#### Vertical 2 (Frontend)
- Extract the V2 design contract into a written spec: token list from `app.css` `:root` and
  both dark blocks, the seven type scales in `v2.css`, the six chart types, tooltip placement
  rules, sticky-head hysteresis, the ≤6-column table rule.
- Inventory `app.js` + `nv2.js` and classify every helper as **port**, **replace** or **drop**.
- **Deliverable:** design-system spec; a helper-porting inventory.

#### Integration
One joint session with Minnie on the eight conflicts, run against the decision log in §14.
**C1 and C3 must be answered.** G1 (period vs window) is already settled — decided 2026-09-24,
recorded as D11 in `plan.md` §5 — so Phase 1 is unblocked. C5, C6, C7 and G9 (the value pack) can be deferred to Phase 6 without
blocking anything.

#### Testing / Definition of Done
Every one of §14.1's eleven blocking items marked **decided**, or **explicitly running on its
stated default with a named owner and a phase**. `plan.md` §8/§9 updated to match. Nothing
left in "we'll see" — a default taken by silence is recorded as one.

#### Expected outcome
Both verticals can work for six phases without needing to re-open a definition.

---

### Phase 1 — Foundations: period filtering and the design system
**Objective:** unblock every screen. The period filter is the one API change every page needs;
the design system is the one frontend asset every page needs.

#### Vertical 1 (Backend)
- **Tasks:** add `from` / `to` to `InsightsQuery` with edge validation; populate
  `CorpusQuery.since` / `until`; thread the period through `InsightsReader.scope()`; echo the
  resolved period into `ScopeResponse`; emit the computed caveat where a metric's
  `window_weeks` exceeds the requested period; add the `repeat` filter.
- **Modules:** `query.py`, `insights_source.py`, `SqlInsightsSource`, `read_insights.py`,
  `envelope.py`, `filters.py`.
- **APIs:** all eight endpoints gain `from` / `to` / `repeat`. No response shape change yet.
- **Dependencies:** the window-vs-period rule from Phase 0.
- **Deliverables:** period filtering live on all eight endpoints; regenerated `openapi.json`
  and `schema.ts`; tests covering undated calls (already a known trap — `occurred_at IS NULL`
  must survive both bounds), tz-aware bounds for Postgres, and the wider-window caveat.

#### Vertical 2 (Frontend)
- **Tasks:** tokens and three-state theme stamped before first paint; app shell and rail with
  question labels and subtexts; primitives — `Panel`, `KpiTile` (crit/warn/good/withheld),
  `Tile`/`BigRow`, `EpistemicChip`, `BandPill` (shape-coded, never colour alone),
  `SeverityLabel`, `Delta`, `Claim`, `Quote`, `Empty`, `Note`, `Withheld`, `Tooltip`,
  `StickyHead`, `DataTable` (≤6 columns, sticky header); charts — `VBars`, `VLine`,
  `Sparkline`, `MiniBars`, `BarCell`, `Heatmap`, `Gauge`, all measuring their container and
  redrawing on resize, null rendered as a **gap**; the evidence `Drawer` with Back.
- **APIs:** none. Storybook-style fixtures only.
- **Dependencies:** the design spec from Phase 0.
- **Deliverables:** a tested design system; every primitive with a vitest test; charts
  verified at 320px, 768px and 1440px.

#### Integration
None required — this is the point. The two verticals do not touch each other in Phase 1.

#### Testing / Definition of Done
Backend: period filter proven against undated calls, tz-aware bounds, and a metric whose window
is wider than the period. Frontend: 100% of primitives under test; theme switch does not flash;
charts keep 12px labels at every width. **Both:** `./scripts/check.sh` green, client regenerates
with zero diff.

#### Expected outcome
Screens can be built. Data can be sliced by period.

---

### Phase 2 — The four read screens that already have endpoints
**Objective:** ship `/exec`, `/risk`, `/accounts/:ref`, `/hierarchy` on real data.

#### Vertical 1 (Backend)
- **Tasks:** apply the C1 and C3 decisions (both breaking, land together); build
  `domain/aggregation/trends.py` — weekly series, 3-bucket rollup with delta, the noise test,
  drivers, friction by topic; extend `/insights/exec` with movement, drivers and emerging;
  add the region rollup `/insights/hierarchy` needs for V2's region table; insight 7
  (broker-of-record drift) onto the account response.
- **Modules:** `trends.py` (new), `figure.py`, `risk_flag.py`, `exec_scorecard.py`,
  `isolation.py`, the four routers.
- **Dependencies:** Phase 1 period filter; Phase 0 C1 + C3 rulings.
- **Deliverables:** four endpoints serving everything their screens need; one coordinated
  breaking release; regenerated client.

#### Vertical 2 (Frontend)
- **Tasks:** the filter bar — URL as source of truth, mirrored to localStorage, chip row,
  Advanced disclosure with an active count, period segmented control; the four screens;
  `NV.act` equivalent — a typed `issueHref(key, extra)` so every red or orange number links
  to the focused action view (which lands in Phase 4; until then it routes to a placeholder).
- **Dependencies:** Phase 1 design system; the C1 ruling changes `BandPill`'s contract.
- **Deliverables:** four screens matching their V2 page, filters narrowing them, withheld
  states rendering withheld, every figure opening its evidence, keyboard-operable rows.

#### Integration
**Checkpoint I1 — the breaking release.** C1 and C3 ship in one backend commit; the frontend
regenerates the client in the same working session. Verticals must synchronise here: do not
land C1 and C3 separately, and do not land them while a frontend branch is mid-screen.

#### Testing / Definition of Done
Backend: the noise test proven on a synthetic series with a known z; drivers and emerging
proven against fixed buckets; insight 7 proven to render zero mismatches as a finding, not as
an empty panel. Frontend: each screen has a render test per state — loaded, empty, withheld,
error. **Both:** gates green; zero-diff client.

#### Expected outcome
Four of seven V2 pages live on real data.

---

### Phase 3 — Calls workbench and export
**Objective:** `/calls` — the page with no backend at all today.

#### Vertical 1 (Backend)
- **Tasks:** `GET /insights/calls` — the shared filter set plus `q`, `sort`, `order`, `page`,
  `perPage`, returning a stable projection covering the 26 CSV columns; `GET /insights/calls/{id}`
  — the evidence view with transcript turns; server-side CSV, or a documented client-side
  contract if the column list is to stay a frontend concern.
- **Modules:** `list_calls.py`, `read_call_evidence.py`, `calls.py` router, a paged read on
  `SqlInsightsSource`.
- **Dependencies:** Phase 1 period filter.
- **Deliverables:** two endpoints; export contract; **the leak test extended to cover the
  evidence endpoint's output.**
- **Risk owned here:** the evidence endpoint serves transcript text. `plan.md` §6.3 calls
  label stripping "the single most important safety property". The existing leak-check
  (`tests/support/leak_check.py`) must run against the serialised response, not just against
  ingestion.

#### Vertical 2 (Frontend)
- **Tasks:** the calls table — search, six sortable columns, 25/50/100 paging, row selection
  with a select-all-on-page checkbox, download filtered and download selected; the evidence
  drawer wired to the real endpoint and reachable from every `callIds` list on every screen.
- **Dependencies:** Phase 3 backend; Phase 1 `DataTable`.
- **Deliverables:** `/calls`; the drawer working from all screens.

#### Integration
**Checkpoint I2 — the CSV column contract.** Agree once, in writing, whether the 26 columns are
a server projection or a client mapping. Do not let both sides own it; two column lists that
drift is a support ticket nobody can reproduce.

#### Testing / Definition of Done
Backend: pagination stable under an equal-valued sort key (tie-break on call id, or rows
reshuffle between pages); **leak test green on the evidence response**. Frontend: CSV opens
in Excel with the BOM intact; selection survives paging; search does not lose caret position.

#### Expected outcome
Every figure on every screen is traceable to the calls behind it, and the corpus is
exportable.

---

### Phase 4 — Action centre write path
**Objective:** `plan.md` Phase 9 / decision D6. The largest single piece of new backend work.

#### Vertical 1 (Backend)
- **Tasks:** `actions` table — title, source finding, evidence, calls (many-to-many), owner
  team (Touchpoints sheet), owner, priority, seven lifecycle states, assigned/due dates,
  checklist, activity log, action taken, outcome, measurement window; seeding, porting
  `add_action` from `04_build_app_data.py`; `POST /insights/actions` and
  `PATCH /insights/actions/{id}`, with **monitoring and completed requiring a measurement**;
  the playbook catalogue as `config/playbooks.yaml` with a completeness test mirroring
  `test_insights_labels.py`; keep the derived-findings read separate from the persisted-actions
  read — they are different objects and merging them is how a finding acquires a fake status.
- **Dependencies:** none beyond Phase 1.
- **Deliverables:** migration; write endpoints; playbook config; seeded actions.

#### Vertical 2 (Frontend)
- **Tasks:** the focused action view (`?focus=<issue>[&employer=]`) — meaning, why, steps,
  suggested owner, evidence, already-in-progress; the issues-to-act-on list; the Trello board
  with seven lanes, labels, due badges, avatars and a completed edge; the card modal — next
  move, checklist with progress, "what was done" / "what changed" forms, activity timeline,
  Move to, owner and due edit; the composer prefilled from a playbook with calls pre-linked;
  board / table toggle.
- **Dependencies:** Phase 4 backend; Phase 2's `issueHref`.
- **Deliverables:** `/actions` fully working against the server, not localStorage.

#### Integration
**Checkpoint I3 — the playbook key registry.** Issue keys (`unresolved`, `escalation_missed`,
`tp_<touchpoint>`, `cat_<category>`, …) are referenced from every screen and resolved by the
backend. They must be defined once, in `config/playbooks.yaml`, and validated at startup.
A dead key must fail CI, not render an empty panel.

#### Testing / Definition of Done
Backend: lifecycle transitions tested including the refusal to reach *monitoring* or
*completed* without a measurement; every playbook key resolves; every playbook has steps and
an owner. Frontend: create → assign → tick → log → action taken → outcome → completed, end to
end against a real server; no `localStorage` write path remains.

#### Expected outcome
"What should we do next?" is a working system, not a mockup.

---

### Phase 5 — AI insight surfaces
**Objective:** the feed, the four lenses and the strips — as a production capability, under a
contract that cannot invent a number.

#### Vertical 1 (Backend)
- **Tasks:** an insight-generation use case taking **already-computed response DTOs** and
  returning ranked, one-sentence insights with severity, a meta line and an issue key; a prompt
  under `infrastructure/llm/prompts/`; the templated fallback used when no provider is
  configured or a call fails — the screen must never be empty because a model was down;
  **guardrails:** a contract test asserting the service's only inputs are response DTOs, and a
  test asserting every number in generated text appears in the input facts.
- **Dependencies:** Phase 2 (exec facts must exist first); C3 (INFERENCE and RECOMMENDATION).
- **Deliverables:** insight service; prompt; fallback; guardrail tests.

#### Vertical 2 (Frontend)
- **Tasks:** `InsightFeed` (expandable, evidence + What to do), `InsightStrip` (2–4 cards),
  the four-lens grid; the AI badge and the standing tooltip — *"never calculates, forecasts or
  adds a number of its own"* and *"if an insight and a figure disagree, the figure is right"*;
  a visible degraded state when insights are templated rather than generated.
- **Deliverables:** three insight components across seven screens.

#### Integration
**Checkpoint I4 — the honesty contract.** Agree that generated text is labelled INFERENCE or
RECOMMENDATION, never OBSERVED, and that the fallback is visibly distinguishable. This is a
product decision with a compliance edge, and it is the reason C3 matters.

#### Testing / Definition of Done
No generated sentence contains a number absent from its input facts. Every insight carries an
epistemic chip. Provider failure degrades to templated copy with a visible indication and
never blanks a panel.

#### Expected outcome
The one clearly marked AI surface per page that V2 specifies, with the guardrails the README
itself asks for.

---

### Phase 6 — The screens V2 dropped, plus the remainder
**Objective:** close scope. Everything here depends on a Phase 0 deferral being answered.

#### Vertical 1 (Backend)
- `/insights/value-pack` (insights 30–32) **if approved** — 30 and 31 PARTIAL, 31's `routed`
  facet withheld with a stated reason and **never defaulted to false**.
- Withheld panels for insights 6, 9, 17, 22, 25, 26 — the question, why it cannot be answered,
  and exactly what would unlock it.
- `/catalogue` content: all 32 insights with screen and origin.

#### Vertical 2 (Frontend)
- `/rules` (insights 23, 24, 27) **if C5 says keep** — V2 has no design for it, so it inherits
  V1's `rules.html` layout translated into the V2 language.
- `/demand` (insights 15–19) **if C6 says keep** — likewise; `plan.md` already notes it has no
  prototype page and follows the same design language.
- `/value-pack`, `/catalogue`, `/diagnostics`.
- Withheld panel component.

#### Integration
**Checkpoint I5 — the §9 reconciliation.** Walk all 32 insights against what actually renders.
Anything that renders nowhere is either a plan error or a scope cut, and it gets recorded as
one or the other.

#### Testing / Definition of Done
Every BUILD insight in §9 renders somewhere. Every WITHHELD insight renders a withheld panel.
No insight is silently absent. `plan.md` §9 statuses match reality.

#### Expected outcome
Scope is closed and provable against the catalogue.

---

### Phase 7 — Hardening, performance, documentation
**Objective:** production readiness.

#### Vertical 1 (Backend)
Query performance on the paged call list and the trend rollups; caching strategy for
recomputed-per-request figures; Postgres verification of every date boundary (SQLite tolerates
naive vs aware, Postgres does not); README — setup, the three import commands, running an
extraction, the gates, the architecture diagram.

#### Vertical 2 (Frontend)
Accessibility pass (every clickable row focusable, Enter and Space, tooltips reachable by
keyboard, band pills shape-coded not colour-coded); responsive verification at 320/768/1440;
print stylesheet — the prototype README notes these pages get printed in meetings; bundle size.

#### Integration
Full walkthrough of all nine routes against a real extraction run.

#### Definition of Done
All gates green. Coverage maintained. Documentation complete. No known accessibility failure.

---

## 10. Parallel Development Strategy

**The split is clean because the seam already exists.** The OpenAPI document is generated from
the backend and the TypeScript client is generated from it, with a zero-diff gate. That is a
machine-checked contract between the two verticals, not a convention.

| Principle | How |
|---|---|
| **Frontend is never blocked** | Phase 1 Vertical 2 has zero backend dependency. Later phases build against the generated client with fixtures until the endpoint lands. |
| **Backend is never blocked** | No backend task in any phase depends on a frontend deliverable. |
| **Contract changes are events, not surprises** | Any change to a response model regenerates `schema.ts`. The zero-diff gate fails the build if someone forgets. Breaking changes are batched into I1. |
| **One filter model** | `InsightsQuery` stays the single source. A screen that needs a new filter gets it added there, never parsed locally. |
| **One issue-key registry** | `config/playbooks.yaml`, validated at startup. |

**Sequencing rules**

1. **Land C1 and C3 together, once.** Two breaking releases cost twice as much and the second
   always lands mid-screen.
2. **Never merge a backend contract change and a frontend screen in the same PR.** The
   zero-diff gate is the handshake; putting both sides in one PR hides which one broke.
3. **Phase 4 can start early if Phase 2 slips.** The action write path depends only on Phase 1.
4. **Phase 5 cannot start before Phase 2.** Insights summarise figures that must exist first.

**Estimated load balance:** Vertical 1 is heaviest in Phases 1, 3 and 4; Vertical 2 in Phases
1, 2 and 4. Phase 2 is the most lopsided toward the frontend — if it stalls, Vertical 1 pulls
Phase 4 forward rather than waiting.

---

## 11. API / Data / Integration Dependencies

### 11.1 New and changed endpoints

| Endpoint | Phase | Breaking |
|---|---|---|
| All 8 — add `from` / `to` / `repeat` | 1 | No (additive) |
| `/insights/risk`, `/insights/accounts/{ref}` — C1 | 2 | **Yes** |
| All 8 — C3 epistemic split | 2 | **Yes** |
| `/insights/exec` — movement, drivers, emerging | 2 | No |
| `/insights/accounts/{ref}` — insight 7 | 2 | No |
| `GET /insights/calls` | 3 | New |
| `GET /insights/calls/{id}` | 3 | New |
| `POST /insights/actions`, `PATCH /insights/actions/{id}` | 4 | New |
| `GET /insights/value-pack` | 6 | New, pending approval |

### 11.2 Data model changes

| Change | Phase | Migration |
|---|---|---|
| `actions` table + `action_calls` join + checklist + activity log | 4 | Yes |
| Call-list read projection | 3 | No — read path only |
| Playbook catalogue | 4 | No — config |

### 11.3 Sequencing

```
Phase 1 (period) ──┬─> Phase 2 (4 screens) ──> Phase 5 (AI insights)
                   ├─> Phase 3 (calls + evidence)
                   └─> Phase 4 (actions write path)
                                  └─> Phase 6 (remaining screens) ──> Phase 7
```

The only hard cross-vertical blocks are **I1** (the breaking release) and **I3** (the issue-key
registry). Everything else is fixture-shimmable.

---

## 12. Testing and Validation Strategy

**The existing gates do not change.** `./scripts/check.sh` stays the bar and is never weakened
to make something pass.

| Level | What |
|---|---|
| **Domain unit** | Every new aggregation with a hand-checked fixture. The noise test proven against a series with a known z. |
| **Contract** | The import-linter contracts extended if new modules are added. The AI insight service's input contract asserted, not assumed. |
| **Integration** | Every endpoint: happy path, empty corpus, withheld, filtered-to-nothing, invalid filter → 422. |
| **Safety** | `test_no_circular_scoring.py` extended to cover any new path near `design_churn_profile` (C4). The leak test extended to the evidence endpoint's **serialised response** (Phase 3). |
| **Frontend unit** | Every primitive; every screen in four states — loaded, empty, withheld, error. |
| **Contract sync** | `npm run generate:api` producing zero diff. This is the integration test between the verticals. |
| **Manual** | A full walkthrough against a real extraction run at the end of each phase. |

**Two things that will not be caught by any of the above and need naming:**

1. **A test that encodes a stale assumption passes.** This already happened this project: a
   colleague's merge added the `control_exceptions` column, the adapter kept discarding it and
   emitting a now-false caveat, and the tests passed because they encoded the old assumption.
   Any test asserting "this field is unavailable" must be re-checked whenever the schema moves.
2. **A figure that is right and a sentence that is wrong.** The AI surfaces make this newly
   possible. The guardrail in Phase 5 (every number in generated text must appear in the input
   facts) is the only mechanical defence; beyond it, the "figure wins" rule must be visible on
   screen so a reader can resolve the disagreement themselves.

---

## 13. Risks and Dependencies

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| **R1** | **Extraction agreement is below the bar.** L3 38%, L4 19%. Signals, touchpoint, process gap and quality score are exactly what V2 leans on. | **High.** Screens can be built and still show poor data confidently, with a call-id drawer behind it. | Not a frontend problem and not solvable by this plan. `Phase-5-Findings.md` puts the per-field bar in front of Minnie. Build the screens; decide separately what a demo is pointed at. Withheld states must be honest, not decorative. |
| **R2** | **C1 or C3 is deferred past Phase 2.** | **High.** Both are breaking; after the screens exist, the cost is every consumer. | Phase 0 exists for this. If C3 cannot be answered, build Phase 2 with the current three-value enum and accept a second breaking release — but record the choice. |
| **R3** | **Evidence endpoint leaks answer-key material.** Transcript text is the one place label stripping matters. | **High.** `plan.md` §6.3 calls it the single most important safety property. | Extend the leak test to the serialised response before the endpoint ships, not after. |
| **R4** | **The v2 prototype is not self-contained.** It reads `../data.js`, `../app.js` and `../app.css` from `Prototype/`. | Medium. Deleting or reorganising `Prototype/` breaks all seven pages silently — they render their source note and nothing else, with no console error. | **Already bitten once:** PR 23411 committed the folder as `Prototype_V2/`, beside `Prototype/` rather than inside it, so every `../` reference resolved to the repo root and nothing loaded anywhere. Relocated to `Prototype/v2/`. Do not tidy `Prototype/` away, and do not move either folder without loading a page afterwards. |
| **R5** | **Prototype behaviour treated as specification where it is an artefact.** V2 computes over a fully-populated generated `data.js`; the real corpus has 100 calls, most employers with one. | Medium. Panels that look full in the prototype will be mostly withheld in production. | Every screen's empty and withheld states are first-class deliverables in Phase 2, not polish. |
| **R6** | **Two developers diverge on filter semantics.** | Medium. | One `InsightsQuery`. The window-vs-period rule written down in Phase 0. |
| **R7** | **Playbook content ships unreviewed.** V2's README says plainly: *"The recommended steps are generic… they are a starting playbook and need review by the owning teams."* | Medium. Generic advice presented as a recommendation to Operations, Compliance, Account Management and Knowledge Management. | Phase 4 deliverable includes routing `config/playbooks.yaml` to the four owning teams for review before Phase 7. |
| **R8** | **"Newly flagged" ignores the filters.** V2's own README flags this; the tooltip says so. | Low, but it is a figure that disagrees with its own filter bar. | Either scope it or keep the disclosure. Decide in Phase 2. |
| **R9** | **The action write path is the first user-editable state.** | Medium. Concurrency, audit, authorisation — none of which the read surface needed. | Phase 4 needs an explicit answer on who may edit an action. **Not currently specified anywhere.** |
| **R10** | **Azure squash-merge rewrites SHAs and deletes branches.** Already bit this project once. | Low, known. | Rebase stacked branches after every merge; never push to a branch Azure deleted. |

### External dependencies

- **Minnie** — the eight conflicts in §5.1, the Phase 5 per-field bars, and the value-pack scope.
- **Karim** — the v9→v10 schema change behind insights 6, 17 and 25. Nothing here waits on it;
  those insights ship as withheld panels.
- **Finance** — `cost_per_call` (D4). Every money figure stays withheld until it lands.
- **Operations, Compliance, Account Management, Knowledge Management** — playbook review (R7).
- **An authorised extraction run over the full corpus** — real API spend plus member
  conversation data leaving the building. Noted in `Open-Decisions.md` as not yet authorised.

---

## 14. Open Questions / Clarifications Required

**Twenty-two open items across three tables, one of which (G1) is now closed.** All eight conflicts from §5.1 appear —
C8 as three rows, because its four fields need three different answers — and the rest come
from the gaps, risks and integration checkpoints elsewhere in this document. They are
collected here because a plan that scatters its unknowns through fourteen sections is a plan
whose unknowns do not get answered.

**How to read the tables.** IDs keep the prefix of the section they come from, so any item
can be traced back: **C** conflict (§5.1) · **G** gap (§5.2) · **R** risk (§13) ·
**I** integration checkpoint (§9) · **D** decision in `plan.md` §5 · **O** item already open in
`Open-Decisions.md` · **U** undetermined (nothing in the code or the prototype answers it). *Blocks* names the earliest phase that cannot finish without an answer.

**The default column is the point of this section.** Every item carries what happens if
nobody answers it in time. The defaults are chosen so that silence never stops work and never
quietly decides something expensive: where an answer is cheap to reverse, the default moves;
where it is expensive — a breaking change, or a figure that names a person — the default is
to hold the existing position and keep the question open. **A default taken by silence is
recorded in `plan.md` as taken by silence,** so nobody later reads it as a decision somebody
made.

### 14.1 Blocking — an answer is needed before the phase can finish

A struck row is closed; it stays visible with a pointer to where the decision lives, so this
section's length stays a true measure of what is still unknown (§14.4).

| ID | Question | Owner | Blocks | Default if unanswered |
|---|---|---|---|---|
| ~~**G1**~~ | ~~**Period vs window.**~~ **DECIDED 2026-09-24 by Ranjit: the §6.1 rule as written.** A period filter narrows the corpus; it does not redefine a metric's window. Recorded as **D11** in `plan.md` §5, including the rejected alternative and the cost of the caveat-over-suppression choice. | Ranjit | ~~Phase 1~~ — **unblocked** | — |
| **C1** | **What "flagged" names.** Metric 10's four conditions, or two-or-more indicator families? They select different accounts and V2 uses one word for both. | Minnie | **Phase 2** | **Hold D2 for the flag; show the family count beside it under a different name.** The workbook wins on definitions, and `dashboard.yaml` already warns where one word for two systems leads. |
| **C3** | **Epistemic vocabulary.** Three values or six? And does `basis` split from `published`? | Minnie | **Phase 2** | **Split `basis` from `published`, six values.** This is the only default that creates work rather than deferring it, and it is chosen anyway: after Phase 2 the cost moves from one enum plus a client regeneration to every consumer. |
| **C2** | **Applied-filters row.** V2 removes the scope line; §9 Practices requires the row to "always show scope and count". | Ranjit | **Phase 2** | **Adopt V2's chip row, keep the call count in the page head.** The practice is about not hiding what was excluded, not about that specific row. |
| **C4** | **`design_churn_profile` on screen.** V2 shows it in a tooltip, honestly labelled. The codebase walls it out structurally. | Minnie | **Phase 2** | **Do not ship the value.** The disclosure V2 makes can be made in prose without it. Reversible later; a circular-scoring incident is not. |
| **C8a** | **`archetype`.** Not one of the sixteen schema fields. Drives two playbooks (`brush_off`, `circular`) and a filter. | Karim, then Minnie | **Phase 2** | **Drop it** until a source exists. Shipping it means inventing a definition, which §2A.4 forbids. The two playbooks lose their predicate and are held back with it. |
| **R9** | **Who may edit an action?** No authentication or authorisation model exists anywhere in the codebase. | Minnie | **Phase 4** | **Trusted-network, single-tenant, recorded as such** in `plan.md` and on the screen. Do not invent a permission model; do not ship an unlabelled one. |
| **I2** | **CSV ownership.** Is the 26-column projection the server's or the client's? | Ranjit | **Phase 3** | **Server projection.** One list, versioned with the endpoint. Two column lists that drift is a support ticket nobody can reproduce. |
| **C5** | **Does `/rules` ship?** Endpoint built; V2 removed the page; `plan.md` §8 says it should be in the nav. | Minnie | **Phase 6** | **Ship it,** reachable from `/agents` rather than on the main rail. Insights 23, 24 and 27 otherwise render nowhere. |
| **C6** | **Does `/demand` ship?** Same situation. | Minnie | **Phase 6** | **Ship it.** Insights 16 and 19 have no other home; the exec lens only summarises them. |
| **G9** | **Does `/value-pack` ship?** Insights 30, 31 and 32 are all PARTIAL; V2 has no page; no endpoint exists. | Minnie | **Phase 6** | **Defer.** It is the only planned scope item with neither a prototype nor an implementation. Building it on silence would be building it because it was on a list. |

### 14.2 Not blocking, but should be answered

| ID | Question | Owner | Relevant from | Default if unanswered |
|---|---|---|---|---|
| **C7** | **Cost-to-serve.** V2 removes it; insight 15 View 2 defines it. | Ranjit | Phase 6 | **Accept the removal from `/exec`, keep it on `/demand`.** V2 is the presentation authority; the `/exec` placement was Ranjit's own, not the docx's. |
| **C8b** | **Member effort and complexity.** Our composites, not v9 fields. | Ranjit | Phase 2 | **Build them, always labelled as our composites** — §9 insight 29 already requires the label. |
| **C8c** | **`caller_type`.** Used as a V2 filter and in an exec lens; not one of the sixteen fields. Already open in `Open-Decisions.md`. | Minnie | Phase 2 | **Omit the filter** until the existing open question closes. The exec lens keeps the comparison and states the field's provenance. |
| **O3** | **`indicators.min_rate: 0.2`.** Still unsourced, and now visible on screen through the indicator chips V2 puts on every account row. | Minnie | Phase 2 | **Drop the rate, keep the floor** — the recommendation already made in `Open-Decisions.md`. An inert number that silently starts filtering later is the worst of both. |
| **R8** | **"Newly flagged" ignores the filters.** V2's own README flags this. | Ranjit | Phase 2 | **Keep V2's disclosure.** A figure that disagrees with its own filter bar is acceptable only while it says so. |
| **R7** | **Playbook content.** V2 says plainly the steps are generic and need review by the owning teams. | Operations, Compliance, Account Management, Knowledge Management | Phase 7 | **Ship labelled as unreviewed** and route `config/playbooks.yaml` to the four teams during Phase 4. Do not present generic advice as a team's own recommendation. |
| **D4** | **`cost_per_call`.** Unknown, and finance owns it. | Finance | Phase 6 | **Every money figure stays withheld.** Never a placeholder, in config or in code. |
| **D5/D10** | **The v9 → v10 schema change** behind insights 6, 17 and 25. | Karim | — | **Withheld panels ship regardless.** Nothing in this plan waits on it. |

### 14.3 Cannot be determined from the code or the prototype

Nothing in `Prototype/v2`, the workbook, the docx or the codebase answers these. They need
someone to say, and there is no default that is better than asking.

| ID | Question | Owner | Why it matters |
|---|---|---|---|
| **U1** | Are the four lens groupings — Employers · Churn & retention · Product & service · Payer & carrier — a business taxonomy someone asked for, or a presentational choice made in the prototype? | Minnie | The lenses drive which figures the exec page computes. If they are presentational, they can be reorganised freely; if someone asked for them, they are a requirement and the exec payload is shaped by them. |
| **U2** | When the AI provider is unavailable, should the surface degrade to templated copy or hide itself? | Minnie | V2's code degrades; its README does not say which is wanted. This is the difference between a page that is quietly less useful and a page that visibly lost a feature. |
| **U3** | Is V2's seven-lane action lifecycle the client's own process, or a prototype invention? | Minnie | `plan.md` Phase 9 names "seven lifecycle states" and V2 has seven lanes, which agree — but **neither cites a source**, so the agreement may be two guesses rather than one fact. It is the schema of the first write path in the product. |

### 14.4 Where the answers get recorded

Each item is closed in the document that owns it, not in this one: conflicts and gaps in
`plan.md` §8/§9, the three already-open items in `Open-Decisions.md`, and the per-field bars
in `Phase-5-Findings.md`. **This section is the agenda, not the record.** When an item closes,
it is struck here with a pointer to where the decision lives, so that the length of this
section is a true measure of what is still unknown.

---

## 15. Final Recommended Execution Sequence

| Phase | V1 — Backend | V2 — Frontend | Gate to exit |
|---|---|---|---|
| **0** | Decision brief; cost C3 on a throwaway branch; count affected rows | Design-system spec; helper-porting inventory | All eleven of §14.1's blocking items decided, or running on a recorded default |
| **1** | Period filter across all 8 endpoints | Tokens, theme, shell, 13 primitives, 6 charts, drawer | Period proven on undated calls and tz-aware bounds; primitives 100% tested; zero-diff client |
| **2** | C1 + C3 (one release); `trends.py`; exec extension; insight 7 | Filter bar; `/exec`, `/risk`, `/accounts/:ref`, `/hierarchy` | **I1** breaking release synchronised; four screens in four states each |
| **3** | `/insights/calls`, `/insights/calls/{id}`, export contract | `/calls`; evidence drawer wired everywhere | **I2** CSV contract agreed; **leak test green on the evidence response** |
| **4** | `actions` table, write endpoints, `playbooks.yaml` | Focused action view; Trello board; card modal; composer | **I3** issue-key registry validated at startup; full lifecycle end-to-end against a real server |
| **5** | Insight-generation use case, prompt, fallback, guardrails | `InsightFeed`, `InsightStrip`, four-lens grid | **I4** honesty contract; no generated number absent from input facts |
| **6** | Value pack (if approved); withheld panels; catalogue content | `/rules`, `/demand` (if approved), `/value-pack`, `/catalogue` | **I5** §9 reconciliation — every insight renders or is recorded as cut |
| **7** | Performance; Postgres date verification; README + diagram | Accessibility; responsive; print; bundle size | Full walkthrough on a real run; all gates green |

**Start immediately, in this order:**

1. **Phase 0 decision brief** — Vertical 1, one day. G1 is decided, so nothing blocks Phase 1;
   C1 and C3 block Phase 2. Everything else in §14.1 has a default that lets work continue.
2. **Phase 1 design system** — Vertical 2, starts the same day and needs nothing from anyone.
3. **Phase 1 period filter** — Vertical 1, ready to start: G1 is decided (D11 in `plan.md` §5).

**Do not start** Phase 2's screens before C1 is answered; `BandPill`'s contract depends on it,
and it is referenced on four of the seven pages.
