"""`RunExtractionOverCorpus` orchestration: creating a run, working its
items, resuming, cancelling and reconciling — with every port faked."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from application.ports.call_repository import CallRepository, IngestCounts
from application.ports.clock import Clock
from application.ports.llm_provider import LLMProvider
from application.ports.run_repository import RunItemRecord, RunRecord, RunRepository
from application.use_cases.run_extraction_over_corpus import RunExtractionOverCorpus
from domain.entities.ingested_call import IngestedCall
from domain.errors import ConflictError, NotFoundError
from domain.value_objects.call_resolution_status import CallResolutionStatus
from domain.value_objects.caller_type import CallerType
from domain.value_objects.run_status import RunItemStatus, RunStatus
from domain.value_objects.token_usage import TokenUsage
from infrastructure.llm.registry import ProviderRegistry
from infrastructure.logging.llm_audit import LlmAuditLog
from infrastructure.runner.background_runner import BackgroundRunner
from tests.support.settings import make_settings

_NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


def _call(reference: str) -> IngestedCall:
    return IngestedCall(
        reference=reference,
        caller_type=CallerType.MEMBER,
        caller_ref="CB-7700205",
        agent_ref="AGT-01",
        transcript=None,
        resolution_status=CallResolutionStatus.RESOLVED,
        resolution_reason=None,
        member_ref=None,
        employer_contact_ref=None,
        employer_ref=None,
    )


class _FakeCalls(CallRepository):
    def __init__(self, references: tuple[str, ...] = ()) -> None:
        self._references = references

    async def upsert_all(self, calls: tuple[IngestedCall, ...]) -> IngestCounts:
        raise NotImplementedError

    async def get(self, reference: str) -> IngestedCall | None:
        return _call(reference) if reference in self._references else None

    async def list_references(self) -> tuple[str, ...]:
        return self._references


class FixedClock(Clock):
    def now(self) -> datetime:
        return _NOW


@dataclass(frozen=True)
class _FakeOutcome:
    """Just the `usage` the runner reads off a pipeline result."""

    usage: TokenUsage = field(
        default_factory=lambda: TokenUsage(input_tokens=100, output_tokens=20)
    )


class _FakePipeline:
    """Stands in for `ExtractionPipeline` — the use case only ever calls
    `execute`, so that's the entire surface a fake needs here."""

    def __init__(self) -> None:
        self.executed: list[str] = []
        self._fail_for: frozenset[str] = frozenset()
        self.outcome = _FakeOutcome()

    def fail_for(self, *references: str) -> None:
        self._fail_for = frozenset(references)

    async def execute(self, call_reference: str, provider: LLMProvider) -> _FakeOutcome:
        self.executed.append(call_reference)
        if call_reference in self._fail_for:
            raise ValueError(f"simulated failure for {call_reference}")
        return self.outcome


class _FakeRuns(RunRepository):
    """An in-memory run ledger — real enough to exercise the use case's
    resumability and cancellation logic against."""

    def __init__(self) -> None:
        self._next_id = 1
        self._records: dict[int, RunRecord] = {}
        self._items: dict[int, list[RunItemRecord]] = {}

    async def create(
        self,
        call_references: Sequence[str],
        *,
        provider: str,
        model: str,
        created_at: datetime,
    ) -> int:
        run_id = self._next_id
        self._next_id += 1
        self._records[run_id] = RunRecord(
            id=run_id,
            status=RunStatus.PENDING,
            provider=provider,
            model=model,
            created_at=created_at,
            started_at=None,
            finished_at=None,
        )
        self._items[run_id] = [
            RunItemRecord(call_reference=reference, status=RunItemStatus.PENDING)
            for reference in call_references
        ]
        return run_id

    async def get(self, run_id: int) -> RunRecord | None:
        return self._records.get(run_id)

    async def items(self, run_id: int) -> tuple[RunItemRecord, ...]:
        return tuple(self._items.get(run_id, []))

    async def set_status(
        self, run_id: int, status: RunStatus, *, at: datetime | None = None
    ) -> None:
        record = self._records[run_id]
        started_at = record.started_at
        finished_at = record.finished_at
        if at is not None and status is RunStatus.RUNNING and started_at is None:
            started_at = at
        if at is not None and status.is_terminal:
            finished_at = at
        self._records[run_id] = RunRecord(
            id=record.id,
            status=status,
            provider=record.provider,
            model=record.model,
            created_at=record.created_at,
            started_at=started_at,
            finished_at=finished_at,
        )

    async def set_item_status(
        self,
        run_id: int,
        call_reference: str,
        status: RunItemStatus,
        *,
        error: str | None = None,
        usage: TokenUsage | None = None,
        duration_ms: float | None = None,
    ) -> None:
        items = self._items[run_id]
        for index, item in enumerate(items):
            if item.call_reference == call_reference:
                items[index] = RunItemRecord(
                    call_reference=call_reference, status=status, error=error
                )
                return
        raise AssertionError(f"no item {call_reference!r} in run {run_id}")

    async def active_run_ids(self) -> tuple[int, ...]:
        return tuple(run_id for run_id, record in self._records.items() if record.status.is_active)

    def is_terminal(self, run_id: int) -> bool:
        """Test-only convenience for polling a run to its resting state."""
        return self._records[run_id].status.is_terminal


class _BrokenRuns(_FakeRuns):
    """Raises from `items` once armed — the seam the run-level-failure
    test uses, since an item's own failure is already handled per item
    and can't reach `_work`'s outer error path."""

    def __init__(self) -> None:
        super().__init__()
        self.broken = False

    async def items(self, run_id: int) -> tuple[RunItemRecord, ...]:
        if self.broken:
            raise RuntimeError("simulated repository failure")
        return await super().items(run_id)


def _use_case(
    *, references: tuple[str, ...] = ("C-0001",), pipeline: _FakePipeline | None = None
) -> tuple[RunExtractionOverCorpus, _FakeRuns, _FakePipeline]:
    runs = _FakeRuns()
    fake_pipeline = pipeline or _FakePipeline()
    use_case = RunExtractionOverCorpus(
        calls=_FakeCalls(references),
        runs=runs,
        pipeline=fake_pipeline,
        provider_registry=ProviderRegistry(make_settings(llm_provider="ollama"), LlmAuditLog()),
        background_runner=BackgroundRunner(),
        clock=FixedClock(),
    )
    return use_case, runs, fake_pipeline


async def _wait_for(condition: Callable[[], bool], timeout: float = 1.0) -> None:
    # A background task just scheduled via `BackgroundRunner.start` gets no
    # turn at all until something here actually yields — without this, a
    # run already terminal *before* the call under test (e.g. INTERRUPTED,
    # pending resume) would satisfy `condition()` on the very first check.
    await asyncio.sleep(0)
    deadline = asyncio.get_running_loop().time() + timeout
    while not condition():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition never became true")
        await asyncio.sleep(0.01)


class TestStart:
    async def test_a_new_run_processes_every_ingested_call(self) -> None:
        use_case, runs, pipeline = _use_case(references=("C-0001", "C-0002"))

        run_id = await use_case.start()
        await _wait_for(lambda: runs.is_terminal(run_id))

        assert set(pipeline.executed) == {"C-0001", "C-0002"}
        record = await runs.get(run_id)
        assert record is not None
        assert record.status is RunStatus.COMPLETED
        assert record.started_at is not None
        assert record.finished_at is not None

    async def test_a_failed_item_does_not_fail_the_run(self) -> None:
        pipeline = _FakePipeline()
        pipeline.fail_for("C-0002")
        use_case, runs, _ = _use_case(references=("C-0001", "C-0002"), pipeline=pipeline)

        run_id = await use_case.start()
        await _wait_for(lambda: runs.is_terminal(run_id))

        record = await runs.get(run_id)
        assert record is not None
        assert record.status is RunStatus.COMPLETED
        items = {item.call_reference: item for item in await runs.items(run_id)}
        assert items["C-0001"].status is RunItemStatus.COMPLETED
        assert items["C-0002"].status is RunItemStatus.FAILED
        assert items["C-0002"].error is not None


class TestResume:
    async def test_resuming_an_unresumable_run_is_refused(self) -> None:
        use_case, runs, _ = _use_case()
        run_id = await use_case.start()
        await _wait_for(lambda: runs.is_terminal(run_id))

        with pytest.raises(ConflictError, match="cannot be resumed"):
            await use_case.resume(run_id)

    async def test_resuming_an_unknown_run_is_refused(self) -> None:
        use_case, _, _ = _use_case()

        with pytest.raises(NotFoundError):
            await use_case.resume(999)

    async def test_resuming_only_reprocesses_items_that_still_need_work(self) -> None:
        # Simulates a process that died after C-0001 finished but before
        # C-0002 was even picked up — exactly what reconcile_interrupted
        # exists to detect and make resumable.
        use_case, runs, pipeline = _use_case(references=("C-0001", "C-0002"))
        run_id = await runs.create(
            ("C-0001", "C-0002"), provider="ollama", model="m", created_at=_NOW
        )
        await runs.set_status(run_id, RunStatus.RUNNING)
        await runs.set_item_status(run_id, "C-0001", RunItemStatus.COMPLETED)

        reconciled = await use_case.reconcile_interrupted()
        assert reconciled == (run_id,)

        await use_case.resume(run_id)
        await _wait_for(lambda: runs.is_terminal(run_id))

        assert pipeline.executed == ["C-0002"]
        record = await runs.get(run_id)
        assert record is not None
        assert record.status is RunStatus.COMPLETED


class TestCancel:
    async def test_cancelling_an_inactive_run_is_refused(self) -> None:
        use_case, runs, _ = _use_case()
        run_id = await use_case.start()
        await _wait_for(lambda: runs.is_terminal(run_id))

        with pytest.raises(ConflictError, match="not active"):
            await use_case.cancel(run_id)

    async def test_cancelling_an_unknown_run_is_refused(self) -> None:
        use_case, _, _ = _use_case()

        with pytest.raises(NotFoundError):
            await use_case.cancel(999)

    async def test_a_cancelled_run_leaves_unstarted_items_cancelled(self) -> None:
        use_case, runs, pipeline = _use_case(references=("C-0001", "C-0002", "C-0003"))
        run_id = await use_case.start()
        # Cancel before the background task has had a chance to run at
        # all — the CANCELLING request must survive `_work`'s own first
        # write, not be clobbered by it.
        await use_case.cancel(run_id)
        await _wait_for(lambda: runs.is_terminal(run_id))

        record = await runs.get(run_id)
        assert record is not None
        assert record.status is RunStatus.CANCELLED
        assert pipeline.executed == []


class TestRunLevelFailure:
    async def test_an_error_outside_the_per_item_loop_marks_the_run_failed(self) -> None:
        # Distinct from an item's own failure (TestStart above), which
        # never touches the run's own status at all.
        runs = _BrokenRuns()
        pipeline = _FakePipeline()
        use_case = RunExtractionOverCorpus(
            calls=_FakeCalls(("C-0001",)),
            runs=runs,
            pipeline=pipeline,
            provider_registry=ProviderRegistry(make_settings(llm_provider="ollama"), LlmAuditLog()),
            background_runner=BackgroundRunner(),
            clock=FixedClock(),
        )
        run_id = await runs.create(("C-0001",), provider="ollama", model="m", created_at=_NOW)
        await runs.set_status(run_id, RunStatus.FAILED)  # a resumable starting point
        runs.broken = True

        await use_case.resume(run_id)
        await _wait_for(lambda: runs.is_terminal(run_id))

        record = await runs.get(run_id)
        assert record is not None
        assert record.status is RunStatus.FAILED
        assert pipeline.executed == []


class TestStatus:
    async def test_an_unknown_run_has_no_status(self) -> None:
        use_case, _, _ = _use_case()

        assert await use_case.status(999) is None

    async def test_status_bundles_the_record_and_its_progress(self) -> None:
        use_case, runs, _ = _use_case(references=("C-0001",))
        run_id = await use_case.start()
        await _wait_for(lambda: runs.is_terminal(run_id))

        view = await use_case.status(run_id)

        assert view is not None
        assert view.record.id == run_id
        assert view.progress.total == 1
        assert view.progress.completed == 1


class TestReconcileInterrupted:
    async def test_an_active_run_from_a_previous_process_is_marked_interrupted(self) -> None:
        use_case, runs, _ = _use_case()
        run_id = await runs.create(("C-0001",), provider="ollama", model="m", created_at=_NOW)
        await runs.set_status(run_id, RunStatus.RUNNING)

        reconciled = await use_case.reconcile_interrupted()

        assert reconciled == (run_id,)
        record = await runs.get(run_id)
        assert record is not None
        assert record.status is RunStatus.INTERRUPTED

    async def test_a_completed_run_is_left_alone(self) -> None:
        use_case, runs, _ = _use_case()
        run_id = await use_case.start()
        await _wait_for(lambda: runs.is_terminal(run_id))

        reconciled = await use_case.reconcile_interrupted()

        assert reconciled == ()
