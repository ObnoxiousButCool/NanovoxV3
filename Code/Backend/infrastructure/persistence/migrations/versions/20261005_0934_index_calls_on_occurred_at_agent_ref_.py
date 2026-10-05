"""index calls on occurred_at, agent_ref and its foreign keys

Revision ID: eae14c6794c6
Revises: c7d91c38c451
Created: 2026-10-05 09:34:00.306427+00:00

Every one of the eight insight endpoints filters the whole `calls` table by
`occurred_at` for its own metric window, and `/agents`, `/risk` and
`/hierarchy` filter or group by `agent_ref` and `employer_id`. None of the
four carried an index; `member_id` and `employer_contact_id` are foreign
keys that hadn't picked up the `index=True` every other foreign key in this
module already has. Invisible at 600 rows — a full table scan is a full
table scan either way at this size — and a straightforward win once the
corpus is not 600 rows.

Autogenerate also proposed dropping the server defaults on `ground_truth`'s
and `run_items`' columns. That is pre-existing drift between the model and
the revisions that added them, unrelated to indexing `calls`, so it is left
out of this revision (same reasoning as `0a81454dcf36`'s note about
`run_items`).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "eae14c6794c6"
down_revision: str | None = "c7d91c38c451"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("calls", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_calls_agent_ref"), ["agent_ref"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_calls_employer_contact_id"), ["employer_contact_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_calls_employer_id"), ["employer_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_calls_member_id"), ["member_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_calls_occurred_at"), ["occurred_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("calls", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_calls_occurred_at"))
        batch_op.drop_index(batch_op.f("ix_calls_member_id"))
        batch_op.drop_index(batch_op.f("ix_calls_employer_id"))
        batch_op.drop_index(batch_op.f("ix_calls_employer_contact_id"))
        batch_op.drop_index(batch_op.f("ix_calls_agent_ref"))
