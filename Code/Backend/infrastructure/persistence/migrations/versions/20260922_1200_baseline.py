"""baseline — no tables yet

Revision ID: 3ff80baf1219
Revises:
Created: 2026-09-22 12:00:00+00:00

The migration chain has to start somewhere before there is anything to
migrate, so there is always exactly one alembic head (plan §2A.7/§10). Phase
1 adds the first real revision, for the reference-data tables, on top of
this one.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "3ff80baf1219"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
