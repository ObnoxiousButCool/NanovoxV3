# Deploying NanoVox Insights for a two-week run

Written against the repo as it stands. Every claim about the app is checked
against the code, and the file points at the line that settles it. The
container section is checked against an image that was built and run, not
against how a Dockerfile usually behaves.

> **Decision: Azure.** The comparison sections are kept for the reasoning, but
> the answer is **section 0**. Everything else is background.

---

## 0. The decision — App Service B1 Linux, SQLite on `/tmp`

**~$7 for a fortnight, one resource, no registry, no database server, HTTPS
included.** It is the cheapest option on this page that actually works, and it
works because of one trick.

### The trick

Section 2A found SQLite dies on a protocol-backed mount, and App Service's
persistent `/home` is exactly that — an SMB share. The usual conclusion is "add
Postgres" (+$13/month) or "move to Container Apps" (+$5/month registry).

Neither is necessary. **`/tmp` on App Service is container-local disk, not the
share.** So:

- the pristine 4 MB database sits on `/home`, where it persists — a plain file,
  never opened by SQLite there, so SMB's locking is irrelevant;
- the startup command copies it to `/tmp`, a real block device;
- SQLite runs there and behaves correctly.

### What you give up

Writes land on `/tmp` and are lost when the app restarts. In practice that means
**action-board changes reset on restart**, because the corpus comes back from
the pristine copy each time.

For a two-week demo this is a reasonable trade and arguably a feature — every
restart is a clean demo. If the client must keep their action edits across a
restart, add Postgres Flexible Server B1ms and skip the copy entirely; that is
the only thing worth spending the extra on.

### Resources

| Resource | SKU | Two weeks |
|---|---|---|
| Resource group | — | $0 |
| App Service plan, **Linux** | **B1** | **~$6.50** |
| App Service (Web App) | Python 3.10 | included |
| | | **~$7** |

No Container Registry. No Azure Disk. No Postgres. No Static Web App — the API
process serves the frontend (section 1), so there is nothing to host separately.

### Steps

**1. Build the frontend locally.** Oryx will not run `npm run build` for a
Python app, so `dist` must be in what you push.

```bash
cd Code/Frontend && npm ci && npm run build
```

**2. Create the resources.**

```bash
az group create --name nanovox-demo --location eastus

az appservice plan create --name nanovox-plan --resource-group nanovox-demo \
  --sku B1 --is-linux

az webapp create --name nanovox-insights --resource-group nanovox-demo \
  --plan nanovox-plan --runtime "PYTHON:3.10"
```

**3. Configure.** The root `requirements.txt` in this repo is a pointer to
`Code/Backend/requirements.txt`, which is what lets Oryx find the dependencies.

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

Four slashes in the SQLite URL: `sqlite+aiosqlite:///` plus the absolute
`/tmp/...`. `FRONTEND_DIST_PATH` is set explicitly because `paths.py` derives the
default from its own `__file__`, and App Service's layout is not the checkout's.

**4. Startup command** — the copy, then the server.

```bash
az webapp config set --name nanovox-insights --resource-group nanovox-demo \
  --startup-file "mkdir -p /tmp/nanovox && cp /home/data/nanovox_insights.db /tmp/nanovox/ && cd /home/site/wwwroot/Code/Backend && python -m uvicorn frameworks_drivers.main:app --host 0.0.0.0 --port 8000"
```

No `alembic upgrade head`: the shipped database already carries the schema, and
nothing at startup needs alembic (`main.py`'s lifespan does not call it).

**5. Always On.** Without it the app unloads when idle and the first visitor
waits 30+ seconds.

```bash
az webapp config set --name nanovox-insights --resource-group nanovox-demo --always-on true
```

**6. Deploy, then put the database on `/home`.**

```bash
az webapp up --name nanovox-insights --resource-group nanovox-demo

# the 4 MB corpus, to the persistent share
az webapp ssh --name nanovox-insights --resource-group nanovox-demo \
  --command "mkdir -p /home/data"
# then upload data/db/nanovox_insights.db to /home/data via the Kudu console:
#   https://nanovox-insights.scm.azurewebsites.net/newui/fileManager

az webapp restart --name nanovox-insights --resource-group nanovox-demo
```

**7. Verify from outside the host.**

```bash
curl -s https://nanovox-insights.azurewebsites.net/api/v1/health
curl -s https://nanovox-insights.azurewebsites.net/api/v1/insights/exec | head -c 120
curl -s -o /dev/null -w '%{http_code}\n' https://nanovox-insights.azurewebsites.net/risk
```

Expect `"application":"NanoVox Insights"`, `"calls":600` in the second, and
`200` from the third. **Then click an action on "What should we do next?"** — a
health check proves the connection, not that the database is writable, and
section 2A's failure mode is invisible until something writes.

### Honest caveat

I verified the SQLite-on-a-protocol-mount failure by reproducing it, and the
container path end to end. **I have not been able to test App Service itself
from here** — no subscription access. The `/tmp` reasoning is sound and standard,
but treat step 7's write test as the real acceptance gate, not a formality.

If `/tmp` turns out to be unwritable or the copy fails, the fallback is one
setting: point `DATABASE_URL` at a Postgres Flexible Server B1ms and delete the
`cp` from the startup command. Everything else stays.

---

## 1. What you are actually deploying

This matters more than any Azure choice, because most guides assume something
this app is not.

**It is one process on one port.** `frameworks_drivers/spa.py` mounts the built
frontend inside the API process:

> *"One process and one origin, which removes a surprising amount: no CORS, no
> separate web server, no SPA fallback rule to configure, and no rebuilding the
> bundle when the API's address changes."*

So the whole thing runs as:

```
python -m uvicorn frameworks_drivers.main:app --host 0.0.0.0 --port 8050
```

**You need one service, not two.** No Static Web App, no separate API host, no
Front Door, no CORS configuration, no reverse proxy, no nginx sidecar. Splitting
the frontend out would double the bill, reintroduce the CORS the architecture
deliberately removed, and tie the bundle to a specific API address — the build
is host-independent today precisely because it does not know one
(`.env.production` sets `VITE_API_BASE_URL=/api/v1`, a relative path).

If a platform's "deploy your frontend" step asks where your API lives, you are
on the wrong path for this app. There is nothing to answer.

| | |
|---|---|
| Runtime | Python **3.10** (`.venv` is 3.10.11; ruff targets `py310`) |
| Web server | uvicorn, ASGI |
| Database | SQLite file, **4 MB** (`data/db/nanovox_insights.db`) |
| Frontend | Vite build → `Code/Frontend/dist`, served by the API process |
| Build output | ~440 KB of JS + CSS |
| Secrets | `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`) |
| Inbound | one HTTP port |

---

## 2. Will SQL Server Express work?

**No — not without a code change.** This is settled in the config, not by
convention.

`infrastructure/config/settings.py` rejects anything else before the app starts:

```python
_ASYNC_DATABASE_PREFIXES = ("sqlite+aiosqlite:", "postgresql+asyncpg:")
```

```python
@field_validator("database_url")
def _database_must_use_an_async_driver(cls, value: str) -> str:
    if not value.startswith(_ASYNC_DATABASE_PREFIXES):
        raise ValueError("DATABASE_URL must use an async driver — ...")
```

Pointing `DATABASE_URL` at SQL Express fails at startup with a clear error.

### What it would take to make it work

1. Add `aioodbc` (and the system ODBC Driver 18 for SQL Server) to the image.
2. Add `mssql+aioodbc:` to the allowed prefixes.
3. Re-test the Alembic migrations — there are **12+ migration files** written and
   exercised against SQLite and Postgres only. SQL Server differs on identity
   columns, `DateTime` precision and index naming; some will need editing.
4. Re-run the full test suite against SQL Server.

That is a few days of work and a permanent new maintenance surface, for an app
that holds **4 MB** and is read-only in normal use.

### What to do instead

**For two weeks, keep SQLite.** The database is a single 4 MB file, every screen
is a read, and there is no concurrent writer. It is the right tool here, and it
is what decision D9 chose.

If you want a managed database anyway, use **Azure Database for PostgreSQL —
Flexible Server (Burstable B1ms)**. That path is already supported: `asyncpg` is
in `requirements.txt` with the comment *"a deployment points DATABASE_URL at this
instead of aiosqlite, so storage survives a redeploy."* It needs no code change —
only a different `DATABASE_URL` and `alembic upgrade head`.

> For a two-week demo, Postgres adds roughly $13–15/month and a networking step
> for no behaviour you will notice. Recommended only if the app must survive
> redeploys without you copying a file.

---

## 2A. What building and running the image actually showed

The repo now has a `Dockerfile` and a `.dockerignore`. The image builds (381 MB)
and serves the real corpus — health `up`, `/exec` returning 600 calls, SPA deep
links answering 200. Getting there turned up two things that change the advice
above, and neither is visible from reading code.

### Finding 1 — SQLite dies on a network-backed mount

First run, database on a Docker Desktop Windows bind mount:

```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) disk I/O error
```

Not a permissions problem and not a path problem. SQLite needs byte-range locks
with POSIX semantics, and a mount that proxies the filesystem over a protocol —
gRPC-FUSE here — cannot provide them. The same class of failure applies to **any
SMB or NFS-backed share**.

**This matters for Azure App Service.** `/home` on App Service for Linux is an
**Azure Files (SMB) share**. Section 4 told you to put the SQLite file there.
That is the configuration most likely to reproduce this error, and I have not
been able to test App Service itself from here. Treat "SQLite on `/home`" as
unverified and reasonably likely to fail.

On a **real block device** — a Docker named volume, a Fly volume, a Container
Apps Azure Disk — SQLite behaves correctly. That is what the working run used.

### Finding 2 — the volume's owner has to be the container's user

Seeding a named volume as root gave:

```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) attempt to write a readonly database
```

The image runs as uid **10001**, and a pre-populated volume keeps the ownership
it was written with — the Dockerfile's `chown` happens at build time and a mount
covers it. So any copy of the database into the volume must end with:

```bash
chown -R 10001:10001 /app/data
```

Docker only applies the image's ownership when it initialises an **empty**
volume, which is why "deploy first, copy second" needs this and a first-run
container does not.

### Finding 3 — the database is not read-only at runtime

Worth knowing before anyone suggests baking the 4 MB file into the image and
skipping volumes entirely. `action_board.py` exposes **`POST` and `PATCH`**:
moving an action along a lane writes to the database. Bake it in read-only and
the "What should we do next?" screen fails the moment someone clicks it.

A demo that nobody clicks would survive. Yours will be clicked.

### Running it locally

The image and a seeded volume are on this machine already:

```bash
docker run -d --name nanovox -p 8099:8000 \
  -e LLM_PROVIDER=ollama \
  -v nanovox-data:/app/data \
  nanovox-insights:test
```

Then `http://localhost:8099`. `LLM_PROVIDER=ollama` keeps it off a paid API —
the AI panels show their explicit "unavailable" state, which is a designed
state, not a fault.

---

## 3. The step everyone misses: there will be no data

`scripts/deploy.sh` runs migrations and nothing else:

```bash
(cd "$BACKEND" && "$PYTHON" -m alembic upgrade head)
```

Migrations create **empty tables**. `data/` is gitignored (`.gitignore:6`), so
the database does not travel with the repo. Deploy the repo alone and every
screen renders its withheld state: 0 calls, no accounts, no insights. The app
will look broken and will in fact be behaving correctly.

**Do not rebuild the corpus on the server.** Rebuilding means
`frameworks_drivers.cli.run_extraction`, which runs every call through an LLM
provider. That is hours of runtime and real API spend.

**Copy the database file instead.** It is 4 MB:

```bash
# from your machine, once the app is deployed and stopped
scp data/db/nanovox_insights.db <target>:/home/data/db/nanovox_insights.db
```

On Azure App Service the destination is under `/home`, which is the persistent
share. Anything outside `/home` is wiped on restart.

Order matters: **deploy → stop → copy the database → start.** Copying into a
running SQLite database risks a torn read.

---

## 4. Azure, option A — App Service for Linux

> **Downgraded from "recommended" after section 2A.** The steps below are
> correct, but the storage line is the weak point: `/home` is an SMB share and
> SQLite failed on exactly that class of mount when tested. Use this path with
> **Postgres** rather than SQLite, or use Container Apps (option B), which gets
> a real disk.

The least machinery for a two-week run, and the only option here that needs no
Dockerfile — Azure builds from source with Oryx.

### Required Azure resources

| Resource | SKU | Why |
|---|---|---|
| Resource group | — | one container for everything, so teardown is one delete |
| App Service plan | **Linux, B1** | Always On, 1 core, 1.75 GB; persistent `/home` |
| App Service (Web App) | Python 3.10 | the app itself |
| *(optional)* Log Analytics | pay-as-you-go | only if you want retained logs |

You do **not** need: Static Web Apps, API Management, Front Door, Application
Gateway, a storage account, a container registry, or a second app.

> **Do not use the Free (F1) tier.** No Always On, so the app unloads when idle
> and the first request after a pause takes 30+ seconds while uvicorn restarts
> and reopens the database. For a demo people will click into cold, that reads
> as "the app is broken."

### Steps

**1. Build the frontend locally and commit the output for this deployment.**

Oryx will not run `npm run build` for a Python app, so `dist` must exist in what
you push.

```bash
cd Code/Frontend
npm ci
npm run build          # produces Code/Frontend/dist
```

`.env.production` already sets `VITE_API_BASE_URL=/api/v1`, so the bundle is
host-independent — it never needs rebuilding because the address changed.

**2. Create the resources.**

```bash
az group create --name nanovox-demo --location eastus

az appservice plan create \
  --name nanovox-plan --resource-group nanovox-demo \
  --sku B1 --is-linux

az webapp create \
  --name nanovox-insights --resource-group nanovox-demo \
  --plan nanovox-plan --runtime "PYTHON:3.10"
```

**3. Set configuration.** These are App Settings, never a `.env` file in the
repo.

```bash
az webapp config appsettings set \
  --name nanovox-insights --resource-group nanovox-demo \
  --settings \
    APP_ENV=prod \
    LLM_PROVIDER=openai \
    OPENAI_API_KEY='<paste>' \
    DATABASE_URL='sqlite+aiosqlite:////home/data/db/nanovox_insights.db' \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true \
    PYTHONPATH=/home/site/wwwroot/Code/Backend
```

Note the **four** slashes in the SQLite URL: `sqlite+aiosqlite:///` plus the
absolute path `/home/...`.

**4. Set the startup command.**

```bash
az webapp config set \
  --name nanovox-insights --resource-group nanovox-demo \
  --startup-file "cd /home/site/wwwroot/Code/Backend && python -m alembic upgrade head && python -m uvicorn frameworks_drivers.main:app --host 0.0.0.0 --port 8000"
```

App Service gives the container its port in `$PORT` and expects 8000 by default
for Python. Bind `0.0.0.0`, never `127.0.0.1`.

**5. Turn Always On on.**

```bash
az webapp config set --name nanovox-insights \
  --resource-group nanovox-demo --always-on true
```

**6. Deploy.**

```bash
az webapp up --name nanovox-insights --resource-group nanovox-demo
```

**7. Copy the database in** (section 3), then restart:

```bash
az webapp restart --name nanovox-insights --resource-group nanovox-demo
```

**8. Verify from outside the host** — the half a server cannot check about
itself:

```bash
curl -s https://nanovox-insights.azurewebsites.net/api/v1/health
curl -s -o /dev/null -w '%{http_code}\n' https://nanovox-insights.azurewebsites.net/api/v1/insights/exec
curl -s -o /dev/null -w '%{http_code}\n' https://nanovox-insights.azurewebsites.net/risk
```

Expect `{"status":"up", ... "application":"NanoVox Insights"}`, then `200` and a
payload of roughly 70 KB from `/exec`, and `200 text/html` from `/risk` (the SPA
deep-link fallback).

> If `application` comes back as anything other than **"NanoVox Insights"**, or
> the timestamp key is `checked_at` rather than `checkedAt`, you are talking to a
> different build. That exact confusion has already happened once on the VM.

### Known friction

- **SQLite on `/home` is an Azure Files (SMB) share, not local disk.** This is
  the configuration section 2A's `disk I/O error` came from on an equivalent
  mount. If you take this path, set `DATABASE_URL` to Postgres instead and skip
  the file copy entirely. If you try SQLite anyway, test it on day one with a
  real click-through, not just a health check — health reports the connection,
  not a write.
- **Oryx needs `requirements.txt` at a path it finds.** The backend's is at
  `Code/Backend/requirements.txt`, not the repo root. The repo now has a root
  `requirements.txt` that is a one-line pointer to it, so this is handled —
  that file exists only for build systems that look at the root and has no
  other purpose.
- **Writes still need somewhere durable.** Finding 3: the action board writes.
  With Postgres this is a non-issue; with SQLite on an ephemeral container disk
  the status changes vanish on restart.

---

## 5. Azure, option B — Container Apps (recommended on Azure)

Now the better Azure option, because the Dockerfile exists and is proven, and
because this is the Azure service that can give SQLite a real disk.

| Resource | Why |
|---|---|
| Container Apps environment | the runtime |
| Container App | the app |
| Azure Container Registry (Basic) | somewhere to push the image, ~$5/month |
| **Azure Disk** storage mount | SQLite needs a block device — **not** Azure Files |

Use **Azure Disk**, not the Azure Files option the docs reach for first. Files is
SMB, which is the mount type that produced section 2A's `disk I/O error`. Azure
Disk is a block device and behaves like the named volume that worked.

```bash
az acr build --registry <registry> --image nanovox-insights:v1 .
az containerapp create \
  --name nanovox --resource-group nanovox-demo \
  --environment nanovox-env \
  --image <registry>.azurecr.io/nanovox-insights:v1 \
  --target-port 8000 --ingress external \
  --min-replicas 1 --max-replicas 1 \
  --secrets openai-key='<paste>' \
  --env-vars APP_ENV=prod LLM_PROVIDER=openai OPENAI_API_KEY=secretref:openai-key
```

**`--max-replicas 1` is not optional.** An Azure Disk mounts read-write to one
replica, and two processes writing one SQLite file corrupts it. If you need more
than one replica, you need Postgres — that is the real fork, not a tuning knob.

**On scale-to-zero:** genuinely near-free while idle, but a cold start is several
seconds and the first visitor gets it. For a demo people click into, pin
`--min-replicas 1` and accept ~$8–12/month. Use `0` only if the app will sit
untouched for days at a time.

---

## 6. Azure, option C — a VM

What `scripts/deploy.ps1` and `scripts/deploy.sh` already automate, and what you
are running on `10.30.1.34` today.

A **B2s** Linux VM runs this comfortably. The scripts handle venv, migrations,
frontend build, firewall and service registration end to end.

Pick this if you want the deployment to match what you already operate. The
downside is that you own patching, TLS and the firewall — on App Service, HTTPS
and a certificate come free on the `azurewebsites.net` hostname.

---

## 7. Cost, for a two-week run

Indicative only — check the Azure pricing calculator for your region and
agreement. Figures are USD/month; halve them for a fortnight.

| Option | Monthly | Two weeks | Notes |
|---|---|---|---|
| Container Apps, 1 replica + Disk | ~$10–14 | **~$6** | best on Azure; real disk for SQLite |
| Container Apps, scale-to-zero | ~$0–8 | **~$0–4** | cold starts; idle demos only |
| App Service **B1** + Postgres B1ms | ~$26 | **~$13** | no Dockerfile, but two resources |
| App Service **B1** + SQLite on `/home` | ~$13 | ~$7 | **unverified, likely to fail** — section 2A |
| VM **B2s** + disk | ~$35 | **~$18** | you own patching and TLS |
| Azure Container Registry Basic | ~$5 | ~$2.50 | needed by both Container Apps rows |

**Do not forget the LLM spend.** The screens call a provider for generated
insights. The budget line is OpenAI, not Azure. Two mitigations:

- The insight cache is **per process and dies with it** (`application/ports/insight_cache.py`),
  so every restart re-pays for the same sentences. Keep restarts rare.
- Set `LLM_PROVIDER=ollama` if the demo does not need generated prose. The AI
  panels then show their explicit "unavailable" state, which is a designed state
  (decision U2/D14), not an error.

---

## 8. Non-Azure options, ranked for a two-week run

If "it must be Azure" is not a hard constraint, you can do better on both effort
and cost.

### 1. The VM you already have — **$0, today**

`10.30.1.34:8050` is already serving this app, and `deploy.ps1` works. If the
audience is on your network, you are done. This is the honest first answer: the
cheapest deployment is the one already running.

The only reason to move is reach — an external audience, or a link people open
from anywhere.

### 2. Fly.io — best fit if you want a public URL

Closest match to this app's shape of anything on the market, and section 2A
sharpened why:

- A Fly volume is a **real block device**, not a protocol share. This is the
  difference between SQLite working and `disk I/O error`.
- One process, one port — exactly what `spa.py` produces.
- Takes the Dockerfile in this repo as-is.
- HTTPS and a global hostname out of the box.

Roughly **$2–5/month** at this size:

```bash
fly launch --no-deploy          # detects the Dockerfile
fly volumes create nanovox_data --size 1 --region <region>
fly secrets set OPENAI_API_KEY='<paste>'
fly deploy
```

Mount the volume at `/app/data` in `fly.toml`, and set `--max-machines-running 1`
for the same single-writer reason as Container Apps.

### 3. Render — least to learn

A persistent disk on the Starter plan, builds the Dockerfile for you, HTTPS
included. About **$7/month**. Render disks are block devices, so SQLite is fine.

Its free tier sleeps after inactivity with a slow cold start — same objection as
App Service F1, so use Starter.

### 4. Hetzner / DigitalOcean droplet — cheapest real server

**$4–6/month** for a box that `scripts/deploy.sh` will configure unchanged. You
get a plain Linux VM, so TLS is yours to arrange (Caddy makes it two lines).

Best value if you are comfortable on a server and want zero platform lock.

### What I would actually do

- **Internal audience only:** keep the existing VM. Deploy nothing new, spend
  nothing, and the scripts already work.
- **External audience, two weeks, lowest friction:** **Fly.io**. The Dockerfile
  in this repo deploys there unchanged, the volume is a real disk, and it is the
  cheapest thing on this page that is not already running.
- **It must be Azure:** **Container Apps** with an Azure Disk and one replica,
  not App Service. App Service is simpler to set up but its persistent storage
  is the one shape SQLite will not tolerate, so you would be adding Postgres to
  work around it — two resources instead of one, for more money.

Whichever you pick, the storage rule is the same and it is the only thing on
this page I would call a hard requirement:

> **SQLite needs a block device and exactly one writer.** Azure Disk, Fly
> volume, Render disk or a VM's own disk — yes. Azure Files, any SMB or NFS
> share, or more than one replica — no. The moment either is untrue, move to
> Postgres rather than hoping.

---

## 9. Before you start — and how to stop paying

**Prerequisites**

- Python 3.10 and Node installed locally for the build.
- The 4 MB database file to hand (section 3).
- An API key for whichever provider you point `LLM_PROVIDER` at.
- `az login` against the right subscription.

**Teardown.** Everything above lives in one resource group, so a fortnight ends
with one command:

```bash
az group delete --name nanovox-demo --yes --no-wait
```

Check the subscription afterwards. A forgotten B1 plan is the usual way a
two-week demo turns into a twelve-month line item.

---

## 10. Gaps in the repo

1. ~~**No Dockerfile.**~~ **Added and verified** — builds to 381 MB, runs, serves
   the real corpus. Multi-stage: Node 20 builds the frontend, `python:3.10-slim`
   runs it, and the image keeps the checkout's directory shape because
   `paths.py` derives every location from `__file__` and would otherwise find no
   `dist`.
2. ~~**No root `requirements.txt`.**~~ **Added** as a one-line pointer to
   `Code/Backend/requirements.txt`, for builders that only look at the root. The
   Dockerfile does not use it.
3. **The deploy scripts never load data.** Still true — section 3. A fresh target
   comes up empty and looks broken while behaving correctly. Worth fixing in
   `deploy.sh` if this gets deployed more than once.
4. **No CI/CD to any host.** Deployment is manual in every option above. For two
   weeks that is the right amount of machinery.
5. **`scripts/deploy.*` do not know about the container path.** They build and
   run a venv on a host directly, which is still correct for the VM option and
   irrelevant to the other three.
