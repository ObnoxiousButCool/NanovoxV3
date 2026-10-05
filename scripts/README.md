# NanoVox Insights setup scripts

One-shot scripts to go from a fresh clone to a running app, plus the
verification gate that CI runs.

| script | for |
|---|---|
| `start.bat` / `start.sh` | **Development.** Two servers — uvicorn with reload, and Vite — on 8000 and 5173. Bound to 127.0.0.1: reachable from this machine only. |
| `deploy.ps1` | **Deployment on Windows.** One process serving the API and the built frontend on a single port, registered with Task Scheduler. Bound to every interface by default: reachable from other machines, including over VPN. |
| `deploy.sh` | **Deployment on macOS.** The same seven steps, registered with launchd. On Linux it deploys everything and hands you the run command. |
| `check.sh` / `check.bat` | Every gate CI runs. |
| `cloudflared/config.example.yml` | **Publishing a deployment** on a public internet hostname through a Cloudflare Tunnel. Fronts `deploy.ps1`; it does not replace it, and you don't need it for VPN-only access. |

## If you're deploying to a VM so other machines (over VPN) can reach it

Use `deploy.ps1` (or `deploy.sh` on Linux/macOS), not `start.bat` / `start.sh`.
This is almost always the actual problem, so it's worth stating plainly why:

`start.bat` is development mode. It runs two servers — uvicorn on 8000, Vite
on 5173 — both bound to `127.0.0.1` by default, and the frontend's `.env`
points `VITE_API_BASE_URL` at the absolute address
`http://127.0.0.1:8000/api/v1`. Run that on a VM and it works — from inside
the VM, to the VM. It cannot work from anywhere else, for two independent
reasons that both have to be fixed:

1. **`127.0.0.1` means "this machine," to every machine.** A server bound to
   it refuses connections that didn't originate locally, no matter how the
   network is otherwise configured. Being on the company VPN doesn't change
   what `127.0.0.1` means on the VM — it still means the VM, to the VM.
2. **Even with a fixed bind address, the frontend bundle itself hardcodes
   where to send API calls.** A production build made from `.env` (not
   `.env.production`) bakes in `http://127.0.0.1:8000/api/v1`. Load the page
   from a laptop over VPN and the browser *on the laptop* tries to call
   `127.0.0.1:8000` — its own loopback, not the VM's — and every API call
   fails even though the page itself loaded fine.

`deploy.ps1` fixes both: it binds `0.0.0.0` by default (every interface, not
just loopback), and it builds the frontend with `Code/Frontend/.env.production`
in effect, which sets `VITE_API_BASE_URL=/api/v1` — a relative path, so the
bundle calls whatever origin served it, on any host. There is also only one
port, because `deploy.ps1` builds the frontend and serves it from the same
FastAPI process that serves the API (see `frameworks_drivers/spa.py`) — so
there's no separate web server or CORS configuration to get wrong either.

What `deploy.ps1` does **not** do on its own: open the Windows Firewall. It
prints the exact command at the end of a successful run, because running it
unconditionally on every deploy would be a surprising thing for a script to
do to a machine's firewall without being asked:

```powershell
New-NetFirewallRule -DisplayName 'NanoVox Insights' -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

After that, from a machine connected to the VPN, browse to the VM's network
address (also printed at the end of the run) — not `127.0.0.1`, not
`localhost`:

```
http://<the VM's VPN or LAN IP>:8000
```

If it's *still* unreachable after the firewall rule and the right address,
the remaining usual suspects are: a network-level ACL/NSG on the VM itself
(outside Windows Firewall — check with whoever provisioned the VM), the VPN's
own split-tunnelling or routing not including the VM's subnet, or another
process already holding port 8000 (`deploy.ps1 -Port 8080` sidesteps that).

## Deploying

Windows, from an elevated PowerShell:

```powershell
.\scripts\deploy.ps1
```

macOS, with sudo (a LaunchDaemon is written to `/Library/LaunchDaemons`):

```bash
sudo ./scripts/deploy.sh
```

Either script takes `--no-service` (`-NoService` on Windows) to set everything
up without registering a service, which is also the only mode needing no
elevation — useful for a first run you want to watch in the foreground before
trusting it to a scheduled task.

Installs dependencies, migrates the database, builds the frontend, registers a
startup task and verifies the result. Re-running it after a `git pull` is the
update path.

## Running the app for development

- **Windows:** double-click `start.bat`, or run it from a terminal:
  ```bat
  scripts\start.bat
  ```
- **macOS / Linux:**
  ```bash
  ./scripts/start.sh
  ```

Each script:

1. Creates the backend virtual environment (`Code/Backend/.venv`) if missing.
2. Installs backend dependencies from `Code/Backend/requirements.txt`.
3. Copies `Code/Backend/.env.example` → `.env` if no `.env` exists yet.
4. Applies database migrations. SQLite creates the file on first connect but not
   the tables in it, so without this a fresh clone starts and dies on
   "no such table: runs".
5. Installs frontend dependencies (`npm install`) if `node_modules` is missing.
6. Copies `Code/Frontend/.env.example` → `.env` if no `.env` exists yet.
7. Starts the backend (uvicorn, port 8000) and frontend (Vite, port 5173), then
   opens the app in your browser.

Re-running is safe and fast: it skips venv creation and `npm install` once they
exist, and never overwrites an existing `.env`.

## Verifying before you commit

```bash
./scripts/check.sh
```

```bat
scripts\check.bat
```

Runs every gate the CI pipeline runs, in the same order: backend format, lint,
strict typing, Clean Architecture import contracts, tests with an 85% coverage
floor, exactly-one-migration-head; then frontend lint, strict typing, tests
with coverage, and a check that the generated API client (`openapi.json`,
`schema.ts`) matches what the backend actually serves. Requires the dev
tooling, which `check` expects in the venv:

```bash
Code/Backend/.venv/Scripts/pip install -r Code/Backend/requirements-dev.txt
```

## Prerequisites

- **Python 3.10+** on `PATH`. The backend deliberately avoids 3.11-only syntax
  so it runs on the interpreter most machines already have.
- **Node.js 18+** on `PATH` (CI uses 20).

## Configuration

`Code/Backend/.env` and `Code/Frontend/.env` are generated from the matching
`.env.example`, and the defaults work for a local run with no editing.
`Code/Frontend/.env.production` is checked in as-is (it holds no secrets) and
takes over automatically whenever Vite builds in production mode —
`npm run build`, and therefore `deploy.ps1` / `deploy.sh` — regardless of what
`.env` says.

The backend validates its configuration at startup and fails immediately with a
message naming the offending variable, so a mistake here is obvious rather than
mysterious.

Model provider keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) are blank by
default; `GET /api/v1/providers` reports whether a configured provider is
actually reachable.

## Logs

The app writes its own rotating log files under `data/logs/` at the repo
root (not under `Code/Backend/`), regardless of how it was started:

- `nanovox-insights-app.log` — application log.
- `nanovox-insights-access.log` — request log.
- `nanovox-insights-llm-audit.log` — LLM prompt/response audit trail, when
  `LOG_LLM_PROMPTS` is enabled.

This is the first place to look if `deploy.ps1` / `deploy.sh` reports the app
never came up.

## Stopping the servers

- **Development (`start.bat` / `start.sh`):** close the two spawned windows
  ("NanoVox Insights Backend" / "NanoVox Insights Frontend"), or press Ctrl+C
  in each.
- **Deployment (`deploy.ps1`):**
  ```powershell
  Stop-ScheduledTask -TaskName 'NanoVoxInsights'
  ```
- **Deployment (`deploy.sh` on macOS):**
  ```bash
  sudo launchctl bootout system/com.technossus.nanovox-insights
  ```
