# NanoVox Insights — one image, one process, one port.
#
# The API process serves the built frontend itself (see Code/Backend/
# frameworks_drivers/spa.py), so this is a single container and not a pair.
# There is no nginx, no second service and no CORS configuration, because the
# bundle and the API share an origin by construction.
#
# ## The layout is load-bearing
#
# infrastructure/config/paths.py derives every well-known location from its own
# __file__ — PROJECT_ROOT is parents[4], and DEFAULT_FRONTEND_DIST is
# PROJECT_ROOT/Code/Frontend/dist. Flatten the tree into /app and the process
# starts, finds no dist, serves the API alone and answers every page request
# with 404. So the image keeps the checkout's shape: /app/Code/Backend and
# /app/Code/Frontend/dist.

# --- Stage 1: build the frontend ------------------------------------------
# package.json asks for node >= 18; 20 is the current LTS.
FROM node:20-slim AS frontend

WORKDIR /build

# Manifests first, so a source-only change does not reinstall the world.
COPY Code/Frontend/package.json Code/Frontend/package-lock.json ./
RUN npm ci

COPY Code/Frontend/ ./
# .env.production sets VITE_API_BASE_URL=/api/v1 — relative, so this bundle
# works on any host and never needs rebuilding because an address changed.
RUN npm run build

# Fail here rather than at runtime: a missing dist is a container that serves
# JSON and 404s every page, which looks like a routing bug for an hour.
RUN test -f dist/index.html


# --- Stage 2: the runtime --------------------------------------------------
FROM python:3.14-slim AS runtime

# PYTHONDONTWRITEBYTECODE: the source is read-only in the image.
# PYTHONUNBUFFERED: logs reach the platform's collector as they happen rather
# than when a buffer fills, which matters when a container dies mid-request.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=prod \
    APP_HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app/Code/Backend

# curl is here for the HEALTHCHECK below and for debugging a running container.
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencies before source, so a code change replays only the last layers.
COPY Code/Backend/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY Code/Backend/ /app/Code/Backend/
COPY --from=frontend /build/dist /app/Code/Frontend/dist

# data/ is git-ignored and holds the SQLite database and the logs. Declared as
# a volume so the database survives a redeploy — without a mount here, every
# deployment starts empty and every screen renders its withheld state, which
# reads as a broken app rather than an empty one.
RUN mkdir -p /app/data/db /app/data/logs

# Run as nobody. The process only reads its own source and writes under
# /app/data, which the mount owns.
RUN useradd --create-home --uid 10001 nanovox \
    && chown -R nanovox:nanovox /app/data
USER nanovox

VOLUME ["/app/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/api/v1/health" || exit 1

# Migrations then serve. `alembic upgrade head` is a no-op once the schema is
# current, and SQLite creates the file on first connect but not the tables in
# it. Run from this directory because alembic.ini's script_location is relative.
#
# $PORT rather than a literal: App Service, Container Apps, Fly and Render all
# announce the port they expect this way, and a container that ignores it is
# marked unhealthy with no useful log line.
CMD ["sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn frameworks_drivers.main:app --host 0.0.0.0 --port ${PORT}"]
