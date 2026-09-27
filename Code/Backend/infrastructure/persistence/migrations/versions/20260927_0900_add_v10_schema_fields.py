"""add v10 schema fields

Revision ID: c7d91c38c451
Revises: 0a81454dcf36
Created: 2026-09-27 09:00:00.000000+00:00

The Call Tag Schema grew from 16 fields to 20 (`Corpus-v10-Schema-Update.md`
§3). Storage for all four new fields, on both sides of Phase 5's comparison:

- `call_extractions` gains `primary_issue`, `secondary_issues` (L2) and
  `impact_scope_bucket`/`impact_scope_count` (L2), plus `root_cause_owner`
  and `preventable` (L4, computed — see `domain/derivations/root_cause.py`).
- `ground_truth` gains the five matching tracker columns (`preventable`
  needs no count/bucket split — it is a plain three-value enum on both
  sides).

Nullable, with no backfill, following `5e2a9c7d41b8`'s precedent: a row that
already exists was written before these fields existed, so its answers are
unknown rather than empty, and NULL is what both entities already read as
"not analysed" / "the tracker did not state it". The next pipeline run and
the next tracker import fill them in.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7d91c38c451"
down_revision: str | None = "0a81454dcf36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("call_extractions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("primary_issue", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("secondary_issues", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("impact_scope_bucket", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("impact_scope_count", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("root_cause_owner", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("preventable", sa.String(), nullable=True))

    with op.batch_alter_table("ground_truth", schema=None) as batch_op:
        batch_op.add_column(sa.Column("root_cause_owner", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("preventable", sa.String(), nullable=True))
        batch_op.add_column(
            sa.Column("primary_issue", sa.String(), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("secondary_issues", sa.JSON(), nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column("impact_scope", sa.String(), nullable=False, server_default="")
        )


def downgrade() -> None:
    with op.batch_alter_table("ground_truth", schema=None) as batch_op:
        batch_op.drop_column("impact_scope")
        batch_op.drop_column("secondary_issues")
        batch_op.drop_column("primary_issue")
        batch_op.drop_column("preventable")
        batch_op.drop_column("root_cause_owner")

    with op.batch_alter_table("call_extractions", schema=None) as batch_op:
        batch_op.drop_column("preventable")
        batch_op.drop_column("root_cause_owner")
        batch_op.drop_column("impact_scope_count")
        batch_op.drop_column("impact_scope_bucket")
        batch_op.drop_column("secondary_issues")
        batch_op.drop_column("primary_issue")
