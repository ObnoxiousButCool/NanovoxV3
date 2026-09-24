"""add call extraction control exceptions

Revision ID: 5e2a9c7d41b8
Revises: 3cf31349ef15
Created: 2026-09-24 11:00:00.000000+00:00

L1 has detected control exceptions (schema field 7) since A1, and threw
them away: `call_extractions` had nowhere to put them, so metric 7 had an
answer key and nothing to score against.

Nullable, with no backfill. A row that already exists was written before
L1's result was kept, so its control exceptions are unknown rather than
empty — and NULL is what `CallExtraction` reads as "not analysed". The next
run over the corpus fills them in.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5e2a9c7d41b8"
down_revision: str | None = "3cf31349ef15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("call_extractions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("control_exceptions", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("call_extractions", schema=None) as batch_op:
        batch_op.drop_column("control_exceptions")
