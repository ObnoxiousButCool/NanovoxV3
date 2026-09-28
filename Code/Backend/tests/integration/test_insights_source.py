"""`SqlInsightsSource` against a real database.

Two kinds of test here. The first maps stored rows back into the Call Tag
Schema and checks the values survive the round trip. The second is the one
that matters more: a call that cannot be measured — no date, no extraction —
must leave the slice *and* be named, because a call that vanishes silently
takes a denominator with it.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.insights_source import CorpusQuery
from domain.value_objects.call_source import CallSource
from domain.value_objects.category import Category
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.outcome import Outcome
from domain.value_objects.product_line import ProductLine
from domain.value_objects.signal_type import SignalType
from infrastructure.persistence.repositories.insights_source import SqlInsightsSource
from infrastructure.persistence.tables import (
    BrokerRow,
    CallExtractionRow,
    CallRow,
    EmployerRow,
    SignalRow,
)

pytestmark = pytest.mark.asyncio


def broker(reference: str = "BRK-1", groups: int = 4) -> BrokerRow:
    return BrokerRow(
        reference=reference,
        name=f"Broker {reference}",
        agency="Agency",
        region="West",
        groups_in_book=groups,
        signal_profile="neutral",
    )


def employer(
    reference: str = "EMP-1", *, broker_id: int, enrolled: int = 120, region: str = "West"
) -> EmployerRow:
    return EmployerRow(
        reference=reference,
        name=f"Employer {reference}",
        industry="Retail",
        # Stored on the row, never mapped into EmployerFacts.
        design_churn_profile="AT_RISK",
        eligible=200,
        enrolled=enrolled,
        region=region,
        renewal_month="January",
        broker_id=broker_id,
        dental_sponsorship="voluntary",
        lines_held="dental",
        planned_calls=10,
        planned_member_calls=8,
        planned_employer_calls=2,
        fee_band=3,
        annual_fee=4200,
        annual_premium=98000.0,
        cobra_regime="federal",
    )


def call_row(
    reference: str = "C-0001",
    *,
    employer_id: int | None = None,
    occurred_at: datetime | None = datetime(2025, 3, 1, 10, 0, tzinfo=timezone.utc),
    source: CallSource = CallSource.CORPUS_PDF,
) -> CallRow:
    return CallRow(
        reference=reference,
        source=source.value,
        occurred_at=occurred_at,
        aht_seconds=420,
        caller_type="MEMBER",
        caller_ref="MEM-1",
        agent_ref="AG-1",
        agent_name="Alex",
        resolution_status="RESOLVED",
        resolution_reason=None,
        employer_id=employer_id,
    )


def extraction(call_id: int) -> CallExtractionRow:
    return CallExtractionRow(
        call_id=call_id,
        outcome=Outcome.RESOLVED.value,
        category=Category.CLAIMS_AND_EOB.value,
        product_lines=[ProductLine.DENTAL.value, ProductLine.VISION.value],
        complaint_present=True,
        complaint_attributed_to=ComplaintAttribution.BROKER.value,
        intent=[{"type": "expansion", "quote": "we may add vision", "turn_seq": 7}],
        escalation_triggered=True,
        escalation_requested_by_caller=True,
        escalation_handled=False,
        escalation_trigger_type="supervisor_request",
        broker_named_aloud_present=True,
        broker_named_aloud_broker_ref="BRK-1",
        broker_named_aloud_sentiment="ADVERSE",
        touchpoint="Enrolment",
        quality_score=88,
        knowledge_failure_present=True,
        knowledge_failure_rule_id="P-33",
        process_gap_present=False,
    )


async def seed(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    calls: list[CallRow] | None = None,
    analyse: bool = True,
    signals: list[str] | None = None,
    employers: int = 1,
) -> None:
    async with session_factory() as session, session.begin():
        brk = broker()
        session.add(brk)
        await session.flush()
        employer_ids: list[int] = []
        for index in range(employers):
            emp = employer(f"EMP-{index + 1}", broker_id=brk.id, enrolled=100 + index * 50)
            session.add(emp)
            await session.flush()
            employer_ids.append(emp.id)

        for row in calls or [call_row(employer_id=employer_ids[0])]:
            if row.employer_id is None and employer_ids:
                row.employer_id = employer_ids[0]
            session.add(row)
            await session.flush()
            if analyse:
                session.add(extraction(row.id))
            for signal_type in signals or []:
                session.add(SignalRow(call_id=row.id, type=signal_type, quote="q", turn_seq=1))


class TestMapping:
    async def test_a_stored_call_comes_back_as_the_schemas_fields(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory)

        result = await SqlInsightsSource(session_factory).load(CorpusQuery())

        (context,) = result.calls
        assert context.reference == "C-0001"
        assert context.occurred_on == date(2025, 3, 1)
        assert context.tags.outcome is Outcome.RESOLVED
        assert context.tags.category is Category.CLAIMS_AND_EOB
        assert context.tags.product_lines == (ProductLine.DENTAL, ProductLine.VISION)
        assert context.tags.quality_score == 88
        assert context.tags.aht_seconds == 420
        assert context.tags.touchpoint == "Enrolment"

    async def test_employer_and_broker_of_record_are_joined_not_tagged(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory)

        (context,) = (await SqlInsightsSource(session_factory).load(CorpusQuery())).calls

        assert context.employer_ref == "EMP-1"
        assert context.broker_of_record_ref == "BRK-1"

    async def test_nested_value_objects_survive_the_round_trip(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory)

        (context,) = (await SqlInsightsSource(session_factory).load(CorpusQuery())).calls

        assert context.tags.complaint is not None
        assert context.tags.complaint.attributed_to is ComplaintAttribution.BROKER
        assert context.tags.escalation is not None
        assert context.tags.escalation.handled is False
        assert context.tags.knowledge_failure is not None
        assert context.tags.knowledge_failure.rule_id == "P-33"
        assert context.tags.broker_named_aloud is not None
        assert context.tags.intent[0].turn_seq == 7

    async def test_a_call_with_no_employer_keeps_both_joins_empty(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Null exactly when the join did not resolve — never a guess."""
        await seed(session_factory, calls=[call_row(employer_id=None)])

        async with session_factory() as session, session.begin():
            row = await session.get(CallRow, 1)
            assert row is not None
            row.employer_id = None

        (context,) = (await SqlInsightsSource(session_factory).load(CorpusQuery())).calls

        assert context.employer_ref is None
        assert context.broker_of_record_ref is None


class TestSignals:
    async def test_distinct_types_not_occurrences(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """One call raising the same type twice is one signal, not two."""
        await seed(
            session_factory,
            signals=[
                SignalType.PROCESS_BREAKDOWN.value,
                SignalType.PROCESS_BREAKDOWN.value,
                SignalType.BILLING_DEFECT.value,
            ],
        )

        (context,) = (await SqlInsightsSource(session_factory).load(CorpusQuery())).calls

        assert context.tags.signals == frozenset(
            {SignalType.PROCESS_BREAKDOWN, SignalType.BILLING_DEFECT}
        )

    async def test_a_call_with_no_signals_gets_an_empty_set(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory)

        (context,) = (await SqlInsightsSource(session_factory).load(CorpusQuery())).calls

        assert context.tags.signals == frozenset()


class TestWhatItRefusesToInvent:
    async def test_an_undated_call_is_excluded_and_named(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(
            session_factory,
            calls=[call_row("C-0001"), call_row("C-0002", occurred_at=None)],
        )

        result = await SqlInsightsSource(session_factory).load(CorpusQuery())

        assert [c.reference for c in result.calls] == ["C-0001"]
        assert result.undated == ("C-0002",)

    async def test_an_unanalysed_call_is_excluded_and_named(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory, analyse=False)

        result = await SqlInsightsSource(session_factory).load(CorpusQuery())

        assert result.calls == ()
        assert result.unanalysed == ("C-0001",)

    async def test_undated_calls_survive_a_date_bound(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """A NULL date is neither inside nor outside a window.

        Comparing it in SQL would drop the row, and being reported is the
        entire fate of an undated call.
        """
        await seed(
            session_factory,
            calls=[call_row("C-0001"), call_row("C-0002", occurred_at=None)],
        )

        result = await SqlInsightsSource(session_factory).load(
            CorpusQuery(since=date(2025, 1, 1), until=date(2025, 12, 31))
        )

        assert result.undated == ("C-0002",)

    async def test_an_unrecorded_control_exception_is_reported_not_read_as_clean(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """NULL is not an empty list.

        `CallTags` has one empty set for both "L1 ran and found none" and
        "never recorded", so the slice has to say which this was. Otherwise
        an unrecorded call reads as a clean compliance record.
        """
        await seed(session_factory)

        result = await SqlInsightsSource(session_factory).load(CorpusQuery())

        (context,) = result.calls
        assert context.tags.control_exceptions == frozenset()
        assert "control_exceptions" in result.unavailable_fields

    async def test_control_exceptions_are_read_when_the_pipeline_recorded_them(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory, analyse=False)
        async with session_factory() as session, session.begin():
            session.add(
                CallExtractionRow(
                    call_id=1,
                    outcome=Outcome.RESOLVED.value,
                    control_exceptions=[ControlExceptionType.NO_RECORDING_DISCLOSURE.value],
                )
            )

        result = await SqlInsightsSource(session_factory).load(CorpusQuery())

        (context,) = result.calls
        assert context.tags.control_exceptions == frozenset(
            {ControlExceptionType.NO_RECORDING_DISCLOSURE}
        )
        assert result.unavailable_fields == ()

    async def test_an_empty_recorded_list_is_a_finding_not_a_gap(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """L1 ran and found nothing. That is an answer, so no caveat."""
        await seed(session_factory, analyse=False)
        async with session_factory() as session, session.begin():
            session.add(
                CallExtractionRow(call_id=1, outcome=Outcome.RESOLVED.value, control_exceptions=[])
            )

        result = await SqlInsightsSource(session_factory).load(CorpusQuery())

        assert result.calls[0].tags.control_exceptions == frozenset()
        assert result.unavailable_fields == ()

    async def test_caveats_explain_every_exclusion(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(
            session_factory,
            calls=[call_row("C-0001"), call_row("C-0002", occurred_at=None)],
        )

        caveats = " ".join((await SqlInsightsSource(session_factory).load(CorpusQuery())).caveats())

        assert "no date" in caveats
        assert "not recorded for every call" in caveats

    async def test_excluded_counts_both_kinds(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(
            session_factory,
            calls=[call_row("C-0001", occurred_at=None)],
            analyse=True,
        )

        assert (await SqlInsightsSource(session_factory).load(CorpusQuery())).excluded == 1


class TestScope:
    async def test_source_narrows_the_corpus(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(
            session_factory,
            calls=[
                call_row("C-0001", source=CallSource.CORPUS_PDF),
                call_row("C-0002", source=CallSource.PASTED),
            ],
        )

        result = await SqlInsightsSource(session_factory).load(
            CorpusQuery(sources=frozenset({CallSource.CORPUS_PDF}))
        )

        assert [c.reference for c in result.calls] == ["C-0001"]

    async def test_no_source_means_every_source(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(
            session_factory,
            calls=[
                call_row("C-0001", source=CallSource.CORPUS_PDF),
                call_row("C-0002", source=CallSource.PASTED),
            ],
        )

        result = await SqlInsightsSource(session_factory).load(CorpusQuery())

        assert len(result.calls) == 2

    async def test_date_bounds_are_inclusive(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory)

        result = await SqlInsightsSource(session_factory).load(
            CorpusQuery(since=date(2025, 3, 1), until=date(2025, 3, 1))
        )

        assert len(result.calls) == 1


class TestReferenceData:
    async def test_every_employer_is_returned_not_only_callers(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Peer denominators must not move with call volume."""
        await seed(session_factory, employers=3)

        result = await SqlInsightsSource(session_factory).load(CorpusQuery())

        assert len(result.calls) == 1
        assert len(result.employers) == 3

    async def test_book_lives_sums_the_whole_book(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory, employers=3)

        result = await SqlInsightsSource(session_factory).load(CorpusQuery())

        (brk,) = result.brokers
        assert brk.book_lives == 100 + 150 + 200
        assert brk.groups_in_book == 4

    async def test_the_churn_profile_is_not_on_the_facts_at_all(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Structurally out of reach, not merely unread.

        This used to assert `eligible` was absent too, as a stand-in for the
        port being narrow in general. That conflated two different rules.
        Narrowness is a design preference and `account_stakes` has since
        needed the reference block, so those fields are carried; the churn
        profile is a principle, and it is the one this test is about.
        """
        await seed(session_factory)

        result = await SqlInsightsSource(session_factory).load(CorpusQuery())
        facts = result.employers[0]

        assert not hasattr(facts, "design_churn_profile")
        # The reference fields the stakes read, carried deliberately, so a
        # future reader can see the line was moved on purpose and where.
        assert facts.eligible == 200
        assert facts.lines_held == "dental"


class TestEmptyDatabase:
    async def test_an_empty_corpus_is_an_answer_not_an_error(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        result = await SqlInsightsSource(session_factory).load(CorpusQuery())

        assert result.calls == ()
        assert result.employers == ()
        assert result.excluded == 0


class TestPartiallyAnalysed:
    """L2 has run, L3 and L4 have not.

    A real state, not a hypothetical: the layers land separately and a
    re-run can stop between them. Every unanswered field must come back
    `None`, because the alternative — `present=False` — is the pipeline
    claiming it looked and found nothing.
    """

    async def test_unanswered_fields_are_none_not_negative(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory, analyse=False)
        async with session_factory() as session, session.begin():
            session.add(
                CallExtractionRow(
                    call_id=1,
                    outcome=Outcome.RESOLVED.value,
                    category=Category.CLAIMS_AND_EOB.value,
                )
            )

        (context,) = (await SqlInsightsSource(session_factory).load(CorpusQuery())).calls

        assert context.tags.outcome is Outcome.RESOLVED
        assert context.tags.complaint is None
        assert context.tags.escalation is None
        assert context.tags.knowledge_failure is None
        assert context.tags.broker_named_aloud is None
        assert context.tags.process_gap is None

    async def test_an_absent_product_line_list_is_empty_not_missing(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory, analyse=False)
        async with session_factory() as session, session.begin():
            session.add(CallExtractionRow(call_id=1, outcome=Outcome.RESOLVED.value))

        (context,) = (await SqlInsightsSource(session_factory).load(CorpusQuery())).calls

        assert context.tags.product_lines == ()
        assert context.tags.intent == ()


class TestCaveats:
    async def test_unanalysed_calls_get_their_own_sentence(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory, analyse=False)

        caveats = " ".join((await SqlInsightsSource(session_factory).load(CorpusQuery())).caveats())

        assert "have not been analysed" in caveats

    async def test_a_corpus_with_nothing_to_report_carries_no_caveats(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """A caveat printed every time stops being read."""
        await seed(session_factory, analyse=False)
        async with session_factory() as session, session.begin():
            session.add(
                CallExtractionRow(call_id=1, outcome=Outcome.RESOLVED.value, control_exceptions=[])
            )

        caveats = (await SqlInsightsSource(session_factory).load(CorpusQuery())).caveats()

        assert caveats == ()
