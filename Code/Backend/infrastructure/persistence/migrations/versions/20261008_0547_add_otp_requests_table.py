"""add otp requests table

Revision ID: 7a232f565d6c
Revises: eae14c6794c6
Created: 2026-10-08 05:47:04.667710+00:00

The email-OTP login's one table (`feature/email-otp-login`, not on main):
one row per code issued, never overwritten — see
`application/ports/otp_repository.py` on why a resend is a new row rather
than an update to the last one.

Autogenerate also proposed dropping the server defaults on `ground_truth`'s
and `run_items`' columns. That is drift from revisions `c7d91c38c451` and
earlier, which added them deliberately, so — following that precedent — it
is left out of this revision.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7a232f565d6c"
down_revision: str | None = "eae14c6794c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "otp_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_otp_requests")),
    )
    with op.batch_alter_table("otp_requests", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_otp_requests_email"), ["email"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("otp_requests", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_otp_requests_email"))
    op.drop_table("otp_requests")
