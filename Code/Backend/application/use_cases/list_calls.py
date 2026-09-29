"""The calls workbench — one row per call, searched, sorted and paged.

## Why this filters in memory rather than in SQL

Every other screen's filters are `InsightFilters`, applied to `CallContext`
in `domain/aggregation/filters.py`. Writing a second implementation in SQL
would mean two definitions of what `escalated=true` selects, and the day
they disagree the calls table will contradict the figure it is supposed to
explain — which is precisely the thing this screen exists to prevent.

So the corpus slice is loaded through the same reader as every figure, and
search, sort and paging happen over the result. One definition, one answer.

**The cost, stated plainly.** The whole filtered slice is materialised per
request. At batch-1 volume that is about a hundred calls and nobody will
notice. It stops being reasonable somewhere in the low tens of thousands,
and the fix at that point is a paged read on `SqlInsightsSource` **plus**
moving `InsightFilters` behind an interface both implementations satisfy —
not a second filter written in SQL beside this one.

## Sorting is total, or pages lose rows

Sorting on a column with ties — outcome, category, a null date — leaves the
order of tied rows to the sort's own stability across two separate
requests. Page 2 can then repeat a row from page 1 and drop another
entirely, and a reader exporting page by page gets a corpus with holes in
it. Every sort here therefore ends in the call reference, which is unique.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING

from application.use_cases.read_insights import InsightsRequest
from domain.errors import ValidationError

if TYPE_CHECKING:
    from application.ports.insights_source import CorpusSlice
    from application.use_cases.read_insights import InsightsReader, ScopedCorpus
    from domain.aggregation.call_tags import (
        AgentFacts,
        BrokerFacts,
        CallContext,
        CallerFacts,
        EmployerFacts,
    )


#: The most rows one request may return. The frontend offers 25, 50 and
#: 100; this is the ceiling the server enforces regardless, so a crafted
#: `perPage=100000` cannot turn the workbench into an export endpoint that
#: nobody rate-limits.
MAX_PER_PAGE = 100
DEFAULT_PER_PAGE = 25


class Sort(str, Enum):
    """The six sortable columns, named on the wire rather than by index.

    Column indices would silently re-point at a different column the first
    time the table's column order changed.
    """

    DATE = "date"
    EMPLOYER = "employer"
    AGENT = "agent"
    CATEGORY = "category"
    OUTCOME = "outcome"
    QUALITY = "quality"


@dataclass(frozen=True)
class CallRowView:
    """One call, flattened for a table row and for a CSV line.

    Deliberately not `CallContext`: that is the aggregation input and has
    no employer name, no broker agency and no region, because a figure must
    not be able to read them. A table row needs all three, so the joining
    happens here and the aggregation input stays as narrow as it was.
    """

    reference: str
    occurred_on: date
    employer_ref: str | None
    employer_name: str | None
    #: Who rang, joined from reference data. `None` where the reference
    #: matches nobody, which is a gap in reference data rather than an
    #: anonymous caller, and is why the row keeps the reference too.
    caller_ref: str | None
    caller_name: str | None
    caller_kind: str | None
    broker_ref: str | None
    broker_agency: str | None
    region: str | None
    agent_ref: str | None
    #: From the Agent Roster. `None` for an agent the roster does not know,
    #: which is a gap in reference data rather than an unattributed call --
    #: the reference is kept beside it for exactly that case.
    agent_name: str | None
    category: str | None
    product_lines: tuple[str, ...]
    touchpoint: str | None
    outcome: str | None
    quality_score: int | None
    aht_seconds: int | None
    complaint: bool
    complaint_against: str | None
    signals: tuple[str, ...]
    escalation_triggered: bool
    escalation_handled: bool
    control_exceptions: tuple[str, ...]
    knowledge_failure: bool
    intents: tuple[str, ...]

    @property
    def haystack(self) -> str:
        """What free-text search looks at, lowercased once per row.

        Names and references only — never transcript text. Search runs over
        the whole filtered slice on every keystroke, and a substring match
        against full transcripts would both be slow and quietly turn this
        box into a way to fish for phrases in member conversations.
        """
        parts = (
            self.reference,
            self.employer_name or "",
            self.employer_ref or "",
            self.broker_agency or "",
            self.agent_ref or "",
            self.category or "",
            self.outcome or "",
            self.touchpoint or "",
        )
        return " ".join(parts).lower()


@dataclass(frozen=True)
class CallsPage:
    """One page, and everything needed to say what it is a page of."""

    rows: tuple[CallRowView, ...]
    #: Rows matching the filters and the search, before paging. The count a
    #: reader needs to know whether page 3 of 3 is the end of the evidence
    #: or the end of the page size. Distinct from `scope.filtered`, which
    #: has not had the search applied to it.
    total: int
    page: int
    per_page: int
    #: The same scope every other screen carries, so this one renders the
    #: filter bar's count and the corpus caveats through the shared frame
    #: rather than through a second, nearly-identical set of fields.
    scope: ScopedCorpus

    @property
    def pages(self) -> int:
        if self.per_page <= 0:
            return 0
        return max(1, -(-self.total // self.per_page))


@dataclass(frozen=True)
class CallsQuery:
    """What one request to the workbench asks for."""

    request: InsightsRequest
    q: str = ""
    sort: Sort = Sort.DATE
    descending: bool = True
    page: int = 1
    per_page: int = DEFAULT_PER_PAGE
    #: Specific calls by reference, for "download selected".
    #:
    #: A filter rather than a client-side slice, so the export stays a
    #: server projection (checkpoint I2). Building the file in the browser
    #: from the selected rows would put a second column list in the
    #: frontend, and the file a reader mails out would come from different
    #: code than the Download-all button's.
    #:
    #: Empty means no narrowing, like every other filter here. Applied
    #: *after* the corpus filters, so selecting a call and then narrowing
    #: the period cannot resurrect a call the period excluded.
    references: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValidationError(
                "Pages start at 1.",
                detail=f"page={self.page} is not a page.",
            )
        if self.per_page < 1 or self.per_page > MAX_PER_PAGE:
            raise ValidationError(
                f"perPage must be between 1 and {MAX_PER_PAGE}.",
                detail=f"perPage={self.per_page} was asked for.",
            )


class ListCalls:
    """The filtered corpus as table rows."""

    def __init__(self, reader: InsightsReader) -> None:
        self._reader = reader

    async def execute(self, query: CallsQuery) -> CallsPage:
        scope = await self._reader.scope(query.request)
        rows = tuple(_row(call, scope.corpus) for call in scope.filtered.calls)
        if query.references:
            rows = tuple(row for row in rows if row.reference in query.references)
        matching = _search(rows, query.q)
        ordered = _sorted(matching, query.sort, query.descending)
        start = (query.page - 1) * query.per_page
        return CallsPage(
            rows=ordered[start : start + query.per_page],
            total=len(ordered),
            page=query.page,
            per_page=query.per_page,
            scope=scope,
        )


def _search(rows: Sequence[CallRowView], q: str) -> tuple[CallRowView, ...]:
    """Every whitespace-separated term must match, in any field.

    AND rather than OR: typing two words to narrow a list and getting a
    longer one is the opposite of what the box appears to do.
    """
    terms = q.lower().split()
    if not terms:
        return tuple(rows)
    return tuple(row for row in rows if all(term in row.haystack for term in terms))


#: How each sortable column reads a row. Nulls are pushed to the end under
#: either direction by sorting on a `(is_null, value)` pair — a null score
#: is "not recorded", and it should not lead the table as the worst score
#: nor as the best depending on which way the arrow points.
_KEYS: dict[Sort, Callable[[CallRowView], tuple[object, ...]]] = {
    Sort.DATE: lambda row: (row.occurred_on.toordinal(),),
    Sort.EMPLOYER: lambda row: (row.employer_name is None, (row.employer_name or "").lower()),
    Sort.AGENT: lambda row: (row.agent_ref is None, (row.agent_ref or "").lower()),
    Sort.CATEGORY: lambda row: (row.category is None, (row.category or "").lower()),
    Sort.OUTCOME: lambda row: (row.outcome is None, (row.outcome or "").lower()),
    Sort.QUALITY: lambda row: (row.quality_score is None, row.quality_score or 0),
}


def _sorted(rows: Sequence[CallRowView], sort: Sort, descending: bool) -> tuple[CallRowView, ...]:
    key = _KEYS[sort]

    def ordering(row: CallRowView) -> tuple[object, ...]:
        # The reference always last, so the order is total. Without it two
        # calls with the same date can swap between requests and a reader
        # paging through loses one row and sees another twice.
        return (*key(row), row.reference)

    ordered = sorted(rows, key=ordering, reverse=descending)
    if descending:
        # Reversing put the null group first again, and pushed the
        # tie-break into reverse alphabetical order. Re-sorting the nulls
        # out and appending them keeps "not recorded" at the end both ways.
        present = [row for row in ordered if not key(row)[0]]
        missing = sorted((row for row in ordered if key(row)[0]), key=lambda row: row.reference)
        ordered = present + missing
    return tuple(ordered)


def _row(call: CallContext, corpus: CorpusSlice) -> CallRowView:
    employer = _employer(corpus.employers, call.employer_ref)
    broker = _broker(corpus.brokers, call.broker_of_record_ref)
    tags = call.tags
    caller = _caller(corpus.callers, tags.caller_ref)
    complaint = tags.complaint
    escalation = tags.escalation
    return CallRowView(
        reference=call.reference,
        occurred_on=call.occurred_on,
        employer_ref=call.employer_ref,
        employer_name=employer.name if employer is not None else None,
        caller_ref=tags.caller_ref,
        caller_name=caller.name if caller is not None else None,
        caller_kind=caller.kind if caller is not None else None,
        broker_ref=call.broker_of_record_ref,
        broker_agency=broker.agency if broker is not None else None,
        region=employer.region if employer is not None else None,
        agent_ref=call.agent_ref,
        agent_name=_agent_name(corpus.agents, call.agent_ref),
        category=tags.category.value if tags.category is not None else None,
        product_lines=tuple(line.value for line in tags.product_lines),
        touchpoint=tags.touchpoint,
        outcome=tags.outcome.value if tags.outcome is not None else None,
        quality_score=tags.quality_score,
        aht_seconds=tags.aht_seconds,
        complaint=complaint is not None and complaint.present,
        complaint_against=(
            complaint.attributed_to.value
            if complaint is not None and complaint.attributed_to is not None
            else None
        ),
        signals=tuple(sorted(signal.value for signal in tags.signals)),
        escalation_triggered=escalation is not None and escalation.triggered,
        escalation_handled=escalation is not None and escalation.handled,
        control_exceptions=tuple(sorted(item.value for item in tags.control_exceptions)),
        knowledge_failure=tags.knowledge_failure is not None and tags.knowledge_failure.present,
        intents=tuple(statement.type.value for statement in tags.intent),
    )


def _agent_name(agents: Sequence[AgentFacts], ref: str | None) -> str | None:
    if ref is None:
        return None
    return next((agent.name for agent in agents if agent.reference == ref), None)


def _caller(callers: Sequence[CallerFacts], ref: str | None) -> CallerFacts | None:
    if ref is None:
        return None
    return next((caller for caller in callers if caller.reference == ref), None)


def _employer(employers: Sequence[EmployerFacts], ref: str | None) -> EmployerFacts | None:
    if ref is None:
        return None
    return next((item for item in employers if item.reference == ref), None)


def _broker(brokers: Sequence[BrokerFacts], ref: str | None) -> BrokerFacts | None:
    if ref is None:
        return None
    return next((item for item in brokers if item.reference == ref), None)
