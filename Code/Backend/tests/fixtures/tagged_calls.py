"""Builders for aggregation fixtures, derived from the Call Tag Schema.

`Backend-Stream-B-Measurement.md` §3: write the aggregations against the Call
Tag Schema and "test them against fixtures derived from it". These are those
fixtures — every field name and allowed value comes from the schema sheet,
not from Stream A's output, so a test here stays valid whatever the pipeline
ends up storing.

Defaults are chosen so a call is *unremarkable*: resolved, no complaint, no
signals, no escalation. A test then sets only the field it is about, which
keeps each one readable and means a new schema field cannot silently change
what an existing test is asserting.
"""

from __future__ import annotations

from datetime import date, timedelta

from domain.aggregation.call_tags import BrokerFacts, CallContext, CallTags, EmployerFacts, Window
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
from domain.value_objects.signal_type import SignalType

#: The corpus's own 12-week window (batch 1: 6 Jul to 25 Sep 2026).
WINDOW_START = date(2026, 7, 6)
WINDOW = Window(start=WINDOW_START, end=date(2026, 9, 28))


def day(offset: int) -> date:
    """A date `offset` days into the window."""
    return WINDOW_START + timedelta(days=offset)


def call(
    reference: str,
    *,
    on: date | None = None,
    employer_ref: str | None = "EMP-01",
    broker_of_record_ref: str | None = "BRK-01",
    agent_ref: str | None = "AG-01",
    caller_ref: str | None = None,
    outcome: Outcome | None = Outcome.RESOLVED,
    category: Category | None = Category.CLAIMS_AND_EOB,
    product_lines: tuple[ProductLine, ...] = (ProductLine.DENTAL,),
    complaint_to: ComplaintAttribution | None = None,
    signals: frozenset[SignalType] = frozenset(),
    escalation: Escalation | None = None,
    control_exceptions: frozenset[ControlExceptionType] = frozenset(),
    knowledge_failure_rule: str | None = None,
    intent: IntentType | None = None,
    quality_score: int | None = None,
    aht_seconds: int | None = 400,
    broker_named: str | None = None,
    broker_sentiment: BrokerSentiment = BrokerSentiment.ADVERSE,
    process_gap_change: str | None = None,
    touchpoint: str | None = None,
) -> CallContext:
    """One tagged call, with everything unremarkable unless stated."""
    return CallContext(
        tags=CallTags(
            reference=reference,
            outcome=outcome,
            category=category,
            product_lines=product_lines,
            complaint=(
                Complaint(present=True, attributed_to=complaint_to)
                if complaint_to is not None
                else Complaint(present=False)
            ),
            signals=signals,
            escalation=escalation,
            control_exceptions=control_exceptions,
            knowledge_failure=(
                KnowledgeFailure(present=True, rule_id=knowledge_failure_rule)
                if knowledge_failure_rule
                else KnowledgeFailure(present=False)
            ),
            intent=(
                (IntentStatement(type=intent, quote="we're going out to bid", turn_seq=14),)
                if intent is not None
                else ()
            ),
            quality_score=quality_score,
            aht_seconds=aht_seconds,
            caller_ref=caller_ref,
            broker_named_aloud=(
                BrokerNamedAloud(present=True, broker_ref=broker_named, sentiment=broker_sentiment)
                if broker_named
                else BrokerNamedAloud(present=False)
            ),
            process_gap=(
                ProcessGap(
                    present=True,
                    gap_type="missing_detail",
                    touchpoint=touchpoint,
                    proposed_change=process_gap_change,
                    raised_by=RaisedBy.CALLER,
                    status=ProcessGapStatus.UNVALIDATED,
                )
                if process_gap_change
                else ProcessGap(present=False)
            ),
            touchpoint=touchpoint,
        ),
        occurred_on=on or WINDOW_START,
        employer_ref=employer_ref,
        broker_of_record_ref=broker_of_record_ref,
        agent_ref=agent_ref,
    )


def calls(count: int, *, prefix: str = "C", **kwargs: object) -> tuple[CallContext, ...]:
    """`count` interchangeable calls, for getting a figure over its min n."""
    return tuple(call(f"{prefix}-{index:04d}", **kwargs) for index in range(1, count + 1))  # type: ignore[arg-type]


def employer(
    reference: str = "EMP-01",
    *,
    enrolled: int = 100,
    region: str = "North",
    broker_ref: str = "BRK-01",
    renewal_month: str = "January",
) -> EmployerFacts:
    return EmployerFacts(
        reference=reference,
        name=f"Employer {reference}",
        enrolled=enrolled,
        region=region,
        industry="Manufacturing",
        renewal_month=renewal_month,
        broker_ref=broker_ref,
        annual_premium=480.0 * enrolled,
    )


def broker(
    reference: str = "BRK-01", *, groups_in_book: int = 5, book_lives: int = 400
) -> BrokerFacts:
    return BrokerFacts(
        reference=reference,
        name=f"Broker {reference}",
        agency=f"Agency {reference}",
        region="North",
        groups_in_book=groups_in_book,
        book_lives=book_lives,
    )
