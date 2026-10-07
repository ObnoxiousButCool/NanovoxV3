# NanoVox Insights — shipped package

Everything needed to run the application on one machine. No source checkout, no
Python, no Node, no registry login, no internet connection after the files
arrive.

| File | Size | What it is |
|---|---|---|
| `nanovox-insights-1.0.0.tar.gz` | 77 MB | the application image: API, built frontend, Python runtime, all dependencies |
| `nanovox_insights.db` | 4 MB | the corpus — 600 calls, as of 2026-09-25 |
| `run.sh` / `run.ps1` | — | load, seed and start |

**Requires Docker.** Nothing else.

---

## Run it

```bash
./run.sh            # serves on 8050
./run.sh 9000       # or any port
```

```powershell
.\run.ps1           # Windows
.\run.ps1 -Port 9000
```

Then open `http://localhost:8050`. First run loads the image and seeds the
database; later runs reuse both.

## Check it is actually up

```bash
curl -s http://localhost:8050/api/v1/health
```

Expect `"status":"up"`, `"application":"NanoVox Insights"`, and the database
component `up`. If `application` reads anything else, a different build is on
that port.

---

## AI-generated insights

The screens that generate prose call a model provider. The package defaults to
`LLM_PROVIDER=ollama`, which means **no API key and no spend**: those panels
show an explicit "unavailable" state. That state is designed, not an error — the
application never substitutes templated copy for generated text.

To enable them, supply a key before starting:

```bash
OPENAI_API_KEY=sk-... LLM_PROVIDER=openai ./run.sh
```

Every other screen — risk, accounts, agents, demand, quality, actions — is
computed from the corpus and needs no provider at all.

---

## What persists, and what does not

The database lives in a Docker volume named `nanovox-data`, not in the image.
Action-board changes are written there and survive restarts.

- **Keep the data, update the app:** load a new image tar, re-run. The volume is
  left alone.
- **Start clean:** `docker rm -f nanovox && docker volume rm nanovox-data`, then
  run again.

Back it up by copying the file out:

```bash
docker run --rm -v nanovox-data:/d -v "$PWD:/out" alpine cp /d/db/nanovox_insights.db /out/backup.db
```

---

## Two things that will waste an afternoon if unknown

**The database must be owned by uid 10001.** The container runs as a non-root
user, and a Docker volume keeps whatever ownership its contents were written
with. `run.sh` handles this. Copy a database in by hand without
`chown -R 10001:10001` and every write is refused with *"attempt to write a
readonly database"* — reads work, so the app looks fine until someone moves an
action.

**Do not put the database on a network share.** SQLite needs POSIX byte-range
locks. On an SMB or NFS mount — or a Docker Desktop bind mount from a Windows
host — it fails with *"disk I/O error"* at startup. A Docker named volume, as
used here, is a real block device and is correct. The same applies to Azure
Files if this is ever moved to a cloud host.

---

## Support notes

- Logs: `docker logs -f nanovox`, JSON lines with a correlation id per request.
- The image serves API and frontend from **one process on one port**. There is
  no separate web server to configure and no CORS to set.
- `GET /api/v1/health` is the liveness check; the container has its own
  `HEALTHCHECK` on it, so `docker ps` reports `healthy` or not.
- API docs are disabled in production by design (`/docs` and `/openapi.json`
  return 404). That is not a fault.
