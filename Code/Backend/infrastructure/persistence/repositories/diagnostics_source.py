"""Reads Phase 5's diagnostics out of the tables a run leaves behind.

Three aggregate queries, no per-row loading: the counts are what the
diagnostics show, and pulling a hundred thousand markers into Python to
length them would be the same answer more slowly.

The run cost is computed from `run_items` rather than read from a stored
total on `runs` — see `domain/run_cost.py`. A stored roll-up is a second
copy of a number, and a resumed run, a retried item or a backfill each give
it a chance to disagree with the items beneath it.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.diagnostics_source import Diagnostics, DiagnosticsSource
from domain.run_cost import RunCost, run_cost
from domain.value_objects.call_resolution_status import CallResolutionStatus
from domain.value_objects.token_usage import TokenUsage
from infrastructure.persistence.tables import CallRow, RunItemRow, RunRow, ScoreMarkerRow

#: What `RaisedMarker.verification_status` holds for a marker that survived.
#: Everything else is an `EvidenceRejection` value.
_ACCEPTED = "accepted"


class SqlDiagnosticsSource(DiagnosticsSource):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def read(self) -> Diagnostics:
        async with self._session_factory() as session:
            counts = (
                await session.execute(
                    select(ScoreMarkerRow.verification_status, func.count()).group_by(
                        ScoreMarkerRow.verification_status
                    )
                )
            ).all()

            unresolved = (
                (
                    await session.execute(
                        select(CallRow.reference)
                        .where(CallRow.resolution_status == CallResolutionStatus.CALLER_UNRESOLVED)
                        .order_by(CallRow.reference)
                    )
                )
                .scalars()
                .all()
            )

            cost = await self._last_run_cost(session)

        raised = sum(count for _, count in counts)
        rejected = tuple(
            sorted(
                ((status, count) for status, count in counts if status != _ACCEPTED),
                key=lambda pair: (-pair[1], pair[0]),
            )
        )
        return Diagnostics(
            rejected_evidence=rejected,
            markers_raised=raised,
            unresolved_callers=tuple(unresolved),
            last_run_cost=cost,
        )

    async def _last_run_cost(self, session: AsyncSession) -> RunCost | None:
        """The most recently created run's cost, or `None` if none exists.

        Ordered by `created_at` then `id`: two runs created in the same
        second would otherwise come back in whatever order the database
        chose, and "the last run" has to mean one particular run.
        """
        last = (
            await session.execute(
                select(RunRow.id).order_by(RunRow.created_at.desc(), RunRow.id.desc()).limit(1)
            )
        ).scalar_one_or_none()
        if last is None:
            return None

        rows = (
            await session.execute(
                select(
                    RunItemRow.input_tokens,
                    RunItemRow.output_tokens,
                    RunItemRow.usage_reported,
                    RunItemRow.duration_ms,
                ).where(RunItemRow.run_id == last)
            )
        ).all()
        # Items that never ran contribute no usage, and counting them would
        # drag the per-call figures down for a run that simply is not
        # finished — so an item with no duration and no tokens is skipped.
        contributing = [
            row
            for row in rows
            if row.duration_ms is not None or row.input_tokens or row.output_tokens
        ]
        return run_cost(
            [
                TokenUsage(
                    input_tokens=row.input_tokens,
                    output_tokens=row.output_tokens,
                    reported=row.usage_reported,
                )
                for row in contributing
            ],
            [row.duration_ms for row in contributing],
        )
