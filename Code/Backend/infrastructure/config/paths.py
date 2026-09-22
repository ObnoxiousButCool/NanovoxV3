"""Well-known filesystem locations, derived from this file's own position.

Deriving the roots from ``__file__`` keeps absolute paths out of the source.
Every path below is only a *default*: each is overridable through
configuration, so a deployment that does not look like this checkout still
works.
"""

from __future__ import annotations

from pathlib import Path

# .../NanovoxV3/Code/Backend/infrastructure/config/paths.py
#     parents[0] = config      parents[1] = infrastructure
#     parents[2] = Backend     parents[3] = Code            parents[4] = NanovoxV3
_THIS_FILE = Path(__file__).resolve()

BACKEND_ROOT: Path = _THIS_FILE.parents[2]
PROJECT_ROOT: Path = _THIS_FILE.parents[4]

# data/ is git-ignored below data/db and data/logs (client source material
# under data/source/ is separately excluded — plan §3.2, decision D8).
DEFAULT_DATA_DIR: Path = PROJECT_ROOT / "data"
DEFAULT_DATABASE_FILE: Path = DEFAULT_DATA_DIR / "db" / "nanovox_insights.db"
DEFAULT_LOG_DIR: Path = DEFAULT_DATA_DIR / "logs"
DEFAULT_CONFIG_DIR: Path = BACKEND_ROOT / "config"
# The built frontend, served by the API process so a deployment is one
# process on one port. Absent during development, where Vite serves it.
DEFAULT_FRONTEND_DIST: Path = PROJECT_ROOT / "Code" / "Frontend" / "dist"

# The v9 build-bible workbook — git-ignored client material (plan §3.2,
# decision D8). Absent on a machine that hasn't been handed the corpus;
# importing reference data fails with a clear message rather than silently
# reading nothing.
DEFAULT_WORKBOOK_PATH: Path = (
    PROJECT_ROOT / "data" / "source" / "nanovox_corpus_v9_build_bible_2.xlsx"
)


def default_database_url() -> str:
    """SQLite URL for the default on-disk database, as a POSIX-style path.

    SQLAlchemy URLs use forward slashes on every platform, including Windows.
    """
    return f"sqlite+aiosqlite:///{DEFAULT_DATABASE_FILE.as_posix()}"
