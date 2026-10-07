"""`PRAGMA integrity_check`, for SQLite.

A corrupted SQLite file does not announce itself — the next query against
whichever page happens to be damaged fails, or worse, returns another
table's rows (`Documents/notes/Corpus-v10-Schema-Update.md`'s finding: `employers` reading
back `members`' rows after a run that failed 94 of 100 calls). Nothing else
in this codebase checks for that on its own; this is the one place that
does, run right after the one kind of process most likely to write enough
to notice — an extraction run — rather than leaving corruption to be
discovered later by whoever happens to run the query that lands on the
damaged page.

Postgres has its own integrity guarantees and no equivalent pragma, so this
is a no-op for anything that is not SQLite — matching the same dialect
check `engine.py`'s pragmas use.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

#: What a clean database reports. Anything else is a corruption finding,
#: verbatim from SQLite — there is no value in reformatting it.
OK = "ok"


async def check_integrity(engine: AsyncEngine) -> str:
    """`OK` for a clean database, or a description of what's wrong. `None`
    would be a silent skip and indistinguishable from a check that ran and
    found nothing — this returns a string always, so a caller can log or
    print it without a branch for "did this even run".

    Corruption severe enough to break the query itself — the exact
    "database disk image is malformed" `Documents/notes/Corpus-v10-Schema-Update.md`
    reports — is caught rather than left to propagate: the failure to run
    the check is itself the finding, not a reason to skip reporting one.
    """
    if engine.dialect.name != "sqlite":
        return OK
    try:
        async with engine.connect() as connection:
            rows = (await connection.execute(text("PRAGMA integrity_check"))).scalars().all()
    except SQLAlchemyError as exc:
        return f"could not run the check: {exc}"
    return "; ".join(str(row) for row in rows) if rows else OK
