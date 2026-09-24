"""Runs the extraction pipeline (A5) over every ingested call, in the
background of the process that started it (plan §8 Phase 3, "run
orchestration... resumability").

A run's own status and its items' statuses answer different questions
(`domain/value_objects/run_status.py`'s module docstring): this use case
keeps the run RUNNING for as long as any item is being worked, whatever
happens to individual items — a failed call is a failed item, not a
failed run.

Resumability means re-entering `_work` for a run that already exists:
every item still needing work (pending, running, failed or cancelled —
`RunItemStatus.needs_work`) is picked up again, and whatever already
completed or was skipped is left alone. `RunStatus.FAILED` is reserved
for that re-entry itself breaking (a repository error, not a call the
pipeline couldn't finish) — an item failing never fails the run, but an
unhandled error in the loop that tracks items would otherwise leave the
run stuck RUNNING forever, which is worse than marking it FAILED and
resumable.

`reconcile_interrupted` must run once, before any `resume`, whenever a
fresh process starts (the container wires this into the API's startup
and the CLI's entry point): a run this process finds still active
belonged to a process that no longer exists, since a fresh
`BackgroundRunner` starts empty — nothing here could actually be working
it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from application.ports.call_repository import CallRepository
from application.ports.clock import Clock
from application.ports.llm_provider import LLMProvider
from application.ports.provider_registry import ProviderSource
from application.ports.run_repository import RunRecord, RunRepository
from application.ports.run_scheduler import RunScheduler
from domain.errors import ConflictError, NotFoundError
from domain.run_progress import RunProgress, summarise
from domain.value_objects.run_status import RunItemStatus, RunStatus
from domain.value_objects.token_usage import TokenUsage


class _PipelineOutcome(Protocol):
    """The one thing this use case reads off a pipeline result.

    Narrowed to `usage` rather than typed as `ExtractionPipelineResult` for
    the same reason `_CallPipeline` exists: a test double should not have to
    build L1-L4's whole result to exercise a per-item loop.
    """

    @property
    def usage(self) -> TokenUsage: ...


class _CallPipeline(Protocol):
    """What this use case needs from `ExtractionPipeline` — just enough to
    let a test double stand in without building L1-L4's whole fake stack
    again for what is, here, a per-item loop concern."""

    async def execute(self, call_reference: str, provider: LLMProvider) -> _PipelineOutcome: ...


@dataclass(frozen=True)
class RunStatusView:
    """A run's own record alongside how far it has got — what the CLI and
    the endpoint both need to report, bundled once rather than issued as
    two round trips at every call site."""

    record: RunRecord
    progress: RunProgress


class RunExtractionOverCorpus:
    def __init__(
        self,
        *,
        calls: CallRepository,
        runs: RunRepository,
        pipeline: _CallPipeline,
        provider_registry: ProviderSource,
        background_runner: RunScheduler,
        clock: Clock,
    ) -> None:
        self._calls = calls
        self._runs = runs
        self._pipeline = pipeline
        self._provider_registry = provider_registry
        self._background_runner = background_runner
        self._clock = clock

    async def start(self, *, provider_name: str | None = None, model: str | None = None) -> int:
        """Create a new run over every ingested call and begin working it."""
        references = await self._calls.list_references()
        provider = self._provider_registry.create(provider_name, model)
        run_id = await self._runs.create(
            references,
            provider=provider.name,
            model=provider.model,
            created_at=self._clock.now(),
        )
        self._background_runner.start(run_id, self._work(run_id, provider))
        return run_id

    async def resume(self, run_id: int) -> None:
        """Re-enter a run that stopped before every item finished."""
        record = await self._runs.get(run_id)
        if record is None:
            raise NotFoundError(f"There is no run {run_id}.")
        if not record.status.is_resumable:
            raise ConflictError(
                f"Run {run_id} is {record.status.value} and cannot be resumed.",
                detail="Only a CANCELLED, FAILED or INTERRUPTED run can be resumed.",
            )

        provider = self._provider_registry.create(record.provider, record.model)
        if not self._background_runner.start(run_id, self._work(run_id, provider)):
            raise ConflictError(f"Run {run_id} is already being worked.")

    async def cancel(self, run_id: int) -> None:
        """Ask a run to stop after its current item. Resumable afterwards."""
        record = await self._runs.get(run_id)
        if record is None:
            raise NotFoundError(f"There is no run {run_id}.")
        if not record.status.is_active:
            raise ConflictError(f"Run {run_id} is {record.status.value}, not active.")
        await self._runs.set_status(run_id, RunStatus.CANCELLING)

    async def status(self, run_id: int) -> RunStatusView | None:
        record = await self._runs.get(run_id)
        if record is None:
            return None
        items = await self._runs.items(run_id)
        return RunStatusView(record=record, progress=summarise(item.status for item in items))

    async def reconcile_interrupted(self) -> tuple[int, ...]:
        """Move every run this process finds still active to INTERRUPTED.

        Returns the ids moved."""
        active = await self._runs.active_run_ids()
        for run_id in active:
            await self._runs.set_status(run_id, RunStatus.INTERRUPTED, at=self._clock.now())
        return active

    async def _work(self, run_id: int, provider: LLMProvider) -> None:
        # A cancel requested before this task got its first turn on the
        # event loop must survive being overwritten here — RUNNING is the
        # starting status only when nothing has already asked to stop.
        record = await self._runs.get(run_id)
        if record is None or record.status is not RunStatus.CANCELLING:
            await self._runs.set_status(run_id, RunStatus.RUNNING, at=self._clock.now())

        try:
            pending = [item for item in await self._runs.items(run_id) if item.status.needs_work]
            cancelled = False
            for item in pending:
                record = await self._runs.get(run_id)
                if record is not None and record.status is RunStatus.CANCELLING:
                    cancelled = True
                    await self._runs.set_item_status(
                        run_id, item.call_reference, RunItemStatus.CANCELLED
                    )
                    continue

                await self._runs.set_item_status(run_id, item.call_reference, RunItemStatus.RUNNING)
                started = self._clock.now()
                try:
                    result = await self._pipeline.execute(item.call_reference, provider)
                except Exception as exc:
                    await self._runs.set_item_status(
                        run_id,
                        item.call_reference,
                        RunItemStatus.FAILED,
                        error=str(exc),
                        duration_ms=_elapsed_ms(started, self._clock.now()),
                    )
                else:
                    await self._runs.set_item_status(
                        run_id,
                        item.call_reference,
                        RunItemStatus.COMPLETED,
                        usage=result.usage,
                        duration_ms=_elapsed_ms(started, self._clock.now()),
                    )

            final_status = RunStatus.CANCELLED if cancelled else RunStatus.COMPLETED
            await self._runs.set_status(run_id, final_status, at=self._clock.now())
        except Exception:
            # The orchestration itself broke — a repository error, not a
            # single call's failure (that's already handled per item
            # above). Left as RUNNING, this run would look active forever
            # to anything that hasn't crashed; FAILED makes it resumable.
            await self._runs.set_status(run_id, RunStatus.FAILED, at=self._clock.now())
            raise


def _elapsed_ms(started: datetime, finished: datetime) -> float:
    """Wall clock between two readings of the injected clock.

    Never `time.monotonic()`: the domain and application layers take their
    time from the clock they were given, so a test can run a whole corpus
    without waiting for one (plan §2A.1 — no clock, pass it in).
    """
    return (finished - started).total_seconds() * 1000
