"""add approved emails table

Revision ID: c62843240570
Revises: 7a232f565d6c
Created: 2026-10-08 06:42:55.786159+00:00

The email-OTP allowlist moves from `config/approved_emails.yaml` to its own
table (Ranjit, 2026-10-08 — see Documents/notes/Decisions-and-Questions.md).
Starts empty: the YAML file's one entry was a placeholder, not a real
approved address, so there is nothing to carry over. Populate it with
`python -m frameworks_drivers.cli.manage_approved_emails add <email>`.

Autogenerate also proposed dropping the server defaults on `ground_truth`'s
and `run_items`' columns. That is drift from earlier revisions, which added
them deliberately, so — following `0a81454dcf36`'s and `7a232f565d6c`'s
precedent — it is left out of this revision.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c62843240570"
down_revision: str | None = "7a232f565d6c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approved_emails",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approved_emails")),
    )
    with op.batch_alter_table("approved_emails", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_approved_emails_email"), ["email"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("approved_emails", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_approved_emails_email"))
    op.drop_table("approved_emails")
