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
    # find_employer() round-trips the full Employer entity, same as
    # reference_repository.py's own storage direction — still never
    # compared, filtered or scored on.
    "infrastructure/persistence/repositories/reference_lookup.py",
    "infrastructure/reference/xlsx_reference_source.py",
    "tests/unit/test_no_circular_scoring.py",
    # Constructs an Employer fixture (all fields required) to exercise L2's
    # broker-of-record cross-check — the field is set, never read for a
    # decision.
    "tests/unit/test_classify_call_l2.py",
    "tests/integration/test_reference_repository.py",
    # Seeds an EmployerRow to exercise the insights corpus source. The
    # column is NOT NULL so a fixture has to set it; the assertion it
    # supports is that `EmployerFacts` does *not* carry it through.
    "tests/integration/test_insights_source.py",
    # Seeds employers to drive the /insights endpoints. Same reason: the
    # column is NOT NULL, and the response models have no field for it.
    "tests/integration/test_insights_endpoints.py",
    # Seeds employers to exercise the period filter. Same reason again: the
    # column is NOT NULL, so a row cannot be built without setting it, and
    # nothing in that file reads it back.
    "tests/integration/test_insights_period_filter.py",
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
