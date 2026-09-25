"""add action tables

Revision ID: 0a81454dcf36
Revises: 5e2a9c7d41b8
Created: 2026-09-25 08:29:12.737095+00:00

The action centre's write side (Revised plan Phase 4, D6): an action, the
calls behind it, its checklist and its activity log. Separate from the
derived findings `/insights/actions` returns, which store nothing.

Autogenerate also proposed dropping the server defaults on the `run_items`
token columns. That is drift between the model and revision 3cf31349ef15,
which added them deliberately, so it is left out of this revision.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0a81454dcf36"
down_revision: str | None = "5e2a9c7d41b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("source_kind", sa.String(), nullable=False),
        sa.Column("source_detail", sa.String(), nullable=True),
        sa.Column("issue_key", sa.String(), nullable=True),
        sa.Column("evidence", sa.String(), nullable=False),
        sa.Column("recommendation", sa.String(), nullable=True),
        sa.Column("owner_team", sa.String(), nullable=False),
        sa.Column("owner", sa.String(), nullable=True),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("employer_ref", sa.String(), nullable=True),
        sa.Column("broker_ref", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("assigned_on", sa.Date(), nullable=True),
        sa.Column("due", sa.Date(), nullable=True),
        sa.Column("action_taken", sa.String(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("measurement_start", sa.Date(), nullable=True),
        sa.Column("measurement_end", sa.Date(), nullable=True),
        sa.Column("seed_key", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_actions")),
        sa.UniqueConstraint("seed_key", name=op.f("uq_actions_seed_key")),
    )
    with op.batch_alter_table("actions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_actions_employer_ref"), ["employer_ref"], unique=False)
        batch_op.create_index(batch_op.f("ix_actions_status"), ["status"], unique=False)

    op.create_table(
        "action_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action_id", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["action_id"], ["actions.id"], name=op.f("fk_action_log_action_id_actions")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_action_log")),
    )
    with op.batch_alter_table("action_log", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_action_log_action_id"), ["action_id"], unique=False)

    op.create_table(
        "action_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["action_id"], ["actions.id"], name=op.f("fk_action_steps_action_id_actions")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_action_steps")),
        sa.UniqueConstraint("action_id", "position", name="uq_action_step"),
    )
    with op.batch_alter_table("action_steps", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_action_steps_action_id"), ["action_id"], unique=False)

    op.create_table(
        "action_calls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action_id", sa.Integer(), nullable=False),
        sa.Column("call_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["action_id"], ["actions.id"], name=op.f("fk_action_calls_action_id_actions")
        ),
        sa.ForeignKeyConstraint(
            ["call_id"], ["calls.id"], name=op.f("fk_action_calls_call_id_calls")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_action_calls")),
        sa.UniqueConstraint("action_id", "call_id", name="uq_action_call"),
    )
    with op.batch_alter_table("action_calls", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_action_calls_action_id"), ["action_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("action_calls", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_action_calls_action_id"))

    op.drop_table("action_calls")
    with op.batch_alter_table("action_steps", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_action_steps_action_id"))

    op.drop_table("action_steps")
    with op.batch_alter_table("action_log", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_action_log_action_id"))

    op.drop_table("action_log")
    with op.batch_alter_table("actions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_actions_status"))
        batch_op.drop_index(batch_op.f("ix_actions_employer_ref"))

    op.drop_table("actions")
