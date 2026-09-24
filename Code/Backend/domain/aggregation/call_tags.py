"""The sixteen Call Tag Schema fields, as the aggregations read them.

The schema sheet states the contract this module exists to honour:

    "This is the contract between the analysis pipeline and everything
    downstream: every metric, every signal and every intelligence claim in
    this workbook is an aggregation over these sixteen fields and nothing
    else."

So the aggregations are written against the schema, not against Stream A's
`CallExtraction`. That is deliberate and it is what lets the two streams run
in parallel: `CallExtraction` currently carries L2's fields only, because
L3 and L4 are not built yet, and aggregations written against it today would
be rewritten twice as those layers land. The schema is the authority both
streams read, and Stream A stores exactly what the schema says.

`CallTags` is therefore a *port in data form*. Whoever has the facts — the
pipeline, the `ground_truth` answer key, or a test fixture — maps them in.
Nothing in `domain/aggregation/` knows which.

## Why the joins are narrow

`CallContext` carries copies of the few employer and broker fields the
figures need rather than the `Employer` and `Broker` entities themselves.
Two reasons, and the second is the real one:

- An aggregation that takes whole entities can quietly start depending on
  any field on them.
- `Employer` carries the churn-profile label the corpus was *generated*
  from, so scoring an account on it would be circular.
  `tests/unit/test_no_circular_scoring.py` fails if any calculation so much
  as names that field — including in a comment, which is how it caught the
  first draft of this paragraph. Narrow inputs mean the label is not merely
  unread here, it is structurally out of reach: it never enters the
  aggregation layer at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from domain.value_objects.broker_named_aloud import BrokerNamedAloud
from domain.value_objects.category import Category
from domain.value_objects.complaint import Complaint
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.escalation import Escalation
from domain.value_objects.intent_statement import IntentStatement
from domain.value_objects.knowledge_failure import KnowledgeFailure
from domain.value_objects.outcome import Outcome
from domain.value_objects.process_gap import ProcessGap
from domain.value_objects.product_line import ProductLine
from domain.value_objects.signal_type import SignalType


@dataclass(frozen=True)
class CallTags:
    """One call's sixteen tags.

    Field 11 (`markers`) is deliberately absent: it is the per-marker
    evidence behind field 10's score, retained so the score is auditable,
    and the Metrics sheet is explicit that the score is "a property of the
    call and the agent, never averaged to employer, product line or broker."
    Nothing in this layer aggregates markers; the tenet views that do are
    Phase 8's, over the stored markers themselves.
    """

    reference: str

    # 1-3
    outcome: Outcome | None = None
    category: Category | None = None
    #: Multi-valued, and shares over it exceed 100%. Contact rate uses a
    #: single primary line to avoid double counting (schema field 3) — see
    #: `primary_product_line`.
    product_lines: tuple[ProductLine, ...] = ()

    # 4-8
    complaint: Complaint | None = None
    #: Distinct types per call, never occurrences (Signal Taxonomy sheet).
    signals: frozenset[SignalType] = frozenset()
    escalation: Escalation | None = None
    control_exceptions: frozenset[ControlExceptionType] = frozenset()
    knowledge_failure: KnowledgeFailure | None = None

    # 9-12
    intent: tuple[IntentStatement, ...] = ()
    quality_score: int | None = None
    #: Talk time only, excluding hold and after-call work — so every
    #: time-based figure derived from it is a floor, not an estimate.
    aht_seconds: int | None = None

    # 13-16
    caller_ref: str | None = None
    broker_named_aloud: BrokerNamedAloud | None = None
    process_gap: ProcessGap | None = None
    #: Where the failure originated, not where it surfaced.
    touchpoint: str | None = None

    @property
    def primary_product_line(self) -> ProductLine | None:
        """The one line a per-line rate may count this call under.

        `product_lines` is multi-valued and the schema warns that shares over
        it exceed 100%. Counting a two-line call once per line inflates every
        per-line contact rate, so the first line is taken as primary and the
        choice is made in one place rather than at each call site.
        """
        return self.product_lines[0] if self.product_lines else None


@dataclass(frozen=True)
class CallContext:
    """One call's tags, plus when it happened and what it joins to.

    Employer and broker are *joined*, never tagged — schema field 13 is
    explicit about that. The references here come from resolving
    `caller_ref` against reference data, which has already happened by the
    time anything in this layer runs.
    """

    tags: CallTags
    occurred_on: date
    employer_ref: str | None = None
    #: The employer's broker of record, from reference data. Not the same as
    #: `tags.broker_named_aloud.broker_ref`, which is only set when a caller
    #: said a name out loud — and where the two differ, the mismatch is
    #: itself a finding rather than an error to correct.
    broker_of_record_ref: str | None = None
    agent_ref: str | None = None

    @property
    def reference(self) -> str:
        return self.tags.reference


@dataclass(frozen=True)
class EmployerFacts:
    """The employer fields a figure may use, and no others.

    Notably absent: the churn profile. See this module's docstring.
    """

    reference: str
    name: str
    enrolled: int
    region: str
    industry: str
    renewal_month: str
    broker_ref: str
    annual_premium: float | None = None
    annual_fee: int = 0


@dataclass(frozen=True)
class BrokerFacts:
    """The broker fields a figure may use.

    `groups_in_book` and `book_lives` are different denominators and both are
    needed. Metric 2's broker complaint rate divides by groups in book;
    insight 10's ranking floor is 150 *lives*. Neither is ever a count of
    calls — the Broker Master sheet is explicit that book size comes from
    Choice's broker records, and that this is what makes the small-broker
    finding possible at all.
    """

    reference: str
    name: str
    agency: str
    region: str
    groups_in_book: int
    #: Sum of enrolled lives across this broker's employers in reference
    #: data. The Broker Master publishes groups, not lives, so this is
    #: computed — see `book_lives_for()`.
    book_lives: int = 0


def book_lives_for(broker_ref: str, employers: tuple[EmployerFacts, ...]) -> int:
    """Enrolled lives across a broker's book, from reference data.

    The Broker Master carries `groups_in_book` but no lives figure, and
    insight 10's ranking floor is stated in lives, so the two have to be
    bridged somewhere. Here, over every employer whose broker of record is
    this broker — not over the employers that happen to have called, which
    would make the denominator move with call volume and defeat the point of
    the floor.
    """
    return sum(employer.enrolled for employer in employers if employer.broker_ref == broker_ref)


@dataclass(frozen=True)
class Window:
    """The rolling window a figure is computed over.

    Passed in rather than derived from a clock: the domain layer takes no
    clock and no randomness (plan §2A.1), so "the last 12 weeks" is resolved
    by the caller and arrives here as two dates.
    """

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("A window cannot end before it starts.")

    @property
    def weeks(self) -> float:
        """Length in weeks, used to annualise. Never zero — a same-day window is one day."""
        return max((self.end - self.start).days, 1) / 7

    def contains(self, day: date) -> bool:
        """Inclusive at both ends."""
        return self.start <= day <= self.end

    def calls_in(self, calls: tuple[CallContext, ...]) -> tuple[CallContext, ...]:
        return tuple(call for call in calls if self.contains(call.occurred_on))
