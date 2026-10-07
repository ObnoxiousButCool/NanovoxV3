#!/usr/bin/env bash
# NanoVox Insights — load and run the shipped image.
#
# Needs Docker and nothing else: no Python, no Node, no network access to a
# registry. Everything the application runs on is inside the image.
#
#   ./run.sh [port]        default 8050
#
set -euo pipefail

# Git Bash on Windows rewrites arguments that look like POSIX paths into Windows
# ones, including the *container-side* paths handed to `docker cp` and
# `docker exec`. Left on, `mkdir -p /data/db` silently creates
# "C:/Program Files/Git/data/db" inside the container, the copy then fails with
# "Could not find the file /data/db in container", and a listing of /data looks
# correct because it is mangled the same way. Unset everywhere: it does nothing
# on Linux or macOS.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

PORT="${1:-8050}"
IMAGE="nanovox-insights:1.0.0"
VOLUME="nanovox-data"
CONTAINER="nanovox"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Host-side paths still have to be ones the engine can open, and with conversion
# off the engine is handed /c/... which it cannot resolve. `cygpath -m` gives
# C:/... with forward slashes, which Docker accepts; it exists only under Git
# Bash, so elsewhere this leaves the POSIX path alone.
if command -v cygpath >/dev/null 2>&1; then
    HERE="$(cygpath -m "$HERE")"
fi

say() { printf '\n== %s\n' "$1"; }

command -v docker >/dev/null || { echo "Docker is not installed or not on PATH." >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker is installed but the engine is not running." >&2; exit 1; }

say "Loading the image"
if docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "   already loaded."
else
    docker load -i "$HERE/nanovox-insights-1.0.0.tar.gz"
fi

say "Preparing the database"
# Docker copies the image's own /app/data into a volume only when that volume
# is empty, and a volume keeps whatever ownership its contents were written
# with. The image runs as uid 10001, so the database is chowned to it here —
# without that, every write is refused with "attempt to write a readonly
# database" and the action board fails on the first click.
# Test for the database itself, not for the volume. A seed that failed halfway
# leaves the volume behind with nothing in it, and "the volume exists" would
# then skip the copy and start the app on an empty corpus — every screen in its
# withheld state, which reads as a broken build rather than an empty one.
seeded=no
if docker volume inspect "$VOLUME" >/dev/null 2>&1; then
    if docker run --rm -v "$VOLUME:/data" alpine \
        test -s /data/db/nanovox_insights.db >/dev/null 2>&1; then
        seeded=yes
    fi
fi

if [ "$seeded" = yes ]; then
    echo "   database already present; leaving it alone."
else
    docker volume create "$VOLUME" >/dev/null
    # `docker cp` rather than a bind mount of this directory: a bind mount needs
    # a path the engine can resolve, and Git Bash hands it /c/... which Docker
    # Desktop cannot. Copying into a created-but-not-started container works the
    # same on Windows, macOS and Linux. The chown runs on start, after the copy.
    # The seeder has to be *running*, not merely created: `docker cp` into a
    # stopped container writes to its own filesystem layer, and the volume is
    # not mounted until the container runs, so the copy would land nowhere and
    # the volume would stay empty.
    seeder="$(docker run -d -v "$VOLUME:/data" alpine sleep 300)"
    # Remove it whatever happens. Without this a failed copy leaves a container
    # holding the volume, the next attempt cannot delete the volume to start
    # over, and the app comes up on an empty corpus looking like a broken build.
    trap 'docker rm -f "$seeder" >/dev/null 2>&1 || true' EXIT

    docker exec "$seeder" mkdir -p /data/db /data/logs
    docker cp "$HERE/nanovox_insights.db" "$seeder:/data/db/nanovox_insights.db"
    # chown after the copy: a file copied in arrives owned by root, and the
    # application runs as uid 10001 and could not write it.
    docker exec "$seeder" chown -R 10001:10001 /data

    docker rm -f "$seeder" >/dev/null
    trap - EXIT
    echo "   seeded with the shipped corpus."
fi

say "Starting"
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
docker run -d \
    --name "$CONTAINER" \
    -p "$PORT:8000" \
    -v "$VOLUME:/app/data" \
    --restart unless-stopped \
    ${OPENAI_API_KEY:+-e OPENAI_API_KEY="$OPENAI_API_KEY"} \
    -e "LLM_PROVIDER=${LLM_PROVIDER:-ollama}" \
    "$IMAGE" >/dev/null

say "Waiting for health"
for _ in $(seq 1 30); do
    state="$(docker inspect -f '{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo starting)"
    [ "$state" = "healthy" ] && break
    sleep 2
done

if [ "${state:-}" != "healthy" ]; then
    echo "Did not become healthy. Logs:" >&2
    docker logs --tail 30 "$CONTAINER" >&2
    exit 1
fi

say "Ready"
echo "   http://localhost:$PORT"
echo
echo "   stop:  docker stop $CONTAINER"
echo "   logs:  docker logs -f $CONTAINER"
