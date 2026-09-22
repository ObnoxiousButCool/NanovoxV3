"""Serving a built frontend: mounted when present, absent otherwise, no traversal."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from frameworks_drivers.spa import mount_frontend

API_PREFIX = "/api/v1"


def _build(dist: Path) -> None:
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (dist / "app.js").write_text("console.log('hi')", encoding="utf-8")


def test_returns_false_and_mounts_nothing_when_no_build_exists(tmp_path: Path) -> None:
    app = FastAPI()
    mounted = mount_frontend(app, tmp_path / "dist", api_prefix=API_PREFIX)

    assert mounted is False
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 404


def test_serves_index_for_a_client_side_route(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _build(dist)
    app = FastAPI()
    mounted = mount_frontend(app, dist, api_prefix=API_PREFIX)

    assert mounted is True
    with TestClient(app) as client:
        response = client.get("/risk")
        assert response.status_code == 200
        assert response.text == "<html>app</html>"
        assert response.headers["cache-control"] == "no-cache, no-store, must-revalidate"


def test_serves_a_real_asset_with_a_long_lived_cache_header(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _build(dist)
    app = FastAPI()
    mount_frontend(app, dist, api_prefix=API_PREFIX)

    with TestClient(app) as client:
        response = client.get("/app.js")
        assert response.status_code == 200
        assert response.text == "console.log('hi')"
        assert "immutable" in response.headers["cache-control"]


def test_refuses_a_path_under_the_api_prefix(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _build(dist)
    app = FastAPI()
    mount_frontend(app, dist, api_prefix=API_PREFIX)

    with TestClient(app) as client:
        response = client.get(f"{API_PREFIX}/does-not-exist")
        assert response.status_code == 404


def test_refuses_path_traversal_outside_the_build(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _build(dist)
    (tmp_path / "secret.txt").write_text("not for the browser", encoding="utf-8")
    app = FastAPI()
    mount_frontend(app, dist, api_prefix=API_PREFIX)

    with TestClient(app) as client:
        response = client.get("/../secret.txt")
        # Starlette normalises the path before routing reaches the handler,
        # so this either 404s outright or falls back to index.html — never
        # the file outside dist.
        assert response.text != "not for the browser"
