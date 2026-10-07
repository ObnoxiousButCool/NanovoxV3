# Deploying NanoVox Insights through the Azure Portal

Click-by-click, for the plan settled in `Deployment-Options.md` §0: one Linux
App Service on **B1**, SQLite copied to `/tmp` at startup, and Entra ID sign-in
in front of it.

**Cost: $5.71 for a fortnight.** B1 Linux is $0.017/hour in East US on the live
retail price API. Nothing else here bills — no
registry, no database server, no storage account.

> **Sign in as** `Ranjit.Savant@technossus.com`, subscription **Dev-Testing**
> (`124ad7d7-2c62-47dc-b76d-e1eb2545b0ee`), tenant **technossus.com**.
>
> The portal's subscription picker defaults to whichever you used last, and
> this tenant has three — `Corporate`, `Dev-Testing` and a personal one.
> Creating the app in the wrong one is the easiest mistake here.

### Checked before you start

| | |
|---|---|
| `RG-NanoVox-POC` | exists, **East US**, currently **empty** |
| Your role on it | **Owner** |
| `Microsoft.Web` provider | **Registered** |
| Policy assignments | none that block this |
| App registrations by non-admins | **allowed** — step 7 needs no admin |
| B1 Linux, East US | **$0.017/hour** → **$5.71** per fortnight |

---

## Before you open the portal

**1. Build the frontend.** Oryx will not run `npm run build` for a Python app,
so `dist` has to exist in what you deploy.

```powershell
cd C:\Technossus\Code\NanoVox-V3\Code\Frontend
npm ci
npm run build
```

Confirm `Code\Frontend\dist\index.html` exists before going further. Without it
the API starts, serves JSON, and answers every page with 404 — which looks like
a routing bug and is not one.

**2. Have the database to hand**: `data\db\nanovox_insights.db`, about 4 MB.
This is the corpus. Migrations alone would give you empty tables and every
screen in its withheld state.

---

## Step 1 — Resource group

**Nothing to do — `RG-NanoVox-POC` already exists**, in the **Dev-Testing**
subscription, region **East US**, and is empty. Everything below goes in it.

Check the portal is on **Dev-Testing** before step 2, not `Corporate`.

> The region matters only for latency and must match between the group and the
> plan; East US and West US 2 bill identically for B1 Linux.

---

## Step 2 — The web app

1. Search **App Services** → **+ Create** → **Web App**

**Basics tab**

| Field | Value |
|---|---|
| Subscription | **Dev-Testing** |
| Resource Group | `RG-NanoVox-POC` |
| Name | `nanovox-insights` *(becomes `nanovox-insights.azurewebsites.net`, must be globally unique — add a suffix if taken)* |
| Publish | **Code** |
| Runtime stack | **Python 3.14** |
| Operating System | **Linux** |
| Region | **East US** *(matching the resource group)* |

**Pricing plan** — click **Create new**, name it `nanovox-plan`, then
**Change size** → **Dev/Test** → **B1** → **Apply**.

> **Not F1 (Free).** F1 has no Always On, so the app unloads when idle and the
> first visitor after a pause waits 30+ seconds while uvicorn restarts. For a
> demo people click into cold, that reads as broken.

**Deployment / Networking / Monitoring tabs** — leave the defaults. Turn
Application Insights **off** unless you want the telemetry; it bills
separately.

**Review + create** → **Create**. Wait for deployment to finish, then **Go to
resource**.

---

## Step 3 — Application settings

**Settings → Environment variables → App settings tab**. **+ Add** each row,
then **Apply** at the bottom.

| Name | Value |
|---|---|
| `APP_ENV` | `prod` |
| `DATABASE_URL` | `sqlite+aiosqlite:////tmp/nanovox/nanovox_insights.db` |
| `FRONTEND_DIST_PATH` | `/home/site/wwwroot/Code/Frontend/dist` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |
| `LLM_PROVIDER` | `openai` — or `ollama` to run with no API key and no spend |
| `OPENAI_API_KEY` | your key *(omit entirely if you chose `ollama`)* |
| `OPENAI_MODEL` | *optional* — defaults to `gpt-4o-mini` |

**Two of these are easy to get wrong.**

`DATABASE_URL` has **four** slashes: `sqlite+aiosqlite:///` plus the absolute
path `/tmp/...`. Three slashes makes it relative and it will not find the file.

`FRONTEND_DIST_PATH` must be set explicitly. `paths.py` derives its default
from its own `__file__` position, and App Service's layout is not the
checkout's — without this the frontend is not found.

> **Why `/tmp` and not `/home`.** `/home` is an Azure Files (SMB) share.
> SQLite needs POSIX byte-range locks, which a protocol-backed share cannot
> provide — it fails with `disk I/O error`. I reproduced exactly that on an
> equivalent mount. `/tmp` is container-local disk, so SQLite behaves. The
> trade-off is in the Known limits section below.

---

## Step 4 — Startup command and Always On

**Settings → Configuration**, which opens on the **General settings** tab —
that tab does *not* have the Startup Command field. Click the **Stack
settings** tab instead; the field sits just below the Python version
selector.

**Startup Command** — paste this as one line:

```
mkdir -p /tmp/nanovox && cp /home/data/nanovox_insights.db /tmp/nanovox/ && cd /home/site/wwwroot/Code/Backend && python -m uvicorn frameworks_drivers.main:app --host 0.0.0.0 --port 8000
```

**Save** on the Stack settings tab, then switch back to **General settings**
for the rest:

- **Always on** → **On**
- **HTTP version** → 2.0 *(optional)*
- **HTTPS Only** → **On**

It copies the corpus from the persistent share onto local disk, then serves.
No `alembic upgrade head` — the shipped database already carries the schema,
and nothing at startup needs Alembic.

**Save**.

---

## Step 5 — Deploy the code

**Use zip-deploy. Do not try Deployment Center → Continuous Deployment (CI/CD)
with Azure Repos as the source — it fails for this project, confirmed, and
costs you a round trip to discover.** Setting it up asks App Service to create
a service hook on the Azure DevOps project, which needs **Project
Administrator** rights there — a permission on the DevOps project itself, not
on the Azure resource group, and separate from the Owner role this deployment
otherwise only needs. The save fails with:

```
Vso AddWebHook: Failed because you are not an administrator on the VSTS
project. Access Denied: ... needs the following permission(s) on the resource
PublisherSecurity/... to perform this action: Edit Subscription
```

If you land on that screen, click **Discard** and use the path below instead
— it needs no Azure DevOps permission at all, only the Owner role already
confirmed in "Checked before you start."

**Zip-deploy, from the repo root in PowerShell:**

```powershell
cd C:\Technossus\Code\NanoVox-V3
Compress-Archive -Path * -DestinationPath ..\nanovox.zip -Force
az login
az webapp deploy --resource-group RG-NanoVox-POC --name nanovox-insights --src-path ..\nanovox.zip --type zip
```

This is also what settles the frontend `dist` problem: `Code/Frontend/dist` is
git-ignored, so a repository-based deployment (CI/CD, had it worked) would not
have carried it at all. The zip includes your locally built `dist` because
`Compress-Archive` just zips what's on disk, built artifacts included — no
separate upload step needed. If you ever do need to upload it separately
(for instance, redeploying only the frontend), the Kudu file manager in
step 6 reaches `/home/site/wwwroot/Code/Frontend/dist` directly.

`az webapp deploy --type zip` builds from the repo-root `requirements.txt`,
which is a one-line pointer to `Code/Backend/requirements.txt` — that file
exists only so builders that look at the root can find the dependencies.

Watch **Deployment Center → Logs** until it reports success.

---

## Step 6 — Upload the database

1. **Development Tools → Advanced Tools → Go** (opens Kudu in a new tab)
2. Top menu → **Site wwwroot** / the file manager at
   `https://nanovox-insights.scm.azurewebsites.net/newui/fileManager`
3. Navigate to `/home`, create a folder **`data`**
4. Drag `nanovox_insights.db` into `/home/data/`

`/home` persists across restarts; anywhere else does not. This file is the
master copy — the startup command copies it to `/tmp` on every start.

Then **Overview → Restart**.

---

## Step 6a — OpenAI access

Uses **OpenAI's own platform**: a key from `platform.openai.com`, billed by
OpenAI, calling `api.openai.com`. Two app settings and nothing else — no Azure
resource, nothing to provision, nothing on the Azure invoice.

### What actually needs it

**One surface.** `GET /api/v1/insights/generated` is the only endpoint that
calls a model provider — it is what fills the "What this period means" panel.
Every other screen (risk, accounts, agents, demand, quality, actions,
hierarchy, rules, the CSV export) is computed from the corpus and needs no
provider at all.

So the app is fully usable with no key. Those panels then show an explicit
**"unavailable"** state, which is a designed state (decision U2/D14 — the
application never substitutes templated copy for generated text), not an error.

### Outbound access

App Service allows outbound internet by default, so `api.openai.com` is
reachable with no configuration — **as long as you do not add VNet
integration**. If your subscription policy forces VNet integration or a
firewall on outbound traffic, egress to `api.openai.com:443` has to be allowed
explicitly, or every insight request fails with a connection error.

### Verify it from the app, not by guessing

`GET /api/v1/providers` reports each provider as configured and reachable, and
is the fastest way to tell a missing key from a blocked network. Locally it
answers:

```
  ollama       configured=True   reachable=True   model=qwen2.5:7b-instruct
  openai       configured=True   reachable=True   model=gpt-4o-mini
  anthropic    configured=False  reachable=False  model=claude-opus-5
```

Open `https://<app>.azurewebsites.net/api/v1/providers` **in the browser** —
after step 7, `curl` gets a 302 to the sign-in page rather than JSON.

- `configured=False` → the app setting is missing or misspelled.
- `configured=True, reachable=False` → the key is there and the call failed:
  wrong key, no quota, or blocked egress. The `reason` field says which.

### Cost, and the one thing that drives it

Insights are generated per request and the cache **is per process and dies with
it** (`application/ports/insight_cache.py`). Every restart re-pays for the same
sentences, so restarts — not visitors — are the cost driver. Keep them rare,
and do not leave the app restarting in a loop while debugging with a live key.

`gpt-4o-mini` is the default and is inexpensive. The Azure bill for this
deployment is $5.71; OpenAI is billed separately by OpenAI, not by Azure, and
does not appear on your Azure invoice.

### Keeping the key out of plain text

An App Setting is encrypted at rest but visible to anyone with portal access to
the app. For a two-week POC that is usually accepted. If it is not, use a Key
Vault reference instead of the raw value:

```
@Microsoft.KeyVault(SecretUri=https://<vault>.vault.azure.net/secrets/openai-api-key/)
```

That needs a Key Vault, a system-assigned managed identity on the web app, and
a **Key Vault Secrets User** role assignment for that identity. It is a real
addition, not a checkbox — worth it only if policy requires it.

### Leave `OPENAI_BASE_URL` unset

This deployment uses **OpenAI's own platform** (`api.openai.com`) with a
platform API key from `platform.openai.com`. That is the supported path and
needs no base URL: `registry.py` reads `settings.openai_base_url or None`, so
blank becomes `None` and the SDK uses its own default. Setting it to an empty
string is harmless; setting it to anything else points the app somewhere that
is not OpenAI.

> Not Azure OpenAI. There is no adapter for it — decision D1 chose OpenAI,
> Anthropic and Ollama, noting "no Azure Foundry adapter this time". Nothing
> in this guide depends on one.

A missing key fails loudly rather than silently: `_require` raises naming
`OPENAI_API_KEY` and the provider it was needed for, so a blank setting shows
up as a clear error, not as empty panels.

---

## Step 7 — Entra ID sign-in (the reason this is safe to publish)

The app has **no authentication of its own** — no bearer token, no API key.
Published without this step, anyone with the URL sees 95 named employer
organisations, their risk flags and 600 call transcripts with verbatim quotes.
This step puts your tenant's sign-in in front of all of it, with no code change
and no cost.

1. **Settings → Authentication** → **Add identity provider**
2. Identity provider: **Microsoft**
3. Tenant type: **Workforce**
4. App registration type: **Create new app registration**
5. Name: `nanovox-insights` *(leave the generated value)*
6. Supported account types: **Current tenant - Single tenant**
7. **Restrict access**: **Require authentication**
8. **Unauthenticated requests**: **HTTP 302 Found redirect - recommended for
   websites**
9. Token store: **leave enabled**
10. **Add**

Anyone at `technossus.com` can now sign in; nobody else reaches the app.

> This tenant allows standard users to register applications
> (`defaultUserCanCreateApps: true`), so step 4 is available to you and needs
> no administrator. If it is ever greyed out, that setting has changed — ask
> whoever administers Entra ID to create a registration and select it under
> **Pick an existing app registration**.
>
> Note the registration lands in the **technossus.com** directory, not in the
> Dev-Testing subscription. It survives deleting the resources, which is why
> teardown mentions it separately.

---

## Step 8 — Verify

Open `https://nanovox-insights.azurewebsites.net` in a browser. You should be
redirected to a Microsoft sign-in, and land on the Executive overview
afterwards.

Then check, in this order:

| Check | Expected |
|---|---|
| Executive overview loads | `600 calls in scope` under the filters |
| `/risk` deep link, pasted directly | the risk screen, not a 404 |
| Any employer on the accounts page | named account detail renders |
| `/api/v1/providers` in the browser | `openai` as `configured` **and** `reachable` |
| "What this period means" panel | generated sentences, not the unavailable state |
| **Move an action on "What should we do next?"** | **the change sticks** |

**Do not skip the last one.** A health check proves the database connection,
not that it is writable — and a write is exactly what the `/tmp` arrangement
could break. If reads work and that click fails, the problem is the database
path, not the app.

> `curl` against the site now returns a 302 to the sign-in page rather than
> JSON. That is the authentication working. Verify in a browser.

Also expected, and not faults: `/docs` and `/openapi.json` return **404** —
production disables them by design in `main.py`.

---

## Known limits of this setup

**Action-board edits reset when the app restarts.** Writes land in `/tmp`,
which is container-local; the startup command restores the pristine copy from
`/home/data` each time. For a two-week demo this is reasonable and arguably a
feature — every restart is a clean demo. If the client must keep their edits
across a restart, create an **Azure Database for PostgreSQL Flexible Server
(B1ms)**, point `DATABASE_URL` at it, and drop the `cp` from the startup
command. That is the only change; `asyncpg` is already a dependency.

**One instance only.** B1 does not autoscale, which suits SQLite — two
processes writing one SQLite file corrupts it. Do not scale out.

**Generated insights cost money per restart.** The insight cache is per process
and dies with it, so each restart re-pays OpenAI for the same sentences. Set
`LLM_PROVIDER=ollama` if the demo does not need generated prose — those panels
then show an explicit "unavailable" state, which is a designed state and not an
error.

---

## Teardown

`RG-NanoVox-POC` was empty when this was written, so deleting the whole group
would be safe **today**. It may not be by the time you tear down — anything
else put there in the meantime would go with it. Removing the two resources by
name is correct either way:

```powershell
az webapp delete --resource-group RG-NanoVox-POC --name nanovox-insights
az appservice plan delete --resource-group RG-NanoVox-POC --name nanovox-plan --yes
```

Or in the portal: open each of **nanovox-insights** and **nanovox-plan** and
delete them individually.

**The plan is the thing that bills.** Deleting the web app alone leaves the B1
plan running at $0.017/hour forever, which is the usual way a two-week demo
becomes a twelve-month line item. Check the group is back to what it held
before:

```powershell
az resource list --resource-group RG-NanoVox-POC -o table
```

The Entra app registration created in step 7 outlives both. It costs nothing,
but delete it from **Entra ID → App registrations** if you want no trace.
