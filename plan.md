# NanoVox Insights — build plan for a new codebase

Build, from an empty folder, a call-intelligence application for a general
agency: it reads raw call transcripts, extracts a fixed set of facts from each
call with an LLM, joins every call to the employer, broker and member it belongs
to, and renders 32 business insights on seven screens in a specific, already
approved visual design.

> **This file is never committed and never pushed.** §4.1 excludes it from git
> before the first commit. If `git status` ever lists `plan.md`, stop and fix
> that before doing anything else.

---

## Progress (kept by Claude Code — update as you go; never committed)

- [x] §4.1 Repo initialised, `plan.md` excluded, source documents copied in
- [x] §4.2 Bootstrap commit on `main` (Minnie said go ahead), `insights-v1` created, both pushed
- [x] §5 Decisions confirmed with Minnie (D1–D9 decided; D5/D10 deliberately
      parked in §7A pending Karim — that's the decision, not an open item)
- [x] Phase 0 — Scaffold and gates (3 commits, pushed)
- [x] Phase 1 — Domain model and reference data (4 commits, pushed, gates pass)
- [x] Phase 2 — Transcript ingestion, label stripping, caller resolution, answer key (4 commits, pushed, gates pass; 100/100 real calls resolved) — **except the AnswerKeyImporter task, see §8**
- [x] Phase 3 — LLM infrastructure (3 commits, not yet pushed — pushing at Phase 5) — **except run orchestration wiring, see §8**
- [~] Phase 4 — Extraction stages (L1 and L2 built and tested; L3, L4, the derivations and the pipeline use case not started)
- [ ] Phase 5 — Evaluation harness  ← **check-in gate**
- [ ] Phase 6 — Aggregations and read endpoints
- [ ] Phase 7 — Frontend design system (can start any time after Phase 0)
- [ ] Phase 8 — Screens
- [ ] Phase 9 — Action centre write path
- [ ] Phase 10 — Withheld panels, catalogue page, docs

Notes and surprises, newest first:

- 2026-09-22 — Phase 2 done, 4 commits, pushed. Confirmed before starting:
  bible_2 + PDF _1 (member CB-7700205 = Leon Castellano, CB-7700001 = Omar
  Liu not Rowan Hollis — now a regression test); 101 contacts vs 100 calls
  is not a discrepancy (89 employers with one contact + 6 with two = 101,
  matching the sheet's own "101 contacts... 210 planned calls" header —
  unrelated to batch 1's call count, different sheet, no fix needed);
  `VERIFIED (SECONDARY)` has no prose definition anywhere in the workbook —
  documented in the enum's docstring as inferred from the Source column
  (member/agent-portal material vs. the carrier's own primary document), not
  asserted. Ranjit's `rules.html` already has three-way chip logic
  (`is-secondary` class, "secondary" label) but **zero actual CSS for any
  confidence state** — `.conf` has no rule in `app.css` at all. Flagged for
  Phase 7; no chip style invented.

  Real bugs the leak test and the gates themselves caught before commit: (1)
  `split_call_block` was dropping the literal "CALL TAGS" marker from the
  answer-key block (partition() discards the separator); (2) the archetype
  regex greedily spanned back across the AHT segment's own "·" and captured
  "AHT 6m 20s · Competent and resolved" instead of just the archetype; (3)
  the leak test's own first draft flagged call C-0064 for containing "rules
  " — a false positive, since the agent legitimately says "I'll send you
  the actual product rules in writing" — fixed by checking the rule-citation
  *pattern* ("rules C-12, P-14" / "rules —") instead of the bare word,
  shared between the fixture-based and real-corpus leak tests
  (`tests/support/leak_check.py`); (4) `CallRow.turns` as an ORM relationship
  raised `MissingGreenlet` under the async session — replaced with explicit
  delete+insert statements rather than touching the lazy collection.

  Verified end to end against the real corpus (not just fixtures): 100/100
  calls parsed, speaker-resolved (agent name matched exactly one of two
  dialogue labels every time — no guessing needed), 0 unknown agents, 0
  unresolved callers, 100/100 resolved to an employer. Leak test clean
  across all 100. `pypdf` added as a new runtime dependency, pinned in the
  lock file the same metadata-closure way as everything else.

- 2026-09-22 — Phase 1 done, 4 commits, pushed. L1–L4 essential rule settled
  (a layer is essential iff some Metrics-sheet metric needs it — currently
  all four; `domain/layers.py` + `test_layers.py` enforce it). Insight 15
  confirmed on `/demand` (docx: "Screen 3 of 7") with its cost-to-serve view
  also on `/exec` (Ranjit's own placement, `exec.html` section 5) — no new
  catalogue entry. Dependencies: backend pinned via
  `requirements-lock.txt`/`requirements-dev-lock.txt` (computed from real
  installed package metadata — a true clean `pip install` wasn't possible in
  this sandbox, no network); frontend's `package-lock.json` verified for
  real with `npm ci`. `coverage/`-tracking bug fixed and confirmed; `check.sh`
  confirmed to actually exit non-zero on a broken gate (deliberately broke
  one, ran it, reverted).
  For Phase 1 itself: ported Ranjit's stage-1 xlsx reader (stdlib
  zipfile+ElementTree, no new dependency) and stage-3 row mapping, but
  hardened header-row lookup to search by content (the technique
  `03_join_corpus.py` already uses for the Rules sheets) rather than trust a
  fixed row index everywhere, since that depends on the raw XML emitting a
  `<row>` for every blank row above a header — true for this workbook, not
  worth depending on for the next one. Found a third `Confidence` value while
  verifying against the real corpus — `VERIFIED (SECONDARY)` — not in the
  plan's original two-value description; added to `RuleConfidence`. Verified
  the whole importer twice against the real workbook (not just fixtures):
  counts match `tools/README.md` exactly (95/30/285/101/20/122/12), zero
  warnings, and a second run is idempotent (no duplicate rows). `alembic
  check` confirms the migration matches the ORM metadata with no drift.

- 2026-09-22 — Caught the frontend's `coverage/` (Vitest's generated HTML
  report) committed in the Phase 0 frontend-skeleton commit — `.gitignore`
  had `dist/` and `.vite/` but not `coverage/`. Fixed in its own commit
  (untracked the files, added the ignore rule) rather than amending, per §2
  rule 1. Re-ran `scripts/check.sh` clean afterward and pushed.

- 2026-09-22 — Phase 0 done: added §2A "Coding principles (NanoVox standard)"
  after §2, copying NanoVox-V2's actual configs (pyproject.toml tool config,
  import-linter contracts, ruff/mypy settings, eslint/tsconfig/vitest config)
  rather than rewriting them, per §2A.0. Three commits: backend skeleton
  (FastAPI, health endpoint, settings, async SQLAlchemy + an Alembic baseline
  revision so `alembic heads` prints exactly one, RFC 9457 error handling,
  the three import-linter contracts), frontend skeleton (Vite/React/TS,
  router, TanStack Query, a typed client generated from the backend's own
  OpenAPI document, ESLint, Vitest), `scripts/check.sh` + README. Verified
  every gate actually passes, not just that the files exist: backend 93.94%
  coverage (51 tests), frontend 100% lines / 95.74% branches (25 tests),
  ruff/mypy/import-linter/eslint/tsc all clean, one alembic head,
  `generate:api` reproducible byte-for-byte. Backend `.venv` and frontend
  `node_modules` couldn't be installed from PyPI/npm in this sandbox (no
  network) — verified every gate command instead by running it through
  NanoVox-V2's already-installed `.venv`/`node_modules` against this repo's
  own code (read-only use of that reference folder, nothing in it touched),
  then seeded this repo's own `.venv`/`node_modules` the same way so
  `scripts/check.sh` runs end-to-end here too. Both are git-ignored either
  way.

- 2026-09-22 — Minnie: push to the GitHub origin is fine, main included, as
  long as it's never destructive; stop immediately if origin ever becomes
  Azure or a second remote appears. D1 decided (OpenAI default, Anthropic +
  Ollama as the only extras). D2 rewritten to match workbook metric 10 exactly
  (yes/no flag, not a band). D7 turned into an open question for Karim — the
  workbook contradicts itself on knowledge_failure; C-0001 is the proof
  (RESOLVED/91/"Competent and resolved" yet knowledge_failure present).
  Discovered while checking D7: the Signal Taxonomy already has a distinct
  `knowledge_error` signal ("agent stated a published rule incorrectly") that
  is the real agent-conduct event — unrelated to `knowledge_failure`. Global
  `min_n: 5` removed; min n is per metric, from the Metrics sheet. Bootstrap
  commit made and pushed; `insights-v1` created and pushed. §9 reconciliation
  against the Metrics/Call Tag Schema/Questions Worth Asking/Intelligence
  Register sheets done and presented to Minnie; **waiting on her go-ahead**
  before editing §9 further. Biggest finding: §7 Stage D's "fault records"
  (party/role/fault_type) are not a workbook concept at all — confirmed
  against `Insights-Worth-Building.docx`, which names a second per-fault
  record as *the* v10 schema change it's proposing, not something that
  exists today. This affects D5, D10, and insights 6, 7, 10, 11, 15–18, 25, 30.

- 2026-09-22 — Minnie approved the §9 reconciliation as written; applied all of
  it (insights 2, 4, 6, 10, 11, 15, 16, 17, 18, 23, 25, 28, 30, 31; ATTRIBUTION
  retired as a status). §7 rewritten: "fault records" moved to a new §7A "v10
  proposal — not built" appendix (including the finding that
  `MEMBER_COMPREHENSION`/`PLAN_AS_DESIGNED` appear nowhere in the workbook or
  the docx and have no standing); Stage D dropped as a required stage; pipeline
  stages renamed to the workbook's own layer vocabulary. **Checked the
  workbook for L1–L6 as instructed and it only has L1–L4** (grepped every
  sheet's "Emitted by" column) — used L1–L4 instead and flagged the
  discrepancy rather than inventing L5/L6; split essential/additive as
  L1+L2 essential, L3+L4 additive, matching the old A/B-essential,
  C/D-degradable split one-for-one. Checked Ranjit's prototype for a
  cost-to-serve tile per instruction — `exec.html` section 5 has one
  ("What we charge against what it costs to serve," minutes/life vs median,
  fee and premium alongside); folded metric 9 into insight 15 as its minutes
  view rather than a new insight, and added 15 to `/exec`'s insight list in
  Phase 8. Added §2A "Coding principles (NanoVox standard)" after §2, applied
  verbatim except §2A.3's layer range (same L1–L4 correction). D5/D10 now
  point at §7A instead of §7 Stage D. Ready to start Phase 0.

-

---

## 1. Context — read this first

You are starting with no history. This section is what you would otherwise have
to reconstruct.

**The client** is a general agency (a wholesaler in US employee-benefits
insurance). It sells group dental, vision, life and chiropractic plans, plus its
own exchange "program", to employers — always through **brokers**. The general
agency's customer is the broker, not the employer and not the member. A broker
who leaves takes their whole book of employers. Its call centre (Choice
Administrators) answers members and employer HR contacts.

**The relationship that matters most:** a member belongs to an employer; an
employer has exactly one broker of record. **A member never has a broker
directly.** Every call joins Call → Member or Contact → Employer → Broker.

**The corpus** is "v9": a build-bible workbook written by leadership (Karim)
plus a PDF of 100 written transcripts (batch 1 of a planned 600) over twelve
weeks, 6 Jul–25 Sep 2026. The workbook holds the master data (95 employers, 30
brokers, 285 members, 101 employer contacts, 20 agents, 122 rules, 12
touchpoints) and the **Call Tag Schema** — sixteen fields every call must be
reduced to. All employers, brokers, members and calls are fictional.

**The thesis** that separates this from ordinary call-centre analytics:
*attribution*. Beyond what a call was about, record **who caused the problem**,
with the sentence from the transcript that proves it — including when the answer
is the general agency itself. One call can carry two causes: the *proximate*
cause (why the phone rang — e.g. a denial letter that said only "ineligible")
and the *root* cause (why there was anything to deny — e.g. what the broker said
at the enrolment meeting).

**Two prior prototypes exist**, both static HTML:

- **Account Signals** (Ranjit) — built on the real v9 corpus. **Its look,
  layout and interaction model are approved.** You will reproduce them.
- **An attribution prototype** — synthetic data, now deleted. Its ideas are in
  the insight catalogue; **none of its numbers are real** and none may appear
  anywhere in this codebase.

**The insight catalogue** reconciles the two into 32 insights on seven screens.
§9 restates every one as an implementation spec.

**Principles every screen obeys** — these are the product, not polish:

1. **It cites; it does not decide.** Nothing labels an account as leaving or a
   broker as bad. It shows what the calls contain and leaves the judgement to the
   person whose name is on the account.
2. **Thin evidence is withheld, and says why.** Below a minimum sample a figure is
   not shown; its reason is shown where the number would be. Withheld is visually
   distinct from zero.
3. **Every figure opens its evidence** — the calls behind it and the quoted turn.
4. **Every claim declares its kind** — observed, reference, derived, pattern,
   inference or recommendation.
5. **We are a party like any other.** The same rules apply to the general
   agency's own documents as to a broker's.
6. **Nothing circular.** The employer "churn profile" in the workbook generated
   the corpus; no calculation may read it.

---

## 2. Standing rules — from Minnie, not negotiable

1. **Every task is its own commit.** One ▸ task in §8 = one commit. A fix is a new
   commit, never an amend.
2. **Commit messages are one or two sentences, in Minnie's voice.** They must not
   mention Claude, Anthropic, Sonnet, Opus or any AI model or provider in any way.
   No `Co-Authored-By` or similar trailers. Plain and specific — e.g. *"Add
   employer, broker, member and contact tables, loaded from the v9 workbook."*
3. **Push only to this GitHub origin.** `origin` is
   `https://github.com/ObnoxiousButCool/NanovoxV3.git`; Minnie has confirmed
   pushing there is fine, including `main` for the one-off bootstrap commit,
   since the repo starts empty. Never push anything destructive — no
   force-push, no history rewrite, no bulk deletion. The moment `origin`
   points at Azure DevOps, or a second remote is added, **stop pushing
   immediately** and fall back to commit-only, reminding Minnie to push
   herself. Check `git remote -v` first if there is any doubt. Still: after
   every three or four commits, say so out loud even when you did push, so
   Minnie can see progress without checking the remote herself.
4. **Never commit to `main`** after the single bootstrap commit in §4.2.
5. **The two reference folders in §3 are read-only.** Read and copy from them;
   never edit, delete, commit to, or run git in them.
6. **`plan.md` is never committed.**
7. **All gates pass before every commit** (§10).
8. **When this plan is wrong or unclear, stop and ask.** Record the answer in
   Progress → Notes. Do not improvise around it.

---

## 2A. Coding principles (NanoVox standard)

Applies to every phase from here on; overrides any convenience shortcut
elsewhere in this plan.

**A word on "layer" before this section uses it three different ways.** This
codebase has *architecture layers* (§2A.1: domain → application →
infrastructure → frameworks_drivers — code structure), the workbook's own
*extraction layers* (§7: L1–L4 — who produces a tag), and the Rules sheets'
*rule layers* (Program / Administration / Carrier — where a rule lives). Same
word, three unrelated axes. Keep them straight; never let "layer" alone stand
for more than one in the same sentence.

### 2A.0 Style reference

Before Phase 0, read NanoVox-V2's actual code (read-only) and mirror it. At
minimum read: `pyproject.toml`, the import-linter config, ruff/mypy settings,
the domain/application/infrastructure/frameworks_drivers layout, two use cases
end to end (router → use case → port → adapter), the LLM layer and degradation
handling, the test layout and fixtures, and the frontend's eslint/tsconfig/
vitest config, token file, one feature folder and the `generate:api` flow.
Copy configs across (rename the package) rather than rewriting them. When the
plan and NanoVox disagree on style, NanoVox wins. When they disagree on
content, the three bibles win (§3.0).

### 2A.1 Clean Architecture

- Four layers: domain → application → infrastructure → frameworks_drivers.
  Dependencies point inward only.
- Copy NanoVox's import-linter contracts verbatim: layers point inward; the
  domain is framework-free (no fastapi, starlette, sqlalchemy, alembic,
  pydantic, pydantic_settings, httpx, uvicorn); the application depends on
  ports, not frameworks. `lint-imports` runs in the gates.
- Domain: frozen dataclasses, value objects and enums (`CallSource`, layer
  status, epistemic status), plus pure functions for every metric (numerator,
  denominator, window, min n exactly as in the Metrics sheet). No I/O, no
  clock, no randomness: pass them in.
- Application: one use case per user intent, in `application/use_cases`. Use
  cases orchestrate ports and hold no framework types. Ports are
  Protocols/ABCs in the application layer (`TranscriptSource`, `LLMClient`,
  repositories, `SpeechToText`, `AudioStorage`).
- Infrastructure: adapters only (SQLAlchemy repos, the OpenAI/Anthropic/Ollama
  clients, the PDF parser, the label stripper). No business rules.
- frameworks_drivers: FastAPI routers, DI wiring and settings. Routers are
  thin: validate, call a use case, map the result.

### 2A.2 Clean code

- Small, single-responsibility modules and functions. Name things from the
  workbook's vocabulary, not invented synonyms.
- No magic numbers: min n, windows and thresholds live in one domain constants
  module, each citing its Metrics sheet row.
- Docstrings explain why (cite the bible: sheet + row, or insight number), not
  what.
- No dead code, no commented-out code, no TODOs without an issue reference in
  this plan.
- No duplication across metrics: shared eligibility/window logic is one
  function.

### 2A.3 Typing and errors

- mypy strict and TS strict. No `Any`, no bare `type: ignore` / `@ts-ignore`
  (if one is unavoidable, add a comment saying why).
- Explicit domain errors (e.g. `InsufficientSample`, `LayerUnavailable`,
  `LabelLeakDetected`), mapped to HTTP in one place in `frameworks_drivers`.
- **A layer is essential iff some Metrics-sheet metric needs it — decided,
  not assumed.** `domain/layers.py` holds `REQUIRED_LAYERS_BY_METRIC` (every
  metric that has an answer key, mapped to the layers it reads, each citing
  its Metrics-sheet row) and `ESSENTIAL_LAYERS`, set independently. Applied
  today: **L1–L4 are all essential** — every one of them is required by at
  least one metric (L4 alone by metric 5's `process_gap` component and by
  the indicator families metric 10's account page renders alongside the
  flag). The workbook has no L5 or L6 (checked every sheet; §7 records the
  check); if a layer numbered higher is ever added, this same rule decides
  its essential/additive status — additive only if no metric needs it.
  `tests/unit/test_layers.py::test_every_metrics_required_layer_is_essential`
  asserts `REQUIRED_LAYERS_BY_METRIC[metric] ⊆ ESSENTIAL_LAYERS` for every
  metric, so a new metric that quietly needs an additive layer fails the
  suite instead of drifting silently. An unavailable essential layer for one
  call withholds only the metrics that need it, with the reason recorded —
  not the whole call, and never rendered as empty or zero.

### 2A.4 Evidence and data integrity

- The label stripper runs before any LLM call and has its own tests, including
  a test that fails if any `CALL TAGS` / category / archetype / outcome /
  score text survives.
- Every quote the LLM returns is checked against the transcript. A quote not
  found in it is rejected, not repaired.
- Metric 10 is never called a churn prediction, anywhere (code, copy or API
  field names).

### 2A.5 Tests

- Tests are written alongside the code, not after it. Domain metrics get pure
  unit tests, including the min n boundaries and the eligibility rules.
- LLM adapters are tested with recorded responses. No live LLM calls in the
  test suite.
- Use cases are tested with fake ports. API tests go through the FastAPI test
  client.
- Coverage: backend ≥85%; frontend ≥80% lines and ≥75% branches.

### 2A.6 Frontend

- Ranjit's Prototype is the look-and-feel reference. Rebuild it in React/TS;
  don't port the vanilla JS wholesale.
- Design tokens only: no raw colours or spacing in components. CSS modules.
- API types come only from `generate:api` (openapi-typescript). No
  hand-written response types. TanStack Query for server state; filter state
  in the URL.
- Feature folders mirror the screens. Accessible by default: semantic
  elements, labelled controls, keyboard-operable drawer, and never colour
  alone for epistemic status.

### 2A.7 Gates (run before every commit, all must pass)

`ruff check`, `ruff format --check`, `mypy` (strict), `lint-imports`,
`pytest --cov-fail-under=85`, a single alembic head; `eslint .`,
`tsc --build --force`, `vitest run --coverage`, and `generate:api` with no
diff.

Do not commit with a failing gate, and do not weaken a gate to make it pass.
If one blocks you, stop and tell Minnie.

### 2A.8 Audio seam

No audio code now, but nothing may assume a transcript came from a PDF. The
parser is one `TranscriptSource` adapter among future ones.

---

## 3. Inputs and references

### 3.0 The three bibles

Three source documents outrank this plan, and they outrank each other in
different ways — each is authoritative on a different question, not on all
of them:

- **The v9 workbook** (`data/source/nanovox_corpus_v9_build_bible_2.xlsx`)
  wins on **definitions**: the data model, the Call Tag Schema, metric
  formulas, denominators, windows, minimum n, triggers.
- **Ranjit's prototype** wins on **presentation**: layout, visuals,
  interaction.
- **`Insights-Worth-Building.docx`** wins on **scope**: which insights, why,
  the principles.

This plan is derived from them, not the other way round. Where this plan
disagrees with a bible, the bible wins — fix the plan, don't work around it.
Where two bibles claim the same point and disagree with each other, stop and
ask Minnie; don't pick one silently.

### 3.1 Read-only references on this machine

| Folder | What to use it for |
|---|---|
| `C:\Users\ShlokaKulkarni\Downloads\Prototype\Prototype` | **Ranjit's Account Signals prototype — the design reference.** `app.css` is the design system. `app.js` is the shared behaviour to port: filter state in the URL, the theme switcher, the ten indicator families (`NV.INDICATORS`), bands (`NV.bandFor`), quality bands, call archetypes, the chart functions, the stacked drawer, the call-evidence renderer. Each `*.html` is a screen to reproduce. `tools/` is his workbook pipeline: `01_read_workbook.py` (sheet parsing), `03_join_corpus.py` (joins, derived fields), `04_build_app_data.py` (indicators, actions), `README.md` (expected counts). |
| `C:\Users\ShlokaKulkarni\Technossus\NanoVox-V2` | **The existing NanoVox app — the engineering reference.** Same stack as this project. Copy proven pieces rather than rewriting them (list in §3.3). Its working tree may be on any branch; treat it as a library of patterns, not a source of truth for the corpus. |

Serve the prototype beside the app while you build:

```bash
python -m http.server 4599 --directory "/c/Users/ShlokaKulkarni/Downloads/Prototype/Prototype"
```

### 3.2 Source documents — copy into this repo

Copy these three from `NanoVox-V2/Documents/` into `data/source/`:

| File | Role |
|---|---|
| `nanovox_corpus_v9_build_bible_2.xlsx` | Master data, the Call Tag Schema, Transcript Tracker (the answer key), rules, touchpoints, metric and trigger definitions |
| `nanovox_v9_transcripts_batch1_001-100_1.pdf` | The 100 transcripts |
| `Insights-Worth-Building.docx` | The insight catalogue, in prose with worked examples |

**Use workbook `_2` with PDF `_1` and no other pairing.** See §11.

`data/source/` is git-ignored by default (client material; see D8). Tests use
small fixtures extracted from these files and committed under `tests/fixtures/`.

### 3.3 What to reuse from NanoVox-V2

Copy, then adapt to this project's names. Keep their tests.

| From `NanoVox-V2/Code/Backend/` | Why |
|---|---|
| `pyproject.toml` tool config, import-linter contracts | Same gates, same four-layer rules |
| `application/ports/llm_provider.py`, `infrastructure/llm/base.py`, `registry.py`, `providers/*` (OpenAI, Anthropic, Azure Foundry, Ollama), `provider_probe.py` | Provider abstraction is proven; don't rebuild it |
| `infrastructure/llm/prompt_source.py`, `prompts.py` | Versioned prompts as markdown files |
| `domain/scoring/` (rubric engine, marker validation, gates) and `config/rubric.yaml` | The quality score — the v9 framework uses the same six dimensions and weights |
| `domain/parsing.py`, `domain/member_id.py`, `domain/entities/transcript.py`, `turn.py`, `value_objects/speaker.py` | Transcript model — **but fix speaker roles** (§11) |
| `domain/signal_evidence.py`, `domain/scoring/marker_validation.py` | Quote-must-be-in-transcript validation |
| `infrastructure/runner/`, `application/use_cases/run_corpus.py`, run tables | Batch runs with progress and retries |
| `application/ports/speech_to_text.py`, `audio_storage.py` | **Port interfaces only** — for the audio seams in §6.4. Do not copy adapters. |

| From `NanoVox-V2/Code/Frontend/` | Why |
|---|---|
| `package.json` scripts, Vite/TS/ESLint/Vitest config | Same gates |
| `shared/api/client.ts`, `queries.ts`, the `generate:api` flow | Typed API from OpenAPI |
| `shared/ui/charts.tsx` | Starting point; extend to the prototype's chart set |

---

## 4. Repository setup

### 4.1 Initialise

```bash
git init -b main
printf '\n# Local working plans - never committed\nplan.md\n' >> .git/info/exclude
git status --short          # must NOT list plan.md
mkdir -p data/source
cp "/c/Users/ShlokaKulkarni/Technossus/NanoVox-V2/Documents/nanovox_corpus_v9_build_bible_2.xlsx" data/source/
cp "/c/Users/ShlokaKulkarni/Technossus/NanoVox-V2/Documents/nanovox_v9_transcripts_batch1_001-100_1.pdf" data/source/
cp "/c/Users/ShlokaKulkarni/Technossus/NanoVox-V2/Documents/Insights-Worth-Building.docx" data/source/
```

### 4.2 Bootstrap commit, then branch

A branch needs something to branch from, so `main` gets exactly one commit:
`.gitignore`, `.gitattributes` (LF normalisation; the team works on Windows),
and a one-paragraph `README.md` — its paragraph records the three-bibles
precedence from §3.0, so it outlives this plan. Then:

```bash
git checkout -b insights-v1
git push -u origin main
git push -u origin insights-v1
```

All further work is on `insights-v1`. Pushing follows §2 rule 3.

### 4.3 Layout

```
Code/
  Backend/
    domain/                 pure Python; no framework imports
    application/            use cases and ports
    infrastructure/         adapters: persistence, llm, corpus, config
    frameworks_drivers/     FastAPI app, CLI, DI container
    config/                 yaml: rubric, dashboard thresholds, taxonomy
    tests/
  Frontend/
    src/app/  src/features/<screen>/  src/shared/{api,ui,styles,hooks}
data/source/                git-ignored inputs (§3.2)
scripts/check.sh            runs every gate in §10
README.md
```

---

## 5. Decisions — confirm with Minnie at the first check-in

Each has a recommendation. Ask; record the answer here; don't guess.

**D1 — Default LLM provider and model. DECIDED.** OpenAI `gpt-4o-mini` is the
default, matching NanoVox-V2's production `.env` (`LLM_PROVIDER=openai`,
`OPENAI_MODEL=gpt-4o-mini`). Configurable per run. Only two extra providers are
wired in, not all four NanoVox supports: Anthropic (`claude-opus-5`, per
NanoVox-V2's `.env`) and Ollama (`qwen2.5:7b-instruct`, local). Azure Foundry is
not ported — the provider registry stays extensible so it can be added later,
but no adapter is built for it now.

**D2 — Risk flag. DECIDED — this was never a free choice; it's a workbook
definition (§3.0: the workbook wins on definitions).** Metric 10, "Account risk
flag," is a **yes/no flag, not a band**. Denominator: employers with ≥3 calls in
the 12-week window are eligible; employers below that are simply not eligible,
not "no risk". Flagged when ≥2 of four conditions fire: complaint rate up
month-on-month · a failure-driven repeat (metric 4) · market_test intent · a
CHOICE-attributed UNRESOLVED call inside the renewal window. Min n to quote: 10
calls for that employer. **Never called a prediction** — the workbook is
explicit that no termination outcomes exist to validate one against. Ranjit's
ten indicator families (`NV.INDICATORS`) still render on the account page,
relabelled "other conditions observed" — they inform the reader but do not set
the flag and are not a second scoring system. `config/dashboard.yaml`:
`risk_flag: {eligibility_min_calls: 3, flag_threshold: 2, quote_min_calls: 10}`
replaces any band-threshold config. Insights 1 and 14 in §9 are rewritten to
match (below).

**D3 — Fonts. DECIDED — recommended.** Archivo (display), Public Sans (body), IBM Plex Mono (data).
*Recommended:* self-host with `@fontsource/*` so the app never makes an external
request.

**D4 — Cost per call. DECIDED — recommended.** Unknown; finance owns it.
`cost_per_call: null` in config. While null, every money figure renders withheld.
No placeholder number in code, ever.

**D5 — Employer as a responsible party. STILL OPEN — see the §9 reconciliation.**
The v9 schema's `complaint.attributed_to` has CHOICE, BROKER, CARRIER,
PROVIDER — no EMPLOYER, and confirmed against `Insights-Worth-Building.docx`
(line ~126, ~132 of the source): an EMPLOYER value and a second, per-fault
record are both named there as *the* v10 schema change the attribution
prototype is asking for — not something already in the v9 workbook. §7's
"fault records" (party/role/fault_type/confidence) do not exist as a workbook
concept at all; they are the attribution prototype's proposal, carried into
this plan uncritically. Recommended still stands only in the sense of "raise
it with Karim" — but "let the fault records carry their own party list" is not
something to build against the current schema. See the reconciliation table
below for how this affects insights 6, 7, 10, 11, 15–18, 25, 30, and §7A.

**D6 — Action centre writes. DECIDED — recommended.** single-user edits of status, owner,
due date, action taken and outcome; no auth, no history table yet. Items seeded
from the calls; workflow fields start empty rather than invented.

**D7 — Knowledge failure semantics. OPEN QUESTION for Karim, not a decision.**
The workbook disagrees with itself. Metric 8's plain-English meaning: "How
often we told someone something that was factually wrong, and which rule we
got wrong" — reads as an on-call error. The Call Tag Schema's note on
`knowledge_failure`: "naming the rule points at one article; naming the agent
fixes nothing" — reads as an organisational, not a call, failure. C-0001 is
tagged `knowledge_failure` present, rule C-12, touchpoint `denial_letter_eob`
— yet its own outcome is RESOLVED, score 91, archetype "Competent and
resolved": the agent stated the rule correctly on the call; what failed is
that the denial letter never named the waiting period. The tag cannot honestly
be both a factual error on the call and a document failure the agent had no
part in. **Ask Karim which reading v10 intends.**

Until he answers: store `knowledge_failure` exactly as the schema defines it
(`present`, `rule_id`, `correct_statement`); roll it up by rule ID, per metric
8's build note ("must roll up by rule ID… a list of knowledge base articles to
rewrite, ranked by call count"); never label it an agent error anywhere in the
UI or code.

This also **resolves**, rather than waits on, what D7 used to gate. The Signal
Taxonomy already carries the on-call version as its own, separate signal:
`knowledge_error` — "An agent stated a published rule incorrectly," MEDIUM
severity, owner Knowledge Management — independent of `knowledge_failure` and
able to fire with or without it. Agent conduct (insight 28) is built from the
`knowledge_error` **signal**, never from `knowledge_failure` gated by
touchpoint; the `touchpoint = agent_conversation` gate this plan previously
proposed does not appear anywhere in the workbook and is dropped.

**D8 — Are the source documents tracked? DECIDED — recommended.** No — `data/source/` is
git-ignored; tests use small committed fixtures. Minnie may prefer to track them
as NanoVox does.

**D9 — Database. DECIDED — recommended.** SQLite for local development, Postgres via
`DATABASE_URL`, exactly as NanoVox does.

**D10 — Attribution release gate. STILL OPEN, downstream of D5.** As written
this gate assumes "fault records" that D5 now shows are not a workbook
concept — there is nothing in the pipeline's actual output for Minnie to
hand-label against yet. Revisit once D5 is settled with Karim; see the §9
reconciliation table for what's real to gate today (complaint.attributed_to,
broker_named_aloud, process_gap, knowledge_failure, touchpoint) versus what
depends on a schema that doesn't exist yet.

---

## 6. Architecture

### 6.1 Layers

Four layers, dependencies pointing inward, enforced by import-linter with the
same three contracts NanoVox uses: layers point inward; domain imports no
framework; application depends on ports, not frameworks. Copy the contracts from
NanoVox's `pyproject.toml`.

### 6.2 Data flow

```
data/source/ workbook (_2)                 data/source/ transcripts PDF (_1)
        │                                              │
        ▼                                              ▼
 ReferenceImporter                        TranscriptSource: PdfCorpusSource
 employers, brokers, members,             ─ split into calls
 contacts, agents, rules,                 ─ read LEGITIMATE header fields only
 touchpoints, schema, triggers            ─ STRIP every label (§6.3)
        │                                 ─ resolve speaker roles
        │                                 ─ normalise → Transcript (source-agnostic)
        │                                              │
        │   AnswerKeyImporter ◄── Transcript Tracker   │
        │   (ground truth; never an input to the LLM)  │
        ▼                                              ▼
  reference tables ◄───── caller_ref join ─────── calls
                                                       │
                                                       ▼
                                       Extraction pipeline (§7)
                                       L1 deterministic extraction
                                                       │
                                                       ▼
                                       L2 classification ─┬─► L3 quality & knowledge
                                                           └─► L4 signals & gaps
                                                       │
                                  deterministic derivations (repeat, effort,
                                  complexity) — code, not LLM
                                                       ▼
                              domain/aggregation — pure functions;
                              min-n suppression happens HERE
                                                       ▼
                               /api/v1/insights/* read endpoints
                                                       ▼
                            React screens in the prototype's design
```

### 6.3 Label stripping — the single most important safety property

The PDF is an answer sheet. For each call it prints, and the LLM **must never
see**:

- the category in the title line: `C-0001 — Claims & EOB`
- the archetype: `Competent and resolved`
- the rule references: `rules C-12, P-14`
- the outcome and score: `| RESOLVED | score 91/100 |`
- the entire `CALL TAGS` block after the dialogue

Legitimate inputs, which may be kept: call id, date and time, talk time, caller
type, caller reference, agent id and name, and the dialogue turns.

Implement stripping in the ingestion adapter, and prove it:

- [x] ▸ a unit test on every one of the 100 calls asserting the rendered transcript
  sent to the LLM contains none of: `CALL TAGS`, `score `, `/100`, any outcome
  word in a header position, the archetype string, `rules `.
- [ ] ▸ the stripped labels go to the answer-key importer, never discarded silently.

  Status note (2026-09-23): the fixture-based leak test runs everywhere, but the
  real 100-call proof (`tests/integration/test_real_ingest.py`) and the corpus
  regression guard **skip silently on this machine** — they look for the corpus
  under `data/source/`, which does not exist here; the workbook and PDF are in
  `Documents/`. `pytest -rs` shows three SKIPPED, and `scripts/check.sh` still
  reports all gates passed. Point `WORKBOOK_PATH`/`TRANSCRIPTS_PATH` at
  `Documents/`, or place the pair under `data/source/`, before trusting this
  property — §6.3 says every Phase 5 figure depends on it.

If this property ever fails, every evaluation figure in Phase 5 is worthless.

### 6.4 Seams for audio later — build these now, implement nothing behind them

Audio arrives later. It must slot in without restructuring. So:

- **`Transcript` is source-agnostic.** Turns with speaker role, text, optional
  start/end seconds, optional channel. No PDF-specific field survives ingestion.
- **`TranscriptSource` port** with one adapter now (`PdfCorpusSource`) and room
  for `PastedSource` and `AudioSource`. The pipeline takes a `Transcript` and
  never knows where it came from.
- **`CallSource` enum** on every call: `CORPUS_PDF`, `PASTED`, `AUDIO`. `AUDIO`
  exists from day one, unused.
- **Every insights endpoint accepts `source`** (one or many) and filters by it.
  The UI shows the filter only when more than one source has data.
- **Generic `ingest_jobs` table** (kind, status, message, timestamps, result call
  id) rather than a PDF-specific job table.
- **Port interfaces copied from NanoVox** — `SpeechToText`, `AudioStorage` — with
  no adapters and no config. They exist so the dependency direction is decided.

Do not add upload endpoints, speech adapters, storage adapters or audio UI.

---

## 7. The extraction pipeline

**The contract is the workbook's `Call Tag Schema` sheet.** Read it in full
before designing any prompt. It defines all sixteen fields, their types and
allowed values, which layer the workbook expects to produce each one, and rules
such as *"Must cite a rule ID… naming the agent fixes nothing."* Where this plan
and that sheet disagree, the sheet wins; note it.

**Stage names are retired in favour of the workbook's own layer vocabulary.**
The Call Tag Schema's "Emitted by" column already names four layers — checked
against every sheet in the workbook, and nothing beyond L4 appears anywhere.
Use **L1–L4** everywhere from here on — code, prompts, config keys, this plan
— not the old "Stage A/B/C/D" names, and not "L1–L6": that range doesn't exist
in the workbook and was a mistake somewhere upstream of this plan. (Not to be
confused with the four *architecture* layers in §6.1/§2A.1 — domain →
application → infrastructure → frameworks_drivers. Same word, two different
axes: one is code structure, this one is who produces a tag.)

Each layer is its own call, its own prompt file and its own JSON schema where
it involves a model at all. One large schema fails far more often than several
small ones (NanoVox learned this), and each layer can be retried and evaluated
alone.

| Layer | Produces | Essential? | Notes |
|---|---|---|---|
| **L1 — deterministic extraction** (code, no model) | `caller_ref`; the detection half of `control_exceptions` (greeting/verification pattern match on the opening turns) and of `broker_named_aloud` (the name as spotted in the transcript, before validation) | Yes — metrics 1–12 all need `caller_ref` for the employer/broker join | No model judgement needed — Signal Taxonomy: "a greeting check needs no model." Runs first |
| **L2 — classification** (LLM) | `outcome` (v9 decision order: ESCALATED → PARTIALLY RESOLVED → RESOLVED → UNRESOLVED; ESCALATED requires named owner, reference, timeframe), `category` (7 values), `product_lines`, `complaint` {present, attributed_to}, `intent` (expansion / market_test / cancellation, verbatim + turn), `escalation.triggered` / `.requested_by_caller`, `broker_named_aloud` validated against the employer's broker of record, `touchpoint` (first pass), short summary | Yes — metrics 1–4, 6, 9–11 need `outcome`/`complaint`/`intent`/product line | Runs after L1; its category and product line choose which rules L3/L4 see |
| **L3 — quality & knowledge** (LLM) | `quality_score`, `markers` → six-dimension rubric score, `knowledge_failure` {present, rule_id, correct_statement} | Yes — metrics 7, 8, 12 need `control_exceptions`/`knowledge_failure`/`quality_score` | Port NanoVox's marker prompt, validation and rubric engine unchanged. Store `knowledge_failure` exactly as the schema defines it and never label it an agent error (D7, open with Karim) |
| **L4 — signals & gaps** (LLM) | `signals` (13 codes with severity, including `knowledge_error` — the actual agent-conduct event, independent of `knowledge_failure`), `escalation.handled` / `.trigger_type` (8 types), `control_exceptions` confirmed (3 types), `process_gap` {present, gap_type, touchpoint, proposed_change, raised_by, status}, `touchpoint` (confirmed) | Yes — metric 5 needs `process_gap`, metric 6 needs `escalation.handled`, metric 10's account page needs `signals` | Given only the rules for the call's category and product line, never all 122 |

`domain/layers.py::REQUIRED_LAYERS_BY_METRIC` and `ESSENTIAL_LAYERS` are the
source of truth for the "Essential?" column above — read there, not here, once
Phase 1 lands it; this table is illustrative.

**Two different senses of "essential," not to be conflated.** *Metric-essential*
(the table above, and §2A.3's rule) answers "does some metric need this layer at
all" — true for all of L1–L4. *Pipeline-critical* is narrower and about a single
call's record: L1 and L2 run in sequence and are pipeline-critical — a call with
no L1/L2 output has no analysis at all. L3 and L4 run concurrently after L2 and
are not pipeline-critical: a failure in either records that layer as
*unavailable with a reason* for that call, withholding only the metrics that
need it — never the whole call, and never rendered as empty or zero.

**What used to be "fault records" — party, role, PROXIMATE/ROOT — is not a
workbook concept and is not built.** It's parked in §7A.

**Evidence validation, every LLM layer.** Every quote must appear in the
transcript after normalisation, or the item is rejected with a recorded note
(port NanoVox's marker validation). Rejections are counted and shown on
Diagnostics.

**Deterministic, not LLM:** caller resolution (L1); repeat contact exactly as
metric 4 defines it — an UNRESOLVED call followed by a contact from the same
caller within 14 days (no category match required — that was this plan's own
addition, not the workbook's), excluding the window's last 14 days (no
exposure yet); talk time; member effort and complexity composites (port the
formulas from `03_join_corpus.py`: 0–100, High ≥60, Medium ≥35).

**Provenance on every analysis:** provider, model, prompt version per layer,
rubric version, tokens in/out, duration, timestamp. Cache layer outputs keyed
by (transcript hash, layer, prompt version, model) so re-runs don't re-bill.

**Answer key.** The Transcript Tracker sheet holds leadership's tags for all 100
calls. Import them into a `ground_truth` table. They are used **only** to score
the pipeline (Phase 5). No screen renders them.

### 7A. The v10 proposal — not built

A parking lot, not a spec. Nothing here is implemented against the current
schema; it's recorded so the idea isn't lost and nobody has to rediscover it by
rereading the deleted attribution prototype.

`Insights-Worth-Building.docx` names one schema change as the thing that would
unlock insight 6 and 17 outright, and complete 10, 11, 15, 16, 18, 25 and 30: a
**second, per-fault record** on the call, distinct from the single `complaint`
and single `touchpoint` the schema carries today — because today's schema can
hold the proximate cause or the employer-as-cause, but not both at once and not
a root cause behind it. Sketched, never built, never reviewed by Karim:

| Field | Proposed values |
|---|---|
| party | `WB`, `BROKER`, `EMPLOYER` (new — not in `complaint.attributed_to` today), `CARRIER`, `PROVIDER`, `MEMBER_COMPREHENSION`, `PLAN_AS_DESIGNED`, `UNATTRIBUTED` |
| role | `PROXIMATE` / `ROOT` — one call, two causes; this pairing is the actual ask in the docx (its insight 17) |
| fault_type, touchpoint, quote, turn_ref, confidence | as previously drafted here, unreviewed |

**`MEMBER_COMPREHENSION` and `PLAN_AS_DESIGNED` appear nowhere in the workbook
or the docx.** They were invented somewhere upstream of this plan and have no
standing. Drop them from any proposal actually put to Karim, unless he asks for
them himself.

Raise EMPLOYER and the second record with Karim together — they're one ask,
not two, since the second record is what lets EMPLOYER coexist with an
existing complaint target rather than replace it. Until he responds, nothing
is built against this, and D10's release gate has nothing to gate.

---

## 8. Phases and tasks

Each ▸ is one task and one commit. Phase 7 may run in parallel with Phases 1–6.

Task state, verified against the codebase on 2026-09-23 with `scripts/check.sh`
passing: `[x]` done, `[~]` partly done with a status note beneath it, `[ ]` not
started. Phase 8 has no ▸ tasks of its own — its table is the task list, and
none of it is built.

### Phase 0 — Scaffold and gates

- [x] ▸ Backend skeleton: packages, FastAPI app, health endpoint, settings via
  pydantic-settings, async SQLAlchemy + Alembic, pytest, import-linter contracts.
- [x] ▸ Frontend skeleton: Vite + React + TS, router, TanStack Query, Vitest,
  ESLint, OpenAPI type generation.
- [x] ▸ `scripts/check.sh` running every gate in §10; README says how to run it.

Acceptance: `scripts/check.sh` passes on an empty app.

### Phase 1 — Domain model and reference data

- [x] ▸ Domain entities: `Broker`, `Employer`, `Member`, `EmployerContact` (authority
  CAN_BIND / CANNOT_BIND), `Agent` (band, planned calls, expected score, score
  variance), `Rule` (id, layer P/A/C, area, text, commonly-confused-with,
  confidence), `Touchpoint` (code, owner team). Member → employer, contact →
  employer, employer → broker. A member never stores a broker.
- [x] ▸ Tables and first migration. Integer surrogate keys; business references
  (`BRK-12`, `EMP-1030`, `CB-7700205`, `CON-101`, `AGT-01`, `P-14`) as unique,
  indexed, non-null columns. `employers.broker_id` is a foreign key. Derived
  columns commented as derived: participation, fee band, annual fee, COBRA
  regime. `design_churn_profile` stored and never read (a test enforces it).
- [x] ▸ Workbook reader (infrastructure, behind a port). Port sheet parsing from
  `tools/01_read_workbook.py` and derivations from `tools/03_join_corpus.py`: fee
  band by rule P-33 ($25 for 2–8 eligible, $30 for 9–20, $35 for 21–199, $50 for
  200+), COBRA regime (Cal-COBRA below 20 eligible, federal at 20+),
  participation = enrolled ÷ eligible. About 1,500 cells are formulas with no
  cached value — derive; never read them.
- [x] ▸ `ImportReferenceData` use case — idempotent upsert by reference, returns
  counts and warnings. CLI command and `POST /api/v1/reference/import`.
- [x] ▸ Tests assert the counts in the prototype's `tools/README.md` and spot-check
  derived fields against the prototype's `data.js`.

### Phase 2 — Transcript ingestion, label stripping, caller resolution, answer key

- [x] ▸ `Transcript`, `Turn`, `CallSource` and the `TranscriptSource` port (§6.4).
- [x] ▸ `PdfCorpusSource`: split the PDF into 100 calls; read legitimate header
  fields; **strip labels** (§6.3) with the 100-call leakage test.
- [x] ▸ Speaker roles: both speakers are labelled by first name. Match the header's
  agent (`AGT-01|Sarah Whitlock`) against the speaker label; the other speaker is
  the caller. Test on real calls.
- [x] ▸ Caller reference: recognise `CB-\d+` (member) and `CON-\d+` (contact). Resolve
  to member or contact, then employer, then broker; store all resolved ids on the
  call. Unresolved references are stored, flagged, counted on Diagnostics, and
  excluded from account figures with the count shown — never guessed.
- [x] ▸ Ingest use case and `ingest_jobs`; CLI and endpoint.
- [~] ▸ `AnswerKeyImporter`: Transcript Tracker → `ground_truth`. Cross-check against
  the PDF's stripped `CALL TAGS`; report any disagreement.

  Status note (2026-09-23): `AnswerKey`, the `AnswerKeySource` port and
  `PdfAnswerKeySource` exist, so the PDF’s stripped `CALL TAGS` can be read.
  Missing: the Transcript Tracker sheet is not read anywhere, there is no
  `ground_truth` table, no importer use case, and no cross-check or
  disagreement report. `PdfAnswerKeySource` is referenced only by tests.

Acceptance: 100 calls, every one resolved to an employer and broker (or
explicitly flagged), zero label leakage.

### Phase 3 — LLM infrastructure

- [x] ▸ Port the provider port, adapters, registry and probe from NanoVox; `/providers`
  endpoint listing configured providers.
- [x] ▸ Versioned prompt loading; JSON-schema-validated responses; retry policy;
  token and duration accounting; the stage-output cache (§7).
- [~] ▸ Run orchestration: a run over a set of calls with progress, per-call status,
  resumability. Port from NanoVox's runner.

  Status note (2026-09-23): `infrastructure/runner/background_runner.py`,
  `domain/run_progress.py` and `domain/value_objects/run_status.py` exist and
  are tested, but `BackgroundRunner` is referenced only by its own test file —
  not by the container, a CLI or an endpoint. Built, not integrated.

### Phase 4 — Extraction layers

One task per layer: prompt file (where a model is involved), schema, domain
value objects, persistence, validation, tests with recorded provider responses
(no live calls in tests).

- [x] ▸ L1 deterministic extraction (`caller_ref`, opening-turn checks — code, no
  prompt)
- [x] ▸ L2 classification (with rule scoping by category and product line, so L3/L4
  see only the rules relevant to the call)

  Status note (2026-09-23): L1 and L2 are built, migrated (`call_extractions`,
  revisions `20260923_0517` and `20260923_0520`) and tested, but neither is
  composed in `frameworks_drivers/container.py`, so nothing can run them end to
  end yet. The pipeline task below is where that wiring belongs.

- [ ] ▸ L3 quality & knowledge (ported rubric; `knowledge_failure` stored exactly
  as the schema defines it, never labelled an agent error — D7)
- [ ] ▸ L4 signals & gaps (including `process_gap`). **Confirm against the Metrics
  sheet's build note for metric 5** whether `process_gap.present` alone covers
  self-inflicted demand's "calls caused by a logged process defect" component
  (insight 15), or whether "chasing an already-submitted action" needs a
  second condition — don't assume the one-field mapping proposed in §9 is
  final until this is checked against the workbook here.
- [ ] ▸ Deterministic derivations: repeat contact (metric 4), effort, complexity
- [ ] ▸ Pipeline use case wiring L1 → L2 → (L3 ∥ L4), essential vs degradable

### Phase 5 — Evaluation harness  ← stop and check in

- [ ] ▸ Per-field agreement between pipeline output and `ground_truth`, for every
  field that has an answer key: exact match for enums, set overlap for lists,
  rule-id match for knowledge failure, target match for complaint attribution
  (`complaint.attributed_to` — the Metrics sheet's own term for this dimension
  is "attribution target," not "party"; keep that word for this real field).
- [ ] ▸ Diagnostics page: agreement per field, per layer; rejected-evidence counts;
  unresolved callers; token cost of the last run.
- [ ] ▸ No fault-record labelling tool. There is nothing to hand-label until D5 is
  answered and §7A is (or isn't) built — D10 stays parked, not scheduled here.

**Check in with Minnie with the numbers.** Screens are built on pipeline output,
so a field with poor agreement means a screen that shows poor data. Decide
together which fields are good enough before Phase 8.

### Phase 6 — Aggregations and read endpoints

Pure functions in `domain/aggregation/`; read models in `application/`;
endpoints under `/api/v1/insights/`. Every endpoint takes the filter set (§8
Phase 7) plus `source`, and every response carries epistemic class, `n`, the call
ids behind each figure, and withheld reasons. Regenerate the typed client after
each endpoint.

- [ ] ▸ `config/dashboard.yaml`: min n is **per metric, from the Metrics sheet**
  (§3.0 — the workbook wins), not one global number — e.g. contact rate 30,
  complaint rate 10 calls, FCR 30, failure-driven repeat 30, self-inflicted
  demand 60, escalation integrity 30 triggers, control exceptions 30, knowledge
  failure 30, cost to serve 30, risk flag eligibility 3 / quote 10 (D2). Also:
  `cost_per_call: null`, peer size bands (2–24, 25–74, 75–199, 200+ lives),
  broker ranking floor (150 lives), broker pattern test (≥3 adverse mentions
  from ≥2 of that broker's employers), quality bands (good ≥86, average ≥60).
- [ ] ▸ Risk flag (metric 10, D2): yes/no, not a band — eligible at ≥3 calls,
  flagged on ≥2 of its four named conditions, quoted at ≥10 calls. Separately,
  the ten indicator families (port `NV.INDICATORS`) render as "other conditions
  observed" on the account page, informational only, each firing above an
  absolute floor **and** a rate; they do not set the flag.
- [ ] ▸ Peer contact rate; isolation (region → broker → employer tree, region ×
  category matrix, pattern test); agent events (port `agents.html`, from the
  `knowledge_error` signal, D7); rules (cited vs failed-to-explain, by rule
  layer P/A/C, provenance, area — counts only); exec scorecard; self-inflicted
  demand (metric 5's three components, published separately) with its minutes
  view (metric 9); broker book friction from `broker_named_aloud`; touchpoint
  ranking coloured by `complaint.attributed_to`; enrolment promise gap from
  `process_gap` + touchpoint. (Insights 6, 17 and 25 render their withheld
  panels instead — nothing to aggregate for them yet.)
- [ ] ▸ One endpoint per screen: `exec`, `risk`, `accounts/{ref}`, `hierarchy`,
  `demand`, `actions`, `rules`, `agents`, `value-pack/{broker_ref}`.

### Phase 7 — Frontend design system

Reproduce the prototype's `app.css` and `app.js` behaviour as React.

- [ ] ▸ Tokens from `app.css` `:root`, both dark blocks exactly as written. Fonts per
  D3.
- [ ] ▸ Three-state theme (Light default / Dark / Auto), persisted, stamped before
  first paint; charts redraw on switch (port `NV.inkOn`).
- [ ] ▸ Shell: the left rail — brand mark, nav items each with a one-line question
  beneath, theme control and corpus footnote at the foot, top bar under 820px.
- [ ] ▸ Primitives with tests: `Panel`, `KpiTile` (crit / warn / good / withheld),
  `BigRow`, `EpistemicChip`, `BandPill` (shape-coded, never colour alone),
  `SeverityLabel`, `Delta`, `Claim`, `Quote`, `Empty`, `Note`, `Withheld`.
- [ ] ▸ Charts: line with crosshair, horizontal bars with direct labels, grouped bars
  across time buckets, stacked composition with values in the legend, sparkline,
  region × category heatmap. Charts measure their container.
- [ ] ▸ Stacked evidence drawer with Back (`NV.drawer`), and the call-evidence view
  (`NV.callEvidence`).
- [ ] ▸ Filter bar: period (week / month / custom), region, broker, employer, risk
  band, and an *Advanced* disclosure (category, line, touchpoint, outcome, signal,
  escalation, repeat, compliance, effort, complexity, caller type, intent,
  complaint target, agent, quality). URL is the source of truth, mirrored to
  localStorage; "Copy link to this view"; an applied-filters row that always
  shows scope and call count.
- [ ] ▸ Keyboard: every clickable row and card is focusable and activates on Enter
  and Space.

### Phase 8 — Screens

One ▸ per screen. Each: matches its prototype page; filters narrow it; withheld
states render withheld; every figure opens its evidence.

| Route | Screen | Prototype page | Insights (§9) |
|---|---|---|---|
| `/exec` | Board scorecard | `exec.html` | summaries of 1, 5, 13, 15 (cost-to-serve view), 20 |
| `/risk` | Risk overview | `index.html` | 1–5, 9 |
| `/accounts/:ref` | Employer intelligence | `employer.html` | 1, 6, 7, 8 |
| `/hierarchy` | Broker & region | `hierarchy.html` | 10–14 |
| `/demand` | Where calls come from | — (new, same design language) | 15–19 |
| `/actions` | Action centre | `actions.html` | 20–22 |
| `/rules` | Rules & product | `rules.html` — **in the nav**, not hidden | 23–27 |
| `/agents` | Agent conduct | `agents.html` | 28, 29 |
| `/value-pack` | Value pack | — (new) | 30–32 |
| `/catalogue` | Insight catalogue | — (static content) | all 32 |
| `/calls`, `/calls/:id`, `/diagnostics` | Workbench | — | — |

WITHHELD panels (insights 6, 9, 17, 25, 26) render withheld unconditionally —
there is no gate that unlocks them, only a schema change Karim hasn't made.
PARTIAL panels (11, 16's extension, 27, 30, 31's `routed` facet) render their
buildable half and withhold the rest, each with its own stated reason.

### Phase 9 — Action centre write path (D6)

- [ ] ▸ `actions` table: title, source finding, evidence, calls (many-to-many), owner
  team (Touchpoints sheet), owner, priority, status (seven lifecycle states),
  assigned and due dates, action taken, outcome, measurement window.
- [ ] ▸ Seeding, porting `add_action` in `04_build_app_data.py`: one item per process
  gap, knowledge-failure rule, escalation-miss cluster, control-exception type,
  exit-language call, fired pattern trigger.
- [ ] ▸ `PATCH /insights/actions/{id}`; *monitoring* and *completed* require a
  measurement.
- [ ] ▸ Board and table views with the editor.

### Phase 10 — Withheld panels, catalogue, docs

- [ ] ▸ A withheld panel for every WITHHELD insight: the question, why it can't be
  answered, and exactly what data would unlock it.
- [ ] ▸ `/catalogue`: the 32 insights, filterable by screen and origin, each linking
  to where it renders.
- [ ] ▸ README: setup, the three import commands, running an extraction, the gates,
  the architecture in one diagram.

---

## 9. The 32 insights as implementation specs

**Status:** BUILD — computable today from the Call Tag Schema's own fields and
master data · WITHHELD — the field or value does not exist in the workbook (or
in `Insights-Worth-Building.docx`'s own proposals); ship the withheld panel ·
PARTIAL — part builds, part withheld. **ATTRIBUTION is retired as a status.**
It described a "fault records" pipeline stage that turned out not to be a
workbook concept (§7A) — every insight that carried it has been reclassified
above to BUILD, PARTIAL or WITHHELD on its own facts.

**Origin:** S = Account Signals · A = attribution prototype · M = merged ·
N = new from comparing the two.

### Screen 1 — Account risk (`/risk`, `/accounts/:ref`)

| # | Insight | Origin | Status | Computation and rules |
|---|---|---|---|---|
| 1 | Account risk flag | M | BUILD | Metric 10: yes/no, not a band (D2). Eligible at ≥3 calls for that employer in the 12wk window; flagged on ≥2 of the four named conditions; quoted only at ≥10 calls for that employer. Never labelled a prediction. Ranjit's ten indicator families (`NV.INDICATORS`), each with an absolute floor **and** a rate gate, render alongside as "other conditions observed" — informational, not inputs to the flag. At batch-1 volume most of the 92 employers have one call, so most are simply ineligible, not flagged-false — say so on the page. |
| 2 | Size-matched contact rate | A | BUILD | Metric 1: calls × (52 ÷ weeks in window) ÷ (that employer's own enrolled lives ÷ 1,000) — a per-1,000-lives, annualised rate. Lives are the calls' own population, never the book; dividing by book-wide enrolment is the denominator error the workbook names explicitly. Compared with the size-band peer median; show "+25% vs peers", never a bare rate. Min n 30 (Metrics sheet), not a placeholder. |
| 3 | Authority-weighted exit language | A | BUILD | Exit / market-test intent counts toward the exit family only from a contact with `CAN_BIND`. Member exit language is shown, not counted. |
| 4 | Failure-driven repeat contact | S | BUILD | Metric 4: numerator is UNRESOLVED calls followed by a contact from the same caller ≤14 days (same category is **not** a workbook condition — dropped); denominator is all UNRESOLVED calls in the 12wk window, excluding the last 14 days (no exposure period yet); min n 30. Computed, not extracted. Carries a cost view for free: Σ AHT of the repeat calls, same metric. |
| 5 | Escalation integrity | S | BUILD | Handled ÷ triggered. Always show the misleading figure (escalated ÷ all calls) beside it, labelled — keep `exec.html`'s adjacent-tile treatment. |
| 6 | Employer-caused member confusion | A | WITHHELD | No EMPLOYER value exists anywhere in `complaint.attributed_to`, and none is proposed short of the v10 schema change (§7A, D5). No partial path today — ship the withheld panel naming the missing value. |
| 7 | Broker-of-record drift | N | BUILD | Flag when the broker named aloud ≠ the employer's broker of record. A flag, not a ranking. Zero mismatches renders as a finding. |
| 8 | Account facts that raise the stakes | S | BUILD | Eligible / enrolled, participation, fee band, COBRA regime, sponsorship, lines, renewal month. Chipped *reference*; derived ones labelled derived. |
| 9 | Band calibration against renewal outcomes | A | WITHHELD | No termination outcomes exist. When they do: lapse rate per band, lift over base rate, and a **computed** caveat naming bands that don't separate or hold fewer than 10 groups. |

### Screen 2 — Broker and channel (`/hierarchy`)

| # | Insight | Origin | Status | Computation and rules |
|---|---|---|---|---|
| 10 | Broker book friction, split by cause | M | BUILD | **Counts lead.** `broker_named_aloud` present with `sentiment = ADVERSE`, per broker, at the call's touchpoint; the per-100-lives rate is a secondary sorting column only. No book under 150 lives is ranked. Book size from the Broker Master, never from call counts. (Rewritten from "fault records by party," which isn't a real field — see §7A.) |
| 11 | Enrolment promise gap | A | PARTIAL | `process_gap` present with `touchpoint = enrolment_meeting` or `enrolment_material`, per broker, with quotes; extended by `knowledge_failure` at those same touchpoints. Framed as an offer of help, not blame. Partial because it can't yet carry a fault *type* — that's the same missing field as insight 6. |
| 12 | Quiet-book warning | A | BUILD | Books far below median contact rate. A flag; withheld below volume. |
| 13 | Isolated or systemic | S | BUILD | Port `hierarchy.html`: the drill tree; region × category heatmap ("a dark column is book-wide, a dark cell is local"); the pattern test shown fired **and** unfired with what it reached. |
| 14 | Lives and revenue at risk by book | M | BUILD | Metric 10's display views, per broker: Σ enrolled lives, and Σ annual premium ("revenue at risk"), over employers carrying the flag. Presented as exposure, never as expected loss — there is no probability to apply to it. |

### Screen 3 — Where calls come from (`/demand`)

| # | Insight | Origin | Status | Computation and rules |
|---|---|---|---|---|
| 15 | Self-inflicted demand, costed | M | BUILD (money still withheld, D4) | **Two views, one catalogue entry, both on `/demand` (checked against both sources: the docx places insight 15 on "Screen 3 of 7 — Where calls come from," and Ranjit's mockup has no `/demand` page at all — that screen doesn't exist in Account Signals).** **View 1 — the demand itself:** metric 5, rewritten from "fault records with party WB" (not real — §7A) to its actual three components, **published separately, never blended** (Metrics sheet build note): (a) failure-driven repeats (insight 4/metric 4), (b) calls chasing an already-submitted action, (c) calls caused by a logged process defect — `process_gap.present = true` (L4); confirm this mapping in Phase 4 against the workbook, since "chasing an already-submitted action" vs "a logged process defect" may need two different `process_gap`/`signals` conditions, not one. Min n 60. Distinct-calls is the unit, not records. Beside it, the complaint-based cut (`complaint.attributed_to = CHOICE`) stays labelled as a different measure. **View 2 — costed, in minutes:** metric 9 cost-to-serve — Σ aht_seconds × (52 ÷ weeks) ÷ 60 per employer, vs the peer median, min n 30; money never enters this view; `cost_per_call` (D4) stays out of it entirely, not just withheld. **Also rendered on `/exec`** — checked Ranjit's mockup specifically for this view: `exec.html` already carries the near-exact tile ("What we charge against what it costs to serve," top employers by minutes/life vs median, fee and premium alongside, minutes-not-money framing) under its own "Is it working?" section, independent of self-inflicted demand. That's Ranjit's own placement, not the docx's — `/exec` gets View 2 only; View 1 (the three components) has no mockup home and renders solely on `/demand`. Phase 8's screens table lists insight 15 under both `/demand` and `/exec`, marked "(cost-to-serve view)" on the latter. |
| 16 | Touchpoint defect ranking | M | BUILD, extended PARTIAL | Calls per touchpoint with owner team — unchanged, `touchpoint` is a real single-valued field. Extension: coloured by `complaint.attributed_to` where present (4 real values), not a "dominant party" model that assumes fault records. |
| 17 | Proximate vs root cause | A | WITHHELD | This *is* the v10 schema change (§7A) — one touchpoint and one complaint target per call today, no second (root) record. Ship the withheld panel naming exactly what's missing. |
| 18 | The unattributed bucket | A→S | BUILD | Redefined: not an unattributed *fault* (no fault records exist), but calls whose touchpoint/complaint carries no clear upstream artefact — the same "no upstream artefact at fault" count that already feeds insight 16's touchpoint ranking. Check in Phase 6 that this doesn't just duplicate insight 16's residual bucket before giving it a separate panel. |
| 19 | Compliance exception exposure | S | BUILD | Counts by type; per agent and per week with a trend. |

### Screen 4 — Action centre (`/actions`)

| # | Insight | Origin | Status | Computation and rules |
|---|---|---|---|---|
| 20 | The action centre | S | BUILD | Port `actions.html`: lifecycle flow, board / table, evidence-chain drawer. |
| 21 | Where the work came from | S | BUILD | Items by the finding that produced them. |
| 22 | Did-it-work measurement | M | WITHHELD until data | Re-run an item's finding over a window after the fix. Withheld until a comparable before and after exist. Always a before-and-after, never causal. |

### Screen 5 — Rules, carriers and product (`/rules`)

| # | Insight | Origin | Status | Computation and rules |
|---|---|---|---|---|
| 23 | Rules we fail to explain | S | BUILD | Port `rules.html`, worded per how the workbook currently defines the tag — **not** "the D7 correction," since D7 is an open question to Karim, not a settled one (§5). Store and roll up `knowledge_failure` exactly as schema field 8 and metric 8's build note say: by rule ID, and by touchpoint. Counts, never a per-rule rate. Carry "commonly confused with". Never labelled an agent error, pending Karim's answer. |
| 24 | Rule provenance and confidence | S | BUILD | By provenance grade; unverified rules listed by id. |
| 25 | Plan-design confusion index | A | WITHHELD | `PLAN_AS_DESIGNED` and `MEMBER_COMPREHENSION` appear in neither the workbook nor `Insights-Worth-Building.docx` — not even proposed for v10. No path forward and nothing to raise with Karim; ship the withheld panel and say so plainly. |
| 26 | Carrier service scorecard | A | WITHHELD | No carrier entity and no carrier on the call in v9. Show only `complaint.attributed_to = CARRIER` counts, labelled. |
| 27 | Network adequacy clusters | A | PARTIAL | The region × Provider Network cells build; provider specialty and location are withheld. |

### Screen 6 — Agent and handling (`/agents`)

| # | Insight | Origin | Status | Computation and rules |
|---|---|---|---|---|
| 28 | Agent conduct against expected band | S | BUILD | Port `agents.html`: attributable events, not scores; roster vs corpus; band pooling; the harder-calls check. Agent-conduct events come from the **`knowledge_error` signal** ("an agent stated a published rule incorrectly," MEDIUM, owner Knowledge Management) — never from `knowledge_failure`, which is organisational regardless of touchpoint (D7). The two are independent and can fire with or without each other. |
| 29 | Member effort and complexity | S | BUILD | Always labelled as our composites, not v9 fields. |

### Screen 7 — Value pack (`/value-pack`)

| # | Insight | Origin | Status | Computation and rules |
|---|---|---|---|---|
| 30 | Quarterly value pack | A | PARTIAL — full only with the D5 v10 schema change | Per broker: calls handled, resolved first time, escalations handled of warranted, signals passed on. "What we caused" needs the party field D5 asks Karim for (§7A); until then the complaint-based figure, labelled. Opens with our own failures. |
| 31 | Commercial intent routing | M | PARTIAL | Expansion intent: verbatim quote, group, call reference — BUILD. The `routed` facet (metric 11's stated finding: whether it reached sales) is **not** a schema tag; derive it only from a linked Action Centre item, and only if that link exists in the ingested corpus. If no such link exists yet, withhold the `routed` facet specifically, with a stated reason — never default it to false. |
| 32 | Ancillary attach opportunity | A | BUILD | Groups without a line whose members call about that line. |

### Practices — everywhere

| Practice | Where it lives |
|---|---|
| Epistemic chip on every panel | a field in every response; `EpistemicChip` |
| Minimum-n suppression; withheld ≠ zero | backend aggregation; `Withheld`, `KpiTile tone="withheld"` |
| Shareable view state | URL search params mirrored to localStorage |
| No circular scoring | a test that fails if any aggregation reads `design_churn_profile` |
| Every figure opens its evidence | call ids in every response; the drawer |
| Filters slice, never hide | the applied-filters row always shows scope and count |
| Computed caveats | caveat text generated from the numbers, never hand-written |

---

## 10. Gates — before every commit

Backend (`Code/Backend`):

```bash
ruff check . && ruff format --check .
mypy .                                 # strict
lint-imports                           # layer contracts
pytest --cov --cov-fail-under=85
alembic heads                          # exactly one
```

Frontend (`Code/Frontend`):

```bash
npm run lint
npm run typecheck
npm run test:coverage                  # ≥80% lines, ≥75% branches
npm run generate:api                   # after any endpoint change; commit the result
```

`scripts/check.sh` runs all of them. Tests never call a live LLM — use recorded
responses. Every withheld state has a test that it renders withheld, not zero.

---

## 11. Known traps

- **Label leakage.** The PDF prints the answer next to the question (§6.3).
  Stripping is tested on all 100 calls, or evaluation means nothing.
- **Knowledge failure is not an agent error.** The Call Tag Schema: *"Must cite a
  rule ID… Naming the rule points at one article; naming the agent fixes
  nothing."* And touchpoint is *"where the failure originated, not where it
  surfaced."* On C-0001 the agent explains the waiting period correctly; the
  failure is that nobody explained it at enrolment. Ranjit's prototype labels
  this family "Agent stated a published rule incorrectly" — do not carry that
  wording over. See D7.
- **Workbook and PDF must be the matched pair.** The 17 Sep re-issue reassigned
  the caller on all 100 calls (C-0001 moved from CB-7700001 to CB-7700205).
  Either mismatched pairing is internally consistent, so nothing errors — every
  call is simply attributed to the wrong account. Use `_2` with `_1`; warn loudly
  on any call that fails to join or has no turns.
- **The header format changed once already** (`MEMBER CB-7700001 · Rowan Hollis`
  became `MEMBER · CB-7700205`). Parse defensively; a turn-count mismatch is the
  symptom of another change.
- **Speaker labels are first names on both sides.** NanoVox's parser treats an
  unqualified name as the agent, which would make every v9 turn the agent's.
  Resolve by the header's agent name.
- **Batch 1 is thin.** 100 calls across 92 accounts; 85 accounts have one call.
  Most rate-based figures will be withheld. That is the design working. Never
  lower a threshold to make a panel fill.
- **Circularity.** The churn profile generated the corpus. Nothing reads it.
- **Synthetic numbers.** Nothing from the deleted attribution prototype (Kestrel,
  Third Street, Meridian Dental, $15,933, 29%, 2,192 calls) is real. None of it may
  appear in code, tests, fixtures or copy.
- **The prototype's `data.js` is not a data source.** It is generated from the
  workbook's answer key. The app computes everything from its own tables.
- **Cost.** A full run is 100 calls × 4 stages. Use the stage cache, and run a
  5-call sample before any full run.

---

## 12. When to stop and check in

1. After §4 — repo initialised, `plan.md` confirmed excluded, bootstrap commit
   (ask first).
2. After §5 — until D1–D10 are answered.
3. After Phase 2 — show 100 calls resolved to accounts, zero leakage.
4. After Phase 5 — **the evaluation numbers.** Nothing in Phase 8 is shown to
   anyone until Minnie has seen them.
5. After Phase 8 — first full demo.

And after every three or four commits: push to `origin` per §2 rule 3 and say
so — name the branch and what went up. If `origin` is no longer the GitHub
repo, stop pushing and remind Minnie to push herself instead, with the exact
command.
