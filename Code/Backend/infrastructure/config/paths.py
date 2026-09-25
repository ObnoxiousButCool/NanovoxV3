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

# data/ holds only local artefacts — the SQLite database and the logs — and is
# git-ignored whole. The corpus is not under it: it lives in Documents/ and is
# tracked (see below).
DEFAULT_DATA_DIR: Path = PROJECT_ROOT / "data"
DEFAULT_DATABASE_FILE: Path = DEFAULT_DATA_DIR / "db" / "nanovox_insights.db"
DEFAULT_LOG_DIR: Path = DEFAULT_DATA_DIR / "logs"
DEFAULT_CONFIG_DIR: Path = BACKEND_ROOT / "config"
# The built frontend, served by the API process so a deployment is one
# process on one port. Absent during development, where Vite serves it.
DEFAULT_FRONTEND_DIST: Path = PROJECT_ROOT / "Code" / "Frontend" / "dist"

# The corpus, in Documents/ and tracked in git. It used to default to the
# git-ignored data/source/, which no checkout ever populated: the corpus
# tests then skipped silently while scripts/check.sh still reported every
# gate passing, so the label-leak proof §6.3 calls the single most important
# safety property was not actually running. Tracked and found by default, it
# runs everywhere. Still overridable — a deployment that does not look like
# this checkout sets WORKBOOK_PATH and TRANSCRIPTS_DIR.
DEFAULT_CORPUS_DIR: Path = PROJECT_ROOT / "Documents"
# The v9 build-bible workbook — the current one only. A superseded revision
# (see Documents/superseded/) is kept as a regression fixture, never read by
# default.
DEFAULT_WORKBOOK_PATH: Path = DEFAULT_CORPUS_DIR / "nanovox_corpus_v9_build_bible_6.xlsx"
# Every current transcript batch PDF lives directly in this directory —
# `PdfCorpusSource`/`PdfAnswerKeySource` glob `*.pdf` here, non-recursively,
# so `Documents/superseded/` is naturally excluded (see plan §11: a
# superseded batch and its current revision must never both be ingested,
# which is exactly how the "17 Sep re-issue" trap there happened once).
# The corpus is delivered in batches short of a 600-call target — more
# will land in this directory over time, never requiring a settings change.
DEFAULT_TRANSCRIPTS_DIR: Path = DEFAULT_CORPUS_DIR
# L3's fixed scoring rubric (Call Quality Framework sheet).
DEFAULT_RUBRIC_PATH: Path = DEFAULT_CONFIG_DIR / "rubric.yaml"


def default_database_url() -> str:
    """SQLite URL for the default on-disk database, as a POSIX-style path.

    SQLAlchemy URLs use forward slashes on every platform, including Windows.
    """
    return f"sqlite+aiosqlite:///{DEFAULT_DATABASE_FILE.as_posix()}"
