"""Shared test fixtures.

Tests never read the developer's ``.env``: settings are constructed
explicitly through ``IsolatedSettings`` so a local configuration change
cannot make the suite pass or fail.
"""

from __future__ import annotations

import shutil
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from frameworks_drivers.main import create_app
from infrastructure.config.settings import Settings
from infrastructure.persistence import tables as _tables  # noqa: F401
from infrastructure.persistence.engine import create_database_engine, create_session_factory
from infrastructure.persistence.models import Base
from tests.support.settings import make_settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Isolated settings: temporary database, logging off."""
    return make_settings(
        app_env="local",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
        log_enabled=False,
        log_to_console=False,
        log_dir=tmp_path / "logs",
    )


@pytest.fixture(scope="session")
def schema_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An empty database with the schema in it, built once for the session.

    `create_all` over twenty-one tables costs about 0.14s, and it was being
    paid by every integration test that touched a database -- some three
    hundred of them, which is three quarters of a minute spent building the
    same tables over and over.

    Built once here and copied per test below. Copying is a file copy of a
    few tens of kilobytes, so each test still gets its own database and
    nothing is shared between them: the isolation is the same, only the
    construction is not repeated.
    """
    template = tmp_path_factory.mktemp("schema") / "template.db"
    engine = create_engine(f"sqlite:///{template.as_posix()}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
    return template


def _database_file(settings: Settings) -> Path:
    """The file behind a SQLite URL, for a fixture that has to copy one."""
    return Path(settings.database_url.split("///", 1)[1])


@pytest.fixture
def schema(settings: Settings, schema_template: Path) -> None:
    """The tables the application expects, copied from the session template.

    Built from the ORM metadata rather than by running Alembic: that keeps
    the suite fast, and the migrations have their own test. A copy rather
    than a second `create_all` for the reason `schema_template` gives.
    """
    shutil.copyfile(schema_template, _database_file(settings))


@pytest_asyncio.fixture
async def engine(settings: Settings, schema: None) -> AsyncIterator[AsyncEngine]:
    """A real async engine over the same schema-bearing database `schema` built."""
    async_engine = create_database_engine(settings)
    try:
        yield async_engine
    finally:
        await async_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest.fixture
def app(settings: Settings, schema: None) -> FastAPI:
    """An application instance, not yet started, over a database with a schema."""
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """A client for a fully started application, including lifespan."""
    with TestClient(app) as test_client:
        yield test_client
