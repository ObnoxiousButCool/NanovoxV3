"""`design_churn_profile` is stored and never read by any calculation.

Plan principle 6: the employer "churn profile" in the workbook generated the
corpus, so no calculation may read it — it travels through as a stored,
displayed field only. This scans the actual source tree rather than trusting
a comment to stay true, because the whole point is that this can't drift
silently.
"""

from __future__ import annotations

from pathlib import Path

FIELD = "design_churn_profile"

# The only places allowed to mention the field: where it's declared, stored
# and read off the workbook — never compared, filtered or scored on.
ALLOWED = {
    "domain/entities/employer.py",
    "infrastructure/persistence/tables.py",
    "infrastructure/persistence/repositories/reference_repository.py",
    "infrastructure/reference/xlsx_reference_source.py",
    "tests/unit/test_no_circular_scoring.py",
    "tests/integration/test_reference_repository.py",
    "tests/integration/test_reference_lookup.py",
}

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_SKIP_DIR_PARTS = {".venv", "__pycache__", "migrations", "node_modules"}


def test_design_churn_profile_is_never_read_outside_storage() -> None:
    offending: list[str] = []
    for path in _BACKEND_ROOT.rglob("*.py"):
        if _SKIP_DIR_PARTS & set(path.parts):
            continue
        rel = path.relative_to(_BACKEND_ROOT).as_posix()
        if rel in ALLOWED:
            continue
        if FIELD in path.read_text(encoding="utf-8"):
            offending.append(rel)

    assert not offending, (
        f"{FIELD} referenced outside storage in: {offending} — "
        "the churn profile generated the corpus; scoring on it is circular"
    )
