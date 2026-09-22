# NanoVox Insights

A call-intelligence application for a general agency in US employee-benefits
insurance: it reads raw call transcripts, extracts a fixed set of facts from
each call with an LLM, joins every call to the employer, broker and member it
belongs to, and renders business insights across seven screens. Three source
documents govern the build, and they outrank each other on different
questions, not on all of them: the v9 workbook wins on definitions — the data
model, the Call Tag Schema, metric formulas, denominators, windows, minimum n,
triggers; Ranjit's Account Signals prototype wins on presentation — layout,
visuals, interaction; `Insights-Worth-Building.docx` wins on scope — which
insights, why, and the principles behind them. The import commands and an
architecture diagram will follow as the codebase is built.

## Setup

Backend (`Code/Backend`):

```bash
python -m venv .venv
./.venv/Scripts/pip install -r requirements-dev.txt   # .venv/bin/pip on macOS/Linux
cp .env.example .env
alembic upgrade head
python -m uvicorn frameworks_drivers.main:app --reload
```

Frontend (`Code/Frontend`):

```bash
npm install
cp .env.example .env
npm run dev
```

## Before every commit

```bash
./scripts/check.sh
```

Runs every gate: backend format, lint, strict types, the Clean Architecture
import contracts, tests with coverage, and the single-migration-head check;
frontend lint, strict types, tests with coverage, and the typed API client
regenerated from the backend with no diff. Needs a backend `.venv` set up as
above. Never commit past a failing gate, and never weaken a gate to make it
pass.
