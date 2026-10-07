# Deploying NanoVox Insights to Azure

Last revised 2026-10-07. Written against the repo as it stands on `main`
(Python 3.14, container image, Azure DevOps lint pipeline). Each claim about the
app points at the file that settles it. Each claim about Azure was read from
Microsoft Learn on the revision date; anything not checked is marked
**unverified**, and no dollar figures are quoted because none were checked.

> **Status.** Nothing in this guide has been run against a real Azure
> subscription. The container image behind section 8.2 has been built and run
> locally (section 3); the App Service / Oryx path behind the section 0
> recommendation has not, and section 3 says so explicitly. Every `az`
> command below is a sketch to be proven, not a record of something that
> worked. Section 9 lists what has to be true before anyone calls it
> deployed.

---

## 0. Recommendation

**Azure App Service (Linux, B1), running the app's own SQLite database copied
to `/tmp` at startup.** One resource, no database server, no registry, HTTPS
and built-in sign-in included.

| | Needed | Why |
|---|---|---|
| Resource group | Yes | One teardown unit |
| App Service plan, **Linux** (B1 or higher) | Yes | Always On; the Free tier unloads when idle (section 9) |
| App Service (Web App), `PYTHON\|3.14` | Yes | Runs the app from an Oryx source build |
| Authentication or network restriction | **Yes, before any real data goes on it** | The app has no login (section 1) |
| Azure OpenAI resource + model deployment | Optional | Keeps transcript content inside your tenant; needs no code change in principle (section 6) |
| Application Insights | Optional | The app has no App Insights SDK; App Service's own log stream already gets stdout |
| Front Door / Application Gateway + WAF | Optional | Only if the client wants a WAF or a custom domain with managed certificates |

**You do not need:** a database server, Azure Container Registry, Static Web
Apps, a separate API host, API Management, a storage account, Azure Files,
Azure Disk, a second app, nginx, or CORS configuration. The API process serves
the frontend, and the database that already ships with the repo is the one
that runs in production.

**The trick, and its one cost.** App Service's persistent `/home` is an SMB
share, which SQLite cannot write to safely (section 2); `/tmp` is real
container-local disk. The startup command copies the pristine database there
before `uvicorn` starts, so SQLite runs the way it is designed to. The cost:
**action-board edits do not survive a restart** — each restart starts again
from the pristine copy. For a two-week demo that is a reasonable trade, and
arguably a feature: every restart is a clean demo.

**The alternative**, if writes have to survive a restart, is Azure Container
Apps running the tested Docker image, with Azure Database for PostgreSQL for
storage — a registry and a database server, for durability App Service's
free tier of this trick cannot give. Section 8 covers both.

---

## 1. What is being deployed

| Fact | Detail | Where it is settled |
|---|---|---|
| One process, one port | The API serves the built frontend. No CORS, no second origin. | `Code/Backend/frameworks_drivers/spa.py`, `main.py` |
| Python 3.14 | Image, pipeline and scripts all moved to 3.14. | `Dockerfile`, `azure-pipelines.yml` |
| Node 20 at build time only | Frontend is built in the image's first stage. | `Dockerfile` |
| Port comes from `$PORT` | The container `CMD` binds `0.0.0.0:${PORT}`, default 8000. `APP_PORT` is not what the container uses. | `Dockerfile` |
| Migrations run on start **in the container image** | `alembic upgrade head` precedes uvicorn, so an empty Postgres gets its schema on first boot. The App Service startup command (section 8.1) deliberately skips this — the shipped SQLite file already carries the schema it was tested against. | `Dockerfile` `CMD` |
| Health endpoint | `GET /api/v1/health`, per-component, 503 when a component is down. | `frameworks_drivers/api/v1/health.py` |
| Database | SQLite (default) or Postgres via `DATABASE_URL`. **Only** `sqlite+aiosqlite:` and `postgresql+asyncpg:` are accepted; anything else fails at startup. SQL Server is not supported. | `infrastructure/config/settings.py` |
| The database is written to | The action board has `POST` and `PATCH` endpoints. It cannot be baked in read-only. | `frameworks_drivers/api/v1/insights/action_board.py` |
| LLM providers | `openai` (default, `gpt-4o-mini`), `anthropic`, `ollama`. No Azure adapter. `OPENAI_BASE_URL` is honoured. | `infrastructure/llm/registry.py`, `settings.py` |
| In-process state | The insight cache and the background run runner live in the process. They do not survive a restart and are not shared between replicas. | `infrastructure/cache/insight_cache.py`, `infrastructure/runner/background_runner.py` |
| API docs off in prod | `/docs` and `/openapi.json` are disabled when `APP_ENV=prod`. | `main.py` |
| Corpus size | The database is about 2.7 MB (600 calls). The source PDFs and workbook are not needed at runtime; `.dockerignore` excludes them. | `data/db/`, `.dockerignore` |
| **No authentication** | Decision D14: "trusted network, single tenant." No login, no roles. | `Revised-Implementation-Plan.md` R9 / D14 |

### The authentication gap matters on Azure

D14 assumed a trusted network. An app reachable at a public `.azurewebsites.net`
(or Container Apps) URL is on the public internet. That has two consequences:

1. The data is member call transcripts and insights derived from them, readable
   by anyone with the URL.
2. `POST` endpoints under `/api/v1/runs`, `/api/v1/ingest` and
   `/api/v1/reference` are unauthenticated. The run endpoints start LLM work, so
   an anonymous caller can spend the provider budget.

Pick one before the URL goes to anyone: platform authentication (App Service's
built-in Entra ID sign-in needs no code change and is configured on the app
itself; the Container Apps equivalent is **unverified** here), restricting
ingress to known IP ranges, putting the app on a private network reachable by
VPN, or fronting it with Front Door and WAF. This is a decision for the
project, because D14 is Minnie's call and was made for a different environment.

---

## 2. Storage: SQLite on `/tmp`, or Postgres

The rule that governs everything here: **SQLite needs a real block device and
exactly one writer.** Whether that is available depends on which of the two
candidate services is running the app.

**App Service for Linux has one.** `/home` is an SMB share and App Service's
own docs say plainly not to put a file-locking database like SQLite on a
storage mount: *"We don't recommend that you use storage mounts for local
databases, such as SQLite, or for any other applications and components that
rely on file handles and locks."* **`/tmp`, however, is container-local disk,
not the share** — so the recommendation (section 0) copies the pristine
database there at startup and SQLite runs on a real block device, exactly as
it expects. The one cost is durability: `/tmp` does not survive a restart, so
neither does an action-board edit. A local test of SQLite on a
protocol-backed mount (Docker Desktop's gRPC-FUSE bind mount) failed outright
with `disk I/O error` — confirming the docs' warning is not theoretical,
which is also why `/tmp` and not a storage mount is the part that makes this
work at all.

**Container Apps has no equivalent.** It supports container-scoped
(ephemeral) storage, replica-scoped (EmptyDir) storage, and Azure Files over
SMB or NFS. **Azure Disk is not supported.** Blob and Azure NetApp Files
mounts are not supported either. An earlier revision of this file recommended
an Azure Disk mount; that option does not exist. Without a durable mount,
SQLite on Container Apps' own ephemeral disk loses every action-board change
on restart with no `/tmp`-style trick available to avoid it — so a Container
Apps deployment that needs writes to survive a restart has to move the
database off the container entirely.

**So, for Container Apps: Postgres.** The code already supports it (`asyncpg`
is in `requirements.txt`, and `engine.py` disables asyncpg's statement cache
for pooled endpoints). Two caveats, both unproven on Azure:

- The test suite touches Postgres only at the unit level (settings and engine
  construction). I found no test that runs the 16 Alembic migrations or the
  application against a real Postgres. Treat the first `alembic upgrade head`
  against Azure Postgres as a test, not a formality.
- SQLite-only protections do not apply: the pre-run backup
  (`infrastructure/persistence/backup.py`) and the write lock
  (`database_write_lock.py`) are no-ops for Postgres. Backups become Azure's
  job (Flexible Server automated backups).

**Burstable tier**, if Postgres is the path taken. B1ms (1 vCore, 2 GiB), B2s
(2 vCores, 4 GiB) and larger Burstable sizes exist. Microsoft describes
Burstable as suited to proof of concept and development, not recommended for
production, with a CPU-credit model that degrades when credits run out. That
fits a POC pitched to a client; if this becomes the client's production
system, move to General Purpose.

---

## 3. What has been proven locally

**The container image, which is the Container Apps path.** The `Dockerfile`
builds a multi-stage image (Node 20 builds the frontend, `python:3.14-slim`
runs it). The image runs as uid 10001, exposes 8000, declares `/app/data` as a
volume and has a `HEALTHCHECK` on `/api/v1/health`. The layout is
load-bearing: `paths.py` derives `PROJECT_ROOT` from `__file__`, so the image
keeps `/app/Code/Backend` and `/app/Code/Frontend/dist`. Flattening it makes
the process serve the API alone and 404 every page.

`release/` holds a packaged image tarball with `run.sh` and `run.ps1` for
running it on any machine with Docker. That is the tested path today, and it
is not an Azure path.

Two findings from running it that still apply:

- A pre-seeded volume keeps the ownership it was written with, so any copy of a
  SQLite file into it must end with `chown -R 10001:10001 /app/data`. This only
  matters for SQLite deployments.
- The action board writes, so "read-only database" is not an option.

**The App Service / Oryx path is not covered by the above.** Oryx does a
source build (installs from `requirements.txt`, does not read the
`Dockerfile`), so none of the container testing validates it. Nothing in this
repo has run `python -m venv` plus `pip install` the way Oryx does, or
confirmed Oryx detects this as a Python app from the root `requirements.txt`
pointer. Treat the App Service deploy in section 8.1 as the thing section 9
exists to prove, same as everything else on this page.

---

## 4. Do we have a deployment script?

**For Azure: no.** There is no `az` script, no Bicep or Terraform, and no
deployment stage in any pipeline. What exists:

| File | What it does | Use on Azure? |
|---|---|---|
| `scripts/deploy.ps1` | Windows: installs deps, migrates, builds the frontend, registers a Task Scheduler task, verifies. | Only for a Windows VM |
| `scripts/deploy.sh` | macOS: same steps with launchd. On Linux it does everything except service registration and prints the run command. Requires Python 3.13 or 3.14. | Only for a Linux VM, and you would write the systemd unit |
| `scripts/start.sh` / `start.bat` | Development: two servers on 127.0.0.1. | No |
| `scripts/check.sh` / `check.bat` | Runs every CI gate locally. | No |
| `scripts/cloudflared/config.example.yml` | Publishes a deployment through a Cloudflare Tunnel. | No |
| `release/run.sh` / `run.ps1` | Loads the shipped image, seeds a Docker volume with the database, starts it. | No; Docker-only |
| `Dockerfile` | The image. This is what Container Apps would run. | **Yes** |
| `azure-pipelines.yml` | Lint, type, test and migration-head gate. `trigger: none`; it runs only through a Build Validation branch policy, and it does not build, push or deploy. | Gate only |

None of the deploy scripts load data. They run `alembic upgrade head`, which
creates empty tables, so a freshly deployed target shows every screen in its
withheld state (0 calls, no accounts). That looks like a broken app and is the
app behaving correctly.

**Gaps to close for an Azure deployment:** an `az` (or Bicep) provisioning
script, a data-load step (section 7), and optionally a pipeline stage that
redeploys on push — `az webapp up` for App Service, or `az acr build` plus a
Container App update for the alternative. All are changes to the repo and are
not made here.

---

## 5. Architecture

```
 Browser ──HTTPS──> [ auth / network restriction ]
                              │
                      App Service (Linux, B1)
                    ┌───────────────────────────┐
                    │ uvicorn: API + built SPA │── console ──> Log stream
                    │  sqlite file, copied      │
                    │  /home ──copy──> /tmp      │              (section 6)
                    └─────────────┬─────────────┘
                                  │ HTTPS
                                  ▼
                          OpenAI / Anthropic
                           or Azure OpenAI
                              (optional)
```

**The alternative (Container Apps + Postgres):**

```
 Browser ──HTTPS──> [ auth / network restriction ]
                              │
                    Container Apps environment
                    ┌───────────────────────────┐
                    │ Container App (1 replica) │── stdout ──> Log Analytics
                    │  uvicorn: API + built SPA │
                    └─────┬─────────────┬───────┘
                          │             │ HTTPS
          postgresql+asyncpg            ▼
                          ▼        OpenAI / Anthropic
        PostgreSQL Flexible Server     or Azure OpenAI
                                   (optional)

   Azure Container Registry ──image──> Container App
   Key Vault / app secrets  ──secrets─> Container App
```

Keep **min and max replicas / instances at 1** on either path. App Service's
`/tmp` copy is per-instance, so a second instance starts from its own pristine
copy and the two disagree the moment either one gets a write; on Container
Apps with Postgres the database no longer forces this, but the insight cache
and the background runner are per-process either way, so a second
replica/instance means duplicate LLM spend and a run that is "in flight" on
one and invisible to the other.

---

## 6. Configuration

All settings are environment variables read in
`infrastructure/config/settings.py`. On App Service these are App Settings; on
Container Apps, environment variables and secrets. Never a `.env` file shipped
with the code (`.dockerignore` already excludes `.env*`).

| Variable | Value for App Service + SQLite | Notes |
|---|---|---|
| `APP_ENV` | `prod` | Disables `/docs`. |
| `DATABASE_URL` | `sqlite+aiosqlite:////tmp/nanovox/nanovox_insights.db` | Four slashes: `sqlite+aiosqlite:///` plus the absolute `/tmp/...` path. The startup command (section 8.1) is what puts a database file there. |
| `LLM_PROVIDER` | `openai`, `anthropic`, or `ollama` | `ollama` makes the AI panels show their designed "unavailable" state and costs nothing. |
| `OPENAI_API_KEY` | key | **Secret.** |
| `OPENAI_MODEL` | `gpt-4o-mini` default | With Azure OpenAI this is the **deployment name**. |
| `OPENAI_BASE_URL` | empty, or `https://<resource>.openai.azure.com/openai/v1/` | See below. |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | if using Anthropic | **Secret** key. |
| `LOG_LEVEL`, `LOG_FORMAT=json`, `LOG_TO_CONSOLE=true` | defaults are fine | Console output is what App Service's log stream (or Log Analytics, on Container Apps) collects. File logs under `.../data/logs` are lost on restart either way. |
| `LOG_LLM_PROMPTS` | leave `false` | Transcripts are member conversations. |
| `FRONTEND_DIST_PATH` | the built `dist`'s absolute path on the host, e.g. `/home/site/wwwroot/Code/Frontend/dist` | `paths.py` derives a default from its own `__file__`, and App Service's Oryx layout is not the checkout's — set this explicitly or the API serves with no frontend. |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` | Tells Oryx to run the build step (installs from the root `requirements.txt` pointer) rather than serve the push as-is. |

**On the Container Apps + Postgres alternative**, `DATABASE_URL` instead reads
`postgresql+asyncpg://<user>:<password>@<server>.postgres.database.azure.com:5432/<db>`
(**secret**; URL-encode special characters in the password — Flexible Server
requires TLS by default, and asyncpg takes `?ssl=require`, **unverified**,
check on first connect), and `FRONTEND_DIST_PATH` is not needed because the
image already has the built frontend baked in at a fixed path.

**Azure OpenAI without code changes (unverified end to end).** The OpenAI
adapter passes `OPENAI_BASE_URL` to the SDK. Microsoft documents the v1 API as
usable from the standard `OpenAI` client with `base_url` set to
`https://<resource>.openai.azure.com/openai/v1/`, an API key, and the
deployment name as `model`. Strict structured outputs, which this adapter relies
on, are supported on `gpt-4o-mini`, `gpt-4.1` and the `gpt-5` family. Two
things to test: the adapter's reasoning-model check matches on the *model
string* (`gpt-5*`, `o<digit>*`), which for Azure is whatever you named the
deployment, so a deployment named differently from its model will be sent the
wrong parameters; and `ProviderUnavailableError` handling against Azure's error
shapes. Keys can be replaced with Entra ID tokens only with a code change.

---

## 7. Getting the data onto the host

**Do not rebuild the corpus on Azure either way.** Doing it means
`frameworks_drivers.cli.run_extraction`, which sends every call through an
LLM: hours of runtime and real spend. The existing database already has it.

**App Service + SQLite: copy the file, nothing more.** The corpus database is
about 2.7 MB (`data/db/nanovox_insights.db`). Upload it to the app's persistent
`/home` once (the Kudu console's file manager, or `az webapp ssh`), and the
startup command in section 8.1 copies it onto `/tmp` on every boot. No
Alembic, no row-count reconciliation — the shipped file already carries the
schema the app was tested against, and `main.py`'s lifespan does not run
migrations at startup.

**Container Apps + Postgres: there is no existing tooling for this, and it is
the real work item of that path.** The CLI folder has `import_reference.py`,
`import_answer_key.py`, `ingest_transcripts.py` and `seed_actions.py`, but
nothing that copies an existing SQLite database into Postgres. A one-off copy
script (or a tool like pgloader) is needed, followed by checking row counts
per table and one click-through of the action board. Order matters here in a
way it does not for SQLite: start the app once so `alembic upgrade head`
creates the schema, then load data into it — Alembic's version table has to
end up consistent with the loaded schema, or the next start tries to
re-migrate.

**Check afterwards, on either path.** `/api/v1/insights/exec` should report
600 calls.

---

## 8. Steps (a sketch, not a record)

### 8.1 App Service + SQLite path (the recommendation)

**1. Build the frontend locally.** Oryx will not run `npm run build` for a
Python app, so `dist` must exist in what gets built.

```bash
cd Code/Frontend && npm ci && npm run build
```

**2. Create the resources.**

```bash
az login
az group create --name nanovox-demo --location <region>

az appservice plan create --name nanovox-plan --resource-group nanovox-demo \
  --sku B1 --is-linux

az webapp create --name nanovox-insights --resource-group nanovox-demo \
  --plan nanovox-plan --runtime "PYTHON:3.14"
```

**3. Configure** (section 6's table, App Service column).

```bash
az webapp config appsettings set --name nanovox-insights --resource-group nanovox-demo \
  --settings \
    APP_ENV=prod \
    LLM_PROVIDER=openai \
    OPENAI_API_KEY='<paste>' \
    DATABASE_URL='sqlite+aiosqlite:////tmp/nanovox/nanovox_insights.db' \
    FRONTEND_DIST_PATH=/home/site/wwwroot/Code/Frontend/dist \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

**4. Startup command** — the `/tmp` copy, then the server, no Alembic. The
shipped database already carries the schema it was tested against, and
`main.py`'s lifespan does not call Alembic at startup.

```bash
az webapp config set --name nanovox-insights --resource-group nanovox-demo \
  --startup-file "mkdir -p /tmp/nanovox && cp /home/data/nanovox_insights.db /tmp/nanovox/ && cd /home/site/wwwroot/Code/Backend && python -m uvicorn frameworks_drivers.main:app --host 0.0.0.0 --port 8000"
```

**Unverified**: Microsoft Learn notes that with build automation the code can
be served from a temp path exposed as `APP_PATH` rather than
`/home/site/wwwroot`. Resolve the actual path on first deploy rather than
trusting the path above.

**5. Always On** — without it the app unloads when idle and the first visitor
waits 30+ seconds for a cold start.

```bash
az webapp config set --name nanovox-insights --resource-group nanovox-demo --always-on true
```

**6. Deploy, then put the database on `/home`** (section 7).

```bash
az webapp up --name nanovox-insights --resource-group nanovox-demo

az webapp ssh --name nanovox-insights --resource-group nanovox-demo \
  --command "mkdir -p /home/data"
# then upload data/db/nanovox_insights.db to /home/data via the Kudu console:
#   https://nanovox-insights.scm.azurewebsites.net/newui/fileManager

az webapp restart --name nanovox-insights --resource-group nanovox-demo
```

**7. Verify from outside the host** — section 9 is the real version of this
step; at minimum:

```bash
curl -s https://nanovox-insights.azurewebsites.net/api/v1/health
curl -s https://nanovox-insights.azurewebsites.net/api/v1/insights/exec | head -c 120
```

Built-in authentication (Entra ID) is configured on the app itself, with no
code change; by default any user in the tenant can sign in, and restricting to
named users is a separate Entra step (section 1).

**If `/tmp` turns out to be unwritable or the copy fails**, the fallback is one
setting: point `DATABASE_URL` at a Postgres Flexible Server and delete the `cp`
from the startup command — which is section 8.2 in miniature, without
switching the whole app off App Service.

### 8.2 Container Apps + Postgres path (the alternative, for durable writes)

```bash
az login
az group create --name nanovox-demo --location <region>

# Registry and image: built in Azure from the repo's Dockerfile.
az acr create --name <registry> --resource-group nanovox-demo --sku Basic
az acr build --registry <registry> --image nanovox-insights:v1 .

# Database. Burstable is for POC; see section 2.
az postgres flexible-server create \
  --name <server> --resource-group nanovox-demo --location <region> \
  --tier Burstable --sku-name Standard_B1ms \
  --admin-user <admin> --admin-password '<password>' \
  --database-name nanovox

# Logs and the Container Apps environment.
az monitor log-analytics workspace create --workspace-name nanovox-logs --resource-group nanovox-demo
az containerapp env create --name nanovox-env --resource-group nanovox-demo --location <region> \
  --logs-workspace-id <workspace-customer-id> --logs-workspace-key <workspace-key>

# The app. One replica, secrets by reference.
az containerapp create --name nanovox --resource-group nanovox-demo \
  --environment nanovox-env \
  --image <registry>.azurecr.io/nanovox-insights:v1 \
  --registry-server <registry>.azurecr.io \
  --target-port 8000 --ingress external \
  --min-replicas 1 --max-replicas 1 \
  --secrets db-url='<DATABASE_URL>' openai-key='<key>' \
  --env-vars APP_ENV=prod LLM_PROVIDER=openai \
             DATABASE_URL=secretref:db-url OPENAI_API_KEY=secretref:openai-key
```

Not shown, and needed: giving the app permission to pull from the registry
(managed identity with AcrPull, or registry credentials), opening the Postgres
firewall to the Container Apps environment (or using VNet integration, which is
the production answer), and the authentication decision from section 1. Check
the exact flags against `az containerapp create --help` before running.

---

## 9. Acceptance: what "deployed" means

A health check proves the app can connect. It does not prove it can write, and
it does not prove the data is there. All of these, from outside the host:

1. `curl https://<app>/api/v1/health` returns `"status":"up"` and
   `"application":"NanoVox Insights"`, with the database component up.
2. `/api/v1/insights/exec` returns 600 calls.
3. A client-side route such as `/risk` returns 200 `text/html` (the SPA fallback
   works).
4. **Move an action on "What should we do next?", then restart the app and
   check whether the change is still there.** On the recommended App Service +
   SQLite path, **it should not be** — that is the trade section 0 names, and
   seeing the change survive would mean `/tmp` was never actually in play. On
   the Container Apps + Postgres alternative, the change surviving is exactly
   what proves the deployment is durable rather than ephemeral.
5. Unauthenticated access is refused or restricted the way section 1 decided.
6. If a provider is configured: `GET /api/v1/providers` reports it reachable,
   and one AI panel renders generated text.
7. Logs appear in the App Service log stream (or Log Analytics, on Container
   Apps).

Every Azure-specific claim in this file stays unverified until 1 to 4 pass on a
real subscription.

---

## 10. Decisions needed before building

1. **Authentication or network restriction** (section 1). Blocks anything beyond
   an internal smoke test.
2. **Region and data residency** for member transcripts.
3. **Which LLM provider**: OpenAI direct, Anthropic, or Azure OpenAI. This is a
   data-handling decision as much as a cost one.
4. **Whether action-board edits need to survive a restart.** If not, section
   0's App Service + SQLite path is the whole answer. If they do, that is what
   pulls in Postgres and Container Apps (section 8.2), not a preference
   between the two services on their own merits.
5. **Postgres tier**, only if section 10.4 says durability is needed:
   Burstable for a POC, General Purpose if this becomes the system of record.
6. **Who loads the data into Postgres**, and with what, only on that same
   path: a one-off script, pgloader, or a CLI added to the repo. The SQLite
   path's data step (section 7) has no open question.
7. **Whether to add IaC and a pipeline deploy stage** now, or deploy by hand
   once and codify later.

---

## 11. Other targets

For an internal audience, the VM already running this app
(`10.30.1.34:8050`, deployed with `deploy.ps1`) needs no new work. For a quick
non-Azure public URL, any host that gives the container a real block device
works (Fly.io volume, Render persistent disk); the storage rule in section 2
is the same everywhere: SQLite needs a block device and one writer, and Postgres
is the way out the moment that is not true.

SQL Server (including Express) is not an option without code changes: the
settings validator rejects it, and the migrations have only been written for
SQLite and Postgres.

---

## 12. Teardown

Everything above lives in one resource group:

```bash
az group delete --name nanovox-demo --yes --no-wait
```

Check the subscription afterwards. A forgotten always-on resource is the usual
way a demo becomes a standing cost.

---

## Revision notes

Changes from the previous revision, so a reader of the old file knows what no
longer holds:

- **App Service + SQLite on `/tmp` is the recommendation again, Postgres is
  the alternative.** The previous revision (below) flipped this the other
  way; the app never needed Postgres to begin with — SQLite is the database
  that ships with the repo, Postgres was only added for a temporary
  deployment on Neon — and App Service's `/tmp` gives SQLite a real block
  device for no extra resource, at the cost of losing writes on restart
  (section 0, section 2). Container Apps + Postgres stays in the document as
  the path to take if that cost is not acceptable, not as a default.
- **Container Apps with an Azure Disk mount was wrong.** Container Apps does not
  support Azure Disk. Removed, along with the cost table built on it.
- **Python 3.10 is replaced by 3.14** throughout, matching the image, pipeline
  and scripts. 3.10 leaves support on 2026-10-31.
- **"SQLite on App Service `/tmp`" is no longer the headline.** It remains
  technically possible but loses every write on restart and was never tested on
  App Service. Postgres is the recommendation.
- **The authentication gap is now stated up front**, including the unauthenticated
  run and ingest endpoints.
- **Removed unverified dollar figures.** Use the Azure pricing calculator.
- **Added the existing-scripts inventory and the missing-data-load gap.**
