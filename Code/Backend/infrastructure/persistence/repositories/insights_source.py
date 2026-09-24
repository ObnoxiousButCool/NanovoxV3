"""SQLAlchemy implementation of `InsightsSource`.

Reads `calls`, `call_extractions` and `signals` back into the Call Tag
Schema's shape, and reference data into the narrow `EmployerFacts` and
`BrokerFacts` joins the aggregations are allowed to see.

## The joins stay narrow on purpose

`EmployerRow` carries two columns this mapping deliberately leaves behind:
the churn-profile label the corpus was generated from, and `eligible`, which
is rule P-33's denominator rather than the peer-band one. Neither is mapped.
`domain/aggregation/call_tags.py` explains why in full; the short version is
that an account scored on the label it was generated from is scored on its
own answer, and the surest way not to read a column is never to select it.

That label is described here rather than named.
`tests/unit/test_no_circular_scoring.py` fails on the literal string
anywhere outside storage, and wanting to write a clearer docstring is not a
good enough reason to widen its allow-list — this file is precisely the kind
the guard exists to police.

## Eager loading, and why it is spelled out

`CallRow.employer` is already `lazy="selectin"`, but `EmployerRow.broker` is
not, and reaching a broker of record means traversing both. Outside an
awaited context the second hop raises `MissingGreenlet`, so the load path is
stated in the query rather than left to relationship defaults — which are a
property of the table module and could be tuned for a different caller
without anyone here noticing.

## What it will not invent

An outer join, not an inner one, so that calls without an extraction row are
seen and reported rather than quietly missing. Same for calls with no date.
Both are returned by reference in `CorpusSlice`; see that port's docstring
for why each is fatal to a figure rather than merely untidy.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from enum import Enum
from typing import TYPE_CHECKING, TypeVar

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from application.ports.insights_source import CorpusQuery, CorpusSlice, InsightsSource
from domain.aggregation.call_tags import (
    BrokerFacts,
    CallContext,
    CallTags,
    EmployerFacts,
    book_lives_for,
)
from domain.aggregation.rules import RuleFacts
from domain.value_objects.broker_named_aloud import BrokerNamedAloud
from domain.value_objects.broker_sentiment import BrokerSentiment
from domain.value_objects.category import Category
from domain.value_objects.complaint import Complaint
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.escalation import Escalation
from domain.value_objects.intent_statement import IntentStatement
from domain.value_objects.intent_type import IntentType
from domain.value_objects.knowledge_failure import KnowledgeFailure
from domain.value_objects.outcome import Outcome
from domain.value_objects.process_gap import ProcessGap, ProcessGapStatus, RaisedBy
from domain.value_objects.product_line import ProductLine
from domain.value_objects.rule_confidence import RuleConfidence
from domain.value_objects.rule_layer import RuleLayer
from domain.value_objects.signal_type import SignalType
from infrastructure.persistence.tables import (
    BrokerRow,
    CallExtractionRow,
    CallRow,
    EmployerRow,
    RuleRow,
    SignalRow,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_EnumT = TypeVar("_EnumT", bound=Enum)

#: Call Tag Schema fields no included call carries a value for.
#:
#: Computed per request rather than fixed, because it is a fact about the
#: rows that were read and not about the pipeline's capabilities. Stream A
#: now stores `control_exceptions` (schema field 7, metric 7's only input),
#: and its column is nullable: `[]` means L1 ran and found none, `NULL`
#: means it was never recorded. `CallTags` has one empty set for both, so a
#: call with `NULL` would read as a clean compliance record — a claim
#: nobody made. Such a call puts the field in this list instead.


class SqlInsightsSource(InsightsSource):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def load(self, query: CorpusQuery) -> CorpusSlice:
        async with self._session_factory() as session:
            employers, brokers = await self._reference_data(session)
            rules = await self._rules(session)
            calls, undated, unanalysed, unavailable = await self._calls(session, query)

        return CorpusSlice(
            calls=calls,
            employers=employers,
            brokers=brokers,
            rules=rules,
            undated=undated,
            unanalysed=unanalysed,
            unavailable_fields=unavailable,
        )

    async def _reference_data(
        self, session: AsyncSession
    ) -> tuple[tuple[EmployerFacts, ...], tuple[BrokerFacts, ...]]:
        """Every employer and broker, not only those with calls.

        `book_lives_for` is explicit that a broker's book is what reference
        data says it is; computing it from the employers that happened to
        call would make insight 10's 150-lives floor move with call volume
        and defeat the point of having a floor.
        """
        employer_rows = (
            (await session.execute(select(EmployerRow).options(selectinload(EmployerRow.broker))))
            .scalars()
            .all()
        )
        employers = tuple(_employer_facts(row) for row in employer_rows)

        broker_rows = (await session.execute(select(BrokerRow))).scalars().all()
        brokers = tuple(
            BrokerFacts(
                reference=row.reference,
                name=row.name,
                agency=row.agency,
                region=row.region,
                groups_in_book=row.groups_in_book,
                book_lives=book_lives_for(row.reference, employers),
            )
            for row in broker_rows
        )
        return employers, brokers

    async def _rules(self, session: AsyncSession) -> tuple[RuleFacts, ...]:
        """Every rule, in reference order.

        All of them, not only the cited ones: the rewrite list ranks over
        the whole rulebook, and a rule nobody got wrong is a different
        thing from a rule that does not exist.
        """
        rows = (await session.execute(select(RuleRow).order_by(RuleRow.reference))).scalars().all()
        return tuple(
            RuleFacts(
                reference=row.reference,
                layer=RuleLayer(row.layer),
                area=row.area,
                confidence=RuleConfidence(row.confidence),
                commonly_confused_with=row.commonly_confused_with,
            )
            for row in rows
        )

    async def _calls(
        self, session: AsyncSession, query: CorpusQuery
    ) -> tuple[tuple[CallContext, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        statement = (
            select(CallRow, CallExtractionRow)
            .outerjoin(CallExtractionRow, CallExtractionRow.call_id == CallRow.id)
            .options(selectinload(CallRow.employer).selectinload(EmployerRow.broker))
            .order_by(CallRow.reference)
        )
        if query.sources:
            statement = statement.where(
                CallRow.source.in_(sorted(source.value for source in query.sources))
            )
        # Bounds are made UTC-aware to match what is stored: `occurred_at`
        # holds tz-aware timestamps, and a naive bound compares against a
        # `timestamptz` — which SQLite tolerates and Postgres, the
        # deployment target, refuses outright.
        #
        # Undated calls survive both bounds. In SQL a comparison against NULL
        # is neither true nor false, so a plain `occurred_at >= since` would
        # drop them from the result set entirely — and the one thing this
        # port must not do is lose an undated call quietly, since being
        # reported is the whole of what happens to it.
        if query.since is not None:
            statement = statement.where(
                or_(
                    CallRow.occurred_at.is_(None),
                    CallRow.occurred_at
                    >= datetime.combine(query.since, time.min, tzinfo=timezone.utc),
                )
            )
        if query.until is not None:
            statement = statement.where(
                or_(
                    CallRow.occurred_at.is_(None),
                    CallRow.occurred_at
                    <= datetime.combine(query.until, time.max, tzinfo=timezone.utc),
                )
            )

        rows = list((await session.execute(statement)).all())
        analysed = [(call, extraction) for call, extraction in rows if extraction is not None]
        signals = await self._signals(session, [call.id for call, _ in analysed])

        calls: list[CallContext] = []
        undated: list[str] = []
        unrecorded_exceptions = False
        unanalysed = tuple(call.reference for call, extraction in rows if extraction is None)
        for call, extraction in analysed:
            if call.occurred_at is None:
                undated.append(call.reference)
                continue
            unrecorded_exceptions = unrecorded_exceptions or extraction.control_exceptions is None
            calls.append(
                CallContext(
                    tags=_tags(call, extraction, signals.get(call.id, frozenset())),
                    occurred_on=call.occurred_at.date(),
                    employer_ref=call.employer.reference if call.employer else None,
                    broker_of_record_ref=(
                        call.employer.broker.reference if call.employer else None
                    ),
                    agent_ref=call.agent_ref or None,
                )
            )
        unavailable = ("control_exceptions",) if unrecorded_exceptions else ()
        return tuple(calls), tuple(undated), unanalysed, unavailable

    async def _signals(
        self, session: AsyncSession, call_ids: list[int]
    ) -> dict[int, frozenset[SignalType]]:
        """Distinct signal *types* per call, never occurrences.

        The Signal Taxonomy sheet is explicit that density counts distinct
        types, and one call can raise the same type twice with two quotes.
        Collapsing to a set here is what keeps that from being counted as
        two.
        """
        if not call_ids:
            return {}
        rows = (
            (await session.execute(select(SignalRow).where(SignalRow.call_id.in_(call_ids))))
            .scalars()
            .all()
        )
        raised: dict[int, set[SignalType]] = {}
        for row in rows:
            raised.setdefault(row.call_id, set()).add(SignalType(row.type))
        return {call_id: frozenset(types) for call_id, types in raised.items()}


def _employer_facts(row: EmployerRow) -> EmployerFacts:
    return EmployerFacts(
        reference=row.reference,
        name=row.name,
        enrolled=row.enrolled,
        region=row.region,
        industry=row.industry,
        renewal_month=row.renewal_month,
        broker_ref=row.broker.reference,
        annual_premium=row.annual_premium,
        annual_fee=row.annual_fee,
    )


def _tags(call: CallRow, extraction: CallExtractionRow, signals: frozenset[SignalType]) -> CallTags:
    """One stored call as the schema's sixteen fields.

    A `NULL` `control_exceptions` column becomes an empty set here, because
    `CallTags` has no third state — `CorpusSlice.unavailable_fields` is what
    stops that emptiness being read as a clean compliance record.
    """
    return CallTags(
        reference=call.reference,
        outcome=_enum(Outcome, extraction.outcome),
        category=_enum(Category, extraction.category),
        product_lines=tuple(ProductLine(line) for line in (extraction.product_lines or ())),
        complaint=_complaint(extraction),
        signals=signals,
        escalation=_escalation(extraction),
        control_exceptions=frozenset(
            ControlExceptionType(code) for code in (extraction.control_exceptions or ())
        ),
        knowledge_failure=_knowledge_failure(extraction),
        intent=_intent(extraction),
        quality_score=extraction.quality_score,
        aht_seconds=call.aht_seconds,
        caller_ref=call.caller_ref or None,
        broker_named_aloud=_broker_named_aloud(extraction),
        process_gap=_process_gap(extraction),
        touchpoint=extraction.touchpoint,
    )


def _complaint(extraction: CallExtractionRow) -> Complaint | None:
    """`None` when L2 has not answered, which is not the same as no complaint.

    A stored `present=True` with no attribution violates `Complaint`'s own
    invariant and raises here rather than being smoothed to `None`. Smoothing
    would file the call under "not extracted", where it would disappear from
    the counts without appearing in `unanalysed` — a stored row breaking a
    domain rule is a bug worth hearing about, not one worth hiding.
    """
    if extraction.complaint_present is None:
        return None
    return Complaint(
        present=extraction.complaint_present,
        attributed_to=_enum(ComplaintAttribution, extraction.complaint_attributed_to),
    )


def _escalation(extraction: CallExtractionRow) -> Escalation | None:
    if extraction.escalation_triggered is None:
        return None
    return Escalation(
        triggered=extraction.escalation_triggered,
        trigger_type=extraction.escalation_trigger_type,
        requested_by_caller=bool(extraction.escalation_requested_by_caller),
        handled=bool(extraction.escalation_handled),
    )


def _knowledge_failure(extraction: CallExtractionRow) -> KnowledgeFailure | None:
    if extraction.knowledge_failure_present is None:
        return None
    return KnowledgeFailure(
        present=extraction.knowledge_failure_present,
        rule_id=extraction.knowledge_failure_rule_id,
        correct_statement=extraction.knowledge_failure_correct_statement,
    )


def _broker_named_aloud(extraction: CallExtractionRow) -> BrokerNamedAloud | None:
    if extraction.broker_named_aloud_present is None:
        return None
    return BrokerNamedAloud(
        present=extraction.broker_named_aloud_present,
        broker_ref=extraction.broker_named_aloud_broker_ref,
        sentiment=_enum(BrokerSentiment, extraction.broker_named_aloud_sentiment),
        matches_employer_of_record=extraction.broker_named_aloud_matches_employer_of_record,
    )


def _process_gap(extraction: CallExtractionRow) -> ProcessGap | None:
    if extraction.process_gap_present is None:
        return None
    return ProcessGap(
        present=extraction.process_gap_present,
        gap_type=extraction.process_gap_gap_type,
        touchpoint=extraction.process_gap_touchpoint,
        proposed_change=extraction.process_gap_proposed_change,
        raised_by=_enum(RaisedBy, extraction.process_gap_raised_by),
        status=_enum(ProcessGapStatus, extraction.process_gap_status),
    )


def _intent(extraction: CallExtractionRow) -> tuple[IntentStatement, ...]:
    return tuple(
        IntentStatement(
            type=IntentType(str(item["type"])),
            quote=str(item["quote"]),
            turn_seq=int(item["turn_seq"]),
        )
        for item in (extraction.intent or ())
    )


def _enum(kind: type[_EnumT], value: str | None) -> _EnumT | None:
    """A stored enum value, or `None` when the column is null.

    Deliberately not forgiving of an unrecognised value: a category the
    vocabulary no longer contains means the taxonomy moved under stored
    data, and a figure computed as though those calls were uncategorised
    would be quietly wrong for as long as nobody looked.
    """
    return None if value is None else kind(value)
