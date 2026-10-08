# NanoVox Insights — production readiness plan

**Window:** Monday 12 October – Friday 20 November 2026 (**30 working days, 6 weeks**)
**Team:** 2 developers, part time (~50% each) — **30 person-days of capacity**
**Target:** client pilot, real call data, split frontend/backend on Azure, single pipeline
**Written:** 2026-10-08

---

## 1. Read this before planning anything else

### The scope asked for does not fit the window. Here is the honest arithmetic.

Twenty person-days. The brief contains four things, and they are not the same size:

| Ask | Estimate | Fits? |
|---|---|---|
| Decisions and prep | **1.5 days** | yes |
| Migrate SQLite → Postgres | **4.5 days** | yes |
| Split frontend/backend, one pipeline | **5.75 days** | yes |
| Production hardening (secrets, monitoring, staging, backups) | **6.5 days** | yes |
| Cutover, drills, acceptance | **6.5 days** | yes |
| **Phases 0–4 total** | **28.25 days** | **vs 30 available** |
| **Real client data with PHI and SOC 2** | **33 days, plus work that is not development** | **no** |

### Six weeks, and the plan has moved twice — which is the point

| Draft | Window | Estimate | Capacity | Verdict |
|---|---|---|---|---|
| 1st | to 6 Nov | 24.75 | 20 | over by 4.75 |
| 2nd | to 13 Nov | 24.75 | 25 | +0.25 |
| **3rd** | **to 20 Nov** | **28.25** | **30** | **+1.75** |

The second extension absorbed scope; **the third absorbed seven gaps found by reviewing
the plan against the codebase** — chief among them that nothing in it mentioned
authentication, that CI would have gone on testing SQLite, and that the only
`TranscriptSource` implementation reads a PDF.

```
30 working days  ·  30 person-days capacity  ·  28.25 estimated  ·  +1.75 headroom
```

**Two extensions in two reviews is a signal, not a failure.** A first plan that survives
scrutiny unchanged has usually not been scrutinised. It is also the argument for **D0.6**:
the developers who will do this work should re-estimate it in week one, because the next
round of scrutiny is theirs and it will find things too.

**The extra weeks went into the back half, not spread evenly.** Phases 0–2 are the
best-understood work; Phase 2 now runs to 27 October (authentication), Phase 3 to
9 November, and Phase 4 to 20 November. The order at the end is deliberate: dress
rehearsal 13 Nov → **client sign-off 16–17 Nov** → **cutover Thursday 19 Nov** → buffer
20 Nov. An earlier draft had cutover landing before the client had accepted anything.

### +0.25 is arithmetic, not comfort

Real contingency is the buffer task plus that quarter-day — **about 5%** of the work. For
a plan containing a database migration and a dependency nobody on this team controls, 5%
is thin. So the cut list survives as a **fallback, not a plan**:

| If behind at the week-3 check-in | Saves | Why this one first |
|---|---|---|
| **B3.3** — trim the `/risk` payload | 1.5 d | 204 KB works today. It degrades *next*, it is not broken *now*. |
| **B4.1** — load test | 1.0 d | A pilot audience is a handful of readers; a 30-minute smoke under concurrency covers it. |
| **B2.2** — CORS fallback | 0.75 d | Contingent on A2.3 failing. If the linked backend works it disappears by itself. |

These stay in the baseline and are marked `FALLBACK CUT 1/2/3` in the tracker. They are
what goes if the plan slips — not what goes now.

**Do not cut:** A4.1 (restore drill), A3.4 (staging slot), A4.2 (runbook). A pilot without
a tested restore and a rollback path is not a pilot, it is an outage waiting for an
audience.

### These estimates are mine, and unvalidated

I have not done this work in this codebase, and a 25% variance on a first-pass estimate is
ordinary. **D0.6 asks both developers to re-estimate Phases 1–4 against their own
experience in week one.** If they come back at 18 days, there is real slack; at 30, five
weeks was the wrong question too — and 13 October is a much better day to learn that than
10 November.

### The fourth ask does not fit, and the gap is not a sequencing problem

### Why PHI changes everything

This is a health benefits call centre. Call transcripts contain member names, employers,
claim details and medical context. Under HIPAA that is **PHI, not merely PII**, and three
consequences follow immediately:

1. **Every transcript currently goes to `api.openai.com`.** `L2`, `L3` and `L4` extraction
   send call text to a third party. With real data and no Business Associate Agreement in
   place, that is a disclosure. **This is the single blocking item.**
2. **A BAA is a contract, not a config change.** It is signed by legal, not merged by a
   developer, and the lead time is typically weeks.
3. **SOC 2 is an audit of operating controls over time** — usually a 3–6 month observation
   window. Azure's own SOC 2 attestation covers the platform; it says nothing about this
   application. No four-week plan produces a SOC 2 report.

### So this plan does two things

- **Delivers in full** the architecture, database and pipeline work, in five weeks.
- **Names a hard gate** before any real call data enters the system, with the PHI work
  sized and sequenced as Phase 5 — outside this window, and starting in parallel now
  because its long poles are contractual.

> ### The gate
>
> **No production PHI is loaded until Phase 5 items P1–P6 are complete.** Until then the
> pilot runs on the existing fictional corpus, which is indistinguishable to a demo
> audience and carries no disclosure risk. This is a scheduling decision, not a technical
> one, and it is the recommendation of this plan.

---

## 2. Target architecture

```
                      ┌──────────────────────────┐
  browser  ─────────► │  Azure Static Web Apps   │   React bundle, CDN-backed
                      │  nanovox-web             │   Standard tier
                      └───────────┬──────────────┘
                                  │ /api/* proxied (SWA linked backend)
                                  ▼
                      ┌──────────────────────────┐
                      │  Azure App Service       │   FastAPI / uvicorn
                      │  nanovox-api  (B1→P0v3)  │   Python 3.14
                      └───────────┬──────────────┘
                                  │ private endpoint
                                  ▼
                      ┌──────────────────────────┐
                      │  Postgres Flexible Srv   │   B1ms, 7-day PITR
                      │  nanovox-db              │
                      └──────────────────────────┘

  Key Vault (secrets)  ·  App Insights (telemetry)  ·  one Azure DevOps pipeline
```

### Why Static Web Apps rather than a second App Service

**Use SWA's linked backend.** It proxies `/api/*` to the App Service from the same origin,
which means **no CORS configuration at all** — the property `spa.py` was written to
preserve, kept while still splitting the resources. The bundle also keeps its relative
`VITE_API_BASE_URL=/api/v1`, so it stays host-independent and needs no rebuild per
environment.

A second App Service for the frontend would cost more, serve no CDN, and force an absolute
API URL into the bundle. If the linked-backend proxy proves unsuitable (task **A2.3**
decides this), the fallback is SWA + explicit CORS, and that fallback is costed in the
plan rather than discovered.

### What stays

`spa.py` **is not deleted.** It keeps the single-process deployment working for local
development, the container image, and as a rollback path if the split misbehaves during
the pilot. Deleting it removes the fallback on the day it would be needed.

---

## 3. The two tracks

Work is split so the developers rarely block one another. Integration points are named and
dated.

| | **Track A — Platform** | **Track B — Application** |
|---|---|---|
| Owns | Azure resources, database, pipeline, secrets, telemetry | Application code, data access, frontend build, config, performance |
| Phase 1 | Provision Postgres, networking, backups | Verify migrations and data access on Postgres |
| Phase 2 | Provision SWA, restructure the pipeline | Split build, config, CORS/proxy decision |
| Phase 3 | Key Vault, App Insights, staging slot | Instrumentation, error handling, health checks |
| Phase 4 | Cutover, runbook, restore drill | Performance, acceptance pass |

**Integration points:** Fri 16 Oct (database), Fri 23 Oct (split), Wed 4 Nov (hardening),
Wed 11 Nov (dress rehearsal).

---

## 4. Phases

Status values: `Not started` · `In progress` · `Blocked` · `Done` · `Cut`

### Phase 0 — Decisions and prep · Mon 12 – Tue 13 Oct

Two days, both developers, and it is not optional. Four decisions below change later work;
taking them in week three means rework.

| ID | Task | Owner | Start | Due | Est (d) | Depends | Status |
|---|---|---|---|---|---|---|---|
| D0.1 | Confirm Postgres tier and region (B1ms, West US 3) and raise the request | A | 12 Oct | 12 Oct | 0.25 | — | Not started |
| D0.2 | Decide SWA linked-backend vs explicit CORS — spike both, pick one | B | 12 Oct | 13 Oct | 0.5 | — | Not started |
| D0.3 | **Start the Azure OpenAI / BAA conversation with legal** — long lead, blocks Phase 5 | A | 12 Oct | 12 Oct | 0.25 | — | Not started |
| D0.4 | Agree environment names and the staging story (slot vs second RG) | A+B | 13 Oct | 13 Oct | 0.25 | — | Not started |
| D0.5 | Confirm the pilot runs on the fictional corpus — write the gate down | A+B | 13 Oct | 13 Oct | 0.25 | — | Not started |
| D0.6 | **Both developers re-estimate Phases 1–4** against their own experience | A+B | 13 Oct | 13 Oct | 0.0 | — | Not started |
| **D0.7** | **ASK THE CLIENT: data volume, source system, export format, a sample** | A+B | 12 Oct | 13 Oct | 0.0 | — | Not started |

> **D0.3 is the one to do on day one.** Everything in Phase 5 waits on a contract, and the
> contract has a lead time nobody on this team controls.

---

### Phase 1 — Postgres · Wed 14 – Fri 16 Oct

**Smaller than it looks.** The codebase is already dialect-aware: `engine.py:52` branches
for `postgresql+asyncpg`, `integrity.py:40` and `migrations/env.py:44` guard the
SQLite-only paths, `settings.py` already accepts a Postgres URL, and `asyncpg` is already
a dependency. There are 15 migrations and the only non-trivial column type is **JSON, used
7 times** — native in Postgres.

| ID | Task | Owner | Start | Due | Est (d) | Depends | Status |
|---|---|---|---|---|---|---|---|
| A1.1 | Provision Postgres Flexible Server B1ms, private endpoint, firewall | A | 14 Oct | 14 Oct | 0.5 | D0.1 | Not started |
| A1.2 | Enable PITR (7 day), confirm automated backup schedule | A | 14 Oct | 14 Oct | 0.25 | A1.1 | Not started |
| A1.3 | Create DB, role, least-privilege grants — app user is not owner | A | 15 Oct | 15 Oct | 0.5 | A1.1 | Not started |
| B1.1 | Run all 15 migrations against Postgres; fix any dialect assumptions | B | 14 Oct | 15 Oct | 1.0 | A1.1 | Not started |
| B1.2 | Run the full backend suite against Postgres, not SQLite | B | 15 Oct | 15 Oct | 0.5 | B1.1 | Not started |
| B1.3 | Write the corpus loader: ingest into Postgres, repeatable and idempotent | B | 15 Oct | 16 Oct | 1.0 | B1.1 | Not started |
| B1.4 | Decide `backup.py`'s fate — it is SQLite-only and already no-ops elsewhere | B | 16 Oct | 16 Oct | 0.25 | B1.1 | Not started |
| A1.4 | Connection pooling: size `asyncpg` pool against B1ms connection limit | A | 16 Oct | 16 Oct | 0.5 | B1.1 | Not started |
| **A1.5** | **CI runs the suite against Postgres — service container** | A | 16 Oct | 16 Oct | 0.5 | B1.2 | Not started |
| B1.5 | Documented rollback to SQLite if Postgres fails mid-pilot | B | 16 Oct | 16 Oct | 0.5 | B1.1 | Not started |
| **✦** | **Integration point: app runs on Postgres, suite green** | A+B | 16 Oct | 16 Oct | — | — | Not started |

> **B1.2 is the task that earns the phase.** A suite that only ever ran on SQLite has not
> tested Postgres; `filterwarnings = ["error"]` and 1,600 tests will find the differences
> quickly, which is the point of running them before the pipeline does.

---

### Phase 2 — Split frontend and backend · Mon 19 – Tue 27 Oct

| ID | Task | Owner | Start | Due | Est (d) | Depends | Status |
|---|---|---|---|---|---|---|---|
| A2.1 | Provision Static Web App (Standard) — `nanovox-web` | A | 19 Oct | 19 Oct | 0.5 | D0.2 | Not started |
| A2.2 | Rename/retarget App Service as API-only — `nanovox-api` | A | 19 Oct | 19 Oct | 0.5 | — | Not started |
| A2.3 | Wire SWA linked backend; confirm `/api/*` proxies same-origin | A | 20 Oct | 20 Oct | 0.5 | A2.1, A2.2 | Not started |
| B2.1 | Frontend build artefact independent of the backend package | B | 19 Oct | 20 Oct | 1.0 | D0.2 | Not started |
| B2.2 | CORS middleware + `CORS_ORIGINS` wired — **fallback if A2.3 fails** | B | 20 Oct | 21 Oct | 0.75 | A2.3 | Not started |
| B2.3 | Keep `spa.py` working for local/container; add a test that it still serves | B | 21 Oct | 21 Oct | 0.5 | — | Not started |
| A2.4 | **One pipeline, two deploy stages**: build both, deploy API then web | A | 21 Oct | 23 Oct | 1.5 | A2.3, B2.1 | Not started |
| A2.5 | Deploy ordering + rollback: API first, web second, both revertible | A | 23 Oct | 23 Oct | 0.5 | A2.4 | Not started |
| **A2.6** | **Authentication after the split — where sign-in lives, SWA vs API** | A | 26 Oct | 27 Oct | 1.5 | A2.3 | Not started |
| **✦** | **Integration point: both resources deploy from one pipeline run** | A+B | 23 Oct | 23 Oct | — | — | Not started |

> **A2.4 is the heart of the brief.** One pipeline, two stages, one trigger. The API
> deploys first because the bundle calls it; the web deploy is the one that flips what a
> user sees, so it goes last and is the one you roll back.

---

### Phase 3 — Production hardening · Wed 28 Oct – Mon 9 Nov

| ID | Task | Owner | Start | Due | Est (d) | Depends | Status |
|---|---|---|---|---|---|---|---|
| A3.1 | Key Vault + system-assigned managed identity on the API | A | 28 Oct | 28 Oct | 0.5 | — | Not started |
| A3.2 | Move `OPENAI_API_KEY` and `DATABASE_URL` to Key Vault references | A | 29 Oct | 29 Oct | 0.5 | A3.1 | Not started |
| A3.3 | Application Insights on API; connection string via Key Vault | A | 30 Oct | 30 Oct | 0.5 | A3.1 | Not started |
| A3.4 | Staging slot on the API; pipeline deploys to staging then swaps | A | 2 Nov | 3 Nov | 1.0 | A2.4 | Not started |
| A3.5 | Alerts: availability, 5xx rate, p95 latency, DB connection failures | A | 4 Nov | 5 Nov | 0.75 | A3.3 | Not started |
| B3.1 | Structured request logging with correlation id into App Insights | B | 28 Oct | 29 Oct | 0.75 | A3.3 | Not started |
| B3.2 | Health endpoint reports DB and provider reachability for probes | B | 29 Oct | 30 Oct | 0.5 | — | Not started |
| B3.3 | **`/risk` payload: 204 KB and the first thing to degrade** — split or trim | B | 2 Nov | 3 Nov | 1.5 | — | Not started |
| B3.4 | Rate limiting on `/insights/generated` — it costs money per call | B | 6 Nov | 6 Nov | 0.5 | — | Not started |
| A3.6 | Azure budget alert on the subscription, and on OpenAI spend | A | 9 Nov | 9 Nov | 0.25 | — | Not started |
| **✦** | **Integration point: staging swap works, telemetry flowing, alerts fire** | A+B | 4 Nov | 4 Nov | — | — | Not started |

> **B3.4 is not optional once this is public.** `/insights/generated` bills OpenAI per
> request and the insight cache dies with the process. An unauthenticated public endpoint
> that costs money per call is a billing incident waiting for a crawler.

---

### Phase 4 — Pilot readiness and cutover · Mon 9 – Fri 20 Nov

| ID | Task | Owner | Start | Due | Est (d) | Depends | Status |
|---|---|---|---|---|---|---|---|
| A4.1 | **Restore drill**: restore Postgres from PITR into a scratch server | A | 9 Nov | 9 Nov | 0.75 | A1.2 | Not started |
| A4.2 | Runbook: deploy, roll back, restore, rotate a secret, read an alert | A | 10 Nov | 11 Nov | 1.0 | A3.5 | Not started |
| A4.3 | Entra sign-in re-enabled and tested for the pilot audience | A | 12 Nov | 12 Nov | 0.5 | — | Not started |
| B4.1 | Load test: 20 concurrent readers against `/exec` and `/risk` | B | 9 Nov | 10 Nov | 1.0 | B3.3 | Not started |
| B4.2 | Full acceptance pass — nine screens, write path, CSV export | B | 11 Nov | 12 Nov | 0.75 | — | Not started |
| B4.3 | Error budget check: no unhandled 5xx in 48 h of staging | B | 12 Nov | 13 Nov | 0.5 | A3.4 | Not started |
| **B4.4** | **CLIENT ACCEPTANCE: the client signs off, not a developer** | A+B | 16 Nov | 17 Nov | 0.5 | M4 | Not started |
| A4.6 | Decide `RG-NanoVox-POC`'s fate — torn down, or kept as staging | A | 17 Nov | 17 Nov | 0.25 | — | Not started |
| **✦** | **Dress rehearsal: full deploy to staging, swap, verify, roll back** | A+B | 11 Nov | 11 Nov | 0.5 | — | Not started |
| A4.4 | Production cutover | A+B | 19 Nov | 19 Nov | 0.5 | all | Not started |
| A4.5 | Buffer / contingency | A+B | 20 Nov | 20 Nov | 1.0 | — | Not started |

> **A4.5 is deliberate.** A plan with no slack is a shorter plan that fails at the end. It
> is the last working day of the window; if unused, it absorbs Phase 5 prep.

---

## 5. Phase 5 — PHI, PII and SOC 2 · **Outside this window**

**Estimated 30–45 developer-days, plus legal and audit work that is not development.**
Items **P1–P6 are the gate**: production PHI must not be loaded until they are complete.

### The blocking item

| ID | Item | Est (d) | Why |
|---|---|---|---|
| **P1** | **Move from OpenAI to Azure OpenAI, under a signed BAA** | 5–8 | Transcripts containing PHI currently leave for `api.openai.com`. Microsoft signs BAAs and keeps data in your tenant and region; OpenAI's own BAA is possible but a separate negotiation. **Needs an adapter — D1 explicitly declined to build one, so this is new code.** `OPENAI_BASE_URL` already exists and may reach Azure's v1-compatible endpoint, which would shorten this considerably — unverified. |
| **P2** | De-identification before any model call | 5–8 | Strip or tokenise member names, DOB, member IDs and addresses before L2/L3/L4. Reversible mapping held application-side. Reduces exposure even with a BAA in place. |
| **P3** | Encryption and key management review | 2–3 | Azure encrypts at rest by default; decide whether customer-managed keys are required, and confirm TLS enforcement end to end. |
| **P4** | Access control and audit logging | 4–6 | Who may see which employer's calls. Today anyone signed in sees everything. Plus an immutable audit log of reads, which SOC 2 will ask for. |
| **P5** | Retention and deletion | 3–5 | How long transcripts live, how a deletion request is honoured end to end including backups and the stage cache. |
| **P6** | Private networking | 3–4 | VNet integration, private endpoints for Postgres and Key Vault. **Note the interaction:** VNet integration breaks default outbound to `api.openai.com`, so P6 and P1 must be designed together. |

### After the gate

| ID | Item | Est (d) | Why |
|---|---|---|---|
| P7 | SOC 2 readiness assessment | — | Not development. Gap analysis against the Trust Services Criteria. |
| P8 | Change management evidence | 2 | Mostly already true — PR review, branch policy, pipeline gates — but it must be *evidenced*, not merely practised. |
| P9 | Incident response plan and on-call | 2 | Required for SOC 2 Availability. |
| P10 | Vendor management register | 1 | Azure, OpenAI/Azure OpenAI, Azure DevOps — each a subprocessor. |
| P11 | Penetration test | — | External. Budget 2–4 weeks lead time. |

> **SOC 2 is not a sprint.** Type I attests the controls exist on a date; Type II attests
> they operated over 3–12 months. The earliest useful target is Type I after Phase 5, with
> the Type II observation window starting then.

---

## 5A. PII, PHI and SOC 2 — what I would actually do

You asked for a recommendation on this front. Here it is, shortest useful form first.

### The one decision that matters most

**Move the model calls to Azure OpenAI, and do it before real data arrives.**

Not because Azure OpenAI is better at the task — it is the same models — but because of
three properties that have nothing to do with quality:

| | OpenAI platform | Azure OpenAI |
|---|---|---|
| BAA for HIPAA | Possible, negotiated separately | **Standard, via Microsoft's existing agreement** |
| Where the data sits | OpenAI's infrastructure | **Your tenant, your chosen region** |
| Training on your data | Off by API default | **Contractually off** |
| Already in your Azure spend and vendor register | No | **Yes** |

**This reverses advice I gave earlier in this project.** When the question was "which
provider for a demo on fictional data", I said Azure OpenAI was unsupported here and not
worth the work — decision D1 declined to build an adapter, and that was right for a demo.
With real PHI the calculus inverts completely: the adapter is a few days, and the
alternative is a disclosure.

**The encouraging part:** `OPENAI_BASE_URL` is already a setting and
`openai_provider.py` passes it straight to the SDK, so Azure's OpenAI-compatible `/openai/v1/`
endpoint may work with no new adapter at all. Unverified — task **P1** proves or disproves
it in a day, and it is worth proving early because it is the difference between 1 day and 8.

### De-identify before the call, not instead of the BAA

A BAA makes disclosure lawful. It does not make it wise. **P2** strips member names, dates
of birth, member IDs and addresses before any transcript leaves the process, holding the
reversible mapping application-side.

This costs some extraction quality and that trade-off should be measured, not assumed —
the evaluation harness in `Phase-5-Findings.md` already exists to measure exactly this sort
of thing, which makes the question answerable rather than arguable.

### What you already have, and should get credit for

Several SOC 2 controls are genuinely in place, just not evidenced:

- **Change management** — every change goes through a PR, a branch policy and a CI gate.
  SOC 2 asks for exactly this. **P8** is about producing evidence, not new practice.
- **Encryption** — Azure encrypts at rest and TLS is enforced. **P3** is a review.
- **Audit trail of code** — Azure Repos has it.
- **Secret handling** — about to be, once **A3.2** lands. Key Vault plus managed identity
  is the control an auditor expects to see.

### What is genuinely missing

- **Authorisation.** Anyone who signs in sees every employer. For a pilot with one
  customer that is survivable; for PHI it is not, and **P4** is the largest of the six.
- **An audit log of reads.** Who looked at which member's call, and when. Nothing records
  this today. It is the question an auditor asks first and the hardest to retrofit, which
  is an argument for doing it early.
- **Retention and deletion.** No policy, and the mechanics are awkward: a deletion has to
  reach the database, the backups and `StageCache`. **P5**.

### Sequencing, and the one trap

**P1 and P6 must be designed together.** Private networking is the obvious hardening step
and VNet integration is how you get it — but VNet integration **breaks default outbound
internet access**, which is how the app reaches a model provider today. Doing P6 first
silently kills every insight; doing P1 first means the endpoint is already inside your
network and P6 becomes straightforward.

### What I would not do

- **Do not chase SOC 2 Type II before the pilot.** Type II attests that controls *operated*
  over 3–12 months. You cannot shorten it by trying harder. Type I after Phase 5, with the
  Type II window starting then, is the realistic path.
- **Do not build a custom audit-log store.** App Insights plus a dedicated table is enough,
  and an auditor is more comfortable with boring.
- **Do not de-identify by regex alone.** Names in free-text transcripts defeat it. Use the
  structured fields you already extract as the primary signal, with pattern matching as a
  backstop.

---

## 5B. Phase 6 — getting real client data in · **Outside this window**

**~15.5 developer-days, and the first task is a question, not code.**

This phase exists because reviewing the plan against the codebase found the gap it was
built on: **`PdfCorpusSource` is the only implementation of `TranscriptSource`.** It parses
the v9 build-bible PDF with regexes written for that document's layout. A real client
exports from Genesys, Five9, NICE or a CSV — none of which is that PDF.

Phase 1 moves the *database*. Nothing in Phases 0–4 moves the *data*.

| ID | Item | Est (d) | Why |
|---|---|---|---|
| **R1** | **Obtain a real sample and its format from the client** | 0 | Blocks everything below and costs nothing. Started as **D0.7** in week one. |
| **R2** | `TranscriptSource` adapter for the real format | 7.5 | A placeholder until R1 lands. Could be 3 days for a clean CSV or 15 for an audio pipeline with diarisation. |
| R3 | Re-size Postgres, App Service and `/risk` against real volume | 2 | Everything is sized for 600 calls and 4 MB. At 50,000 the ~290 ms corpus load and the 204 KB payload are different problems. |
| **R4** | **Model the extraction cost before running it** | 1 | 600 calls went through L2/L3/L4 once. At tens of thousands, extraction is plausibly the largest line in the project and nobody has costed it. |
| R5 | Onboarding runbook and a repeatable re-ingest path | 2 | A one-off import is not an onboarding. |
| **R6** | **UAT with the client on real data** | 2 | The only acceptance that counts. |
| R7 | Define and agree an uptime target, and measure against it | 1 | "Production-grade" with no number is not a commitment. |

> **R2's estimate is the least trustworthy number in this document**, and it is load-bearing.
> That is the argument for **D0.7**: ask in week one, so the uncertainty is priced in
> October rather than discovered in December.

---

## 6. What is explicitly not in this plan

Named so their absence is a decision rather than an oversight:

- **Multi-tenancy.** One corpus, one customer. Per-tenant isolation is a product change.
- **Real-time ingestion.** The pipeline is offline and batch; this plan does not change it.
- **The open UX findings.** Tracked separately in `UX-Review.md`.
- **Mobile layout.** Review finding 3; still open, still a product decision.
- **Horizontal scale.** B1ms Postgres and one API instance suit a pilot, not a product.
- **Disaster recovery across regions.** Single region. PITR covers data loss, not outage.

---

## 7. Risks

| Risk | Likelihood | Impact | Response |
|---|---|---|---|
| BAA lead time exceeds the window | **High** | Blocks real data | D0.3 on day one; pilot on fictional corpus regardless |
| SWA linked backend unsuitable | Medium | +1 day | D0.2 spikes both; CORS fallback costed as B2.2 |
| Migrations fail on Postgres | Low | +1–2 days | 15 migrations, already dialect-aware; B1.1 finds it in week one |
| Part-time capacity slips | **High** | Scope cut | A4.5 buffer; the three fallback cuts |
| **Client's data format is not what anyone assumed** | **High** | Phase 6 doubles | **D0.7 in week one.** `PdfCorpusSource` is the only adapter that exists |
| Extraction cost at real volume is unaffordable | Medium | Pilot scope | R4 models it *before* running it |
| Real volume breaks the current sizing | Medium | Re-architecture | R3; `/risk` and the ~290 ms corpus load are the first to go |
| `/risk` payload degrades under real volume | Medium | Pilot quality | B3.3; already the known weak point at 204 KB |
| Two part-time developers never overlap | Medium | Integration drag | Four named integration points; keep them |

---

## 8. Cost

| Resource | Tier | Monthly |
|---|---|---|
| App Service plan | B1 Linux | ~$13 |
| Static Web Apps | Standard | ~$9 |
| Postgres Flexible Server | B1ms + 32 GB | ~$15 |
| Key Vault | Standard | ~$1 |
| Application Insights | pay-as-you-go | ~$5 |
| | **Total** | **~$43/month** |

Plus OpenAI (or Azure OpenAI) usage, billed separately and driven by restarts as much as
by readers, since the insight cache dies with the process.

> B1 App Service has no autoscale and one instance. That suits a pilot. A product needs
> P0v3 or better and at least two instances, which roughly triples the compute line — out
> of scope here, and the first thing to revisit after the pilot.

---

## 9. How to track this

`Production-Plan-Tracker.xlsx`, beside this file. One row per task, matching IDs. Update
**Status** and **% complete**; the summary sheet is formula-driven and follows.

Suggested rhythm for two part-time developers: a written check-in at each of the four
integration points, and a status change the day it happens rather than the day before the
next check-in.
