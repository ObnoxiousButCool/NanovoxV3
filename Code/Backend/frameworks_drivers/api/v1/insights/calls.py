"""`/insights/calls` — the workbench, the evidence view, and the export.

## Checkpoint I2: the columns are a server projection

Decided here, per §14.1's recorded default. `CSV_COLUMNS` below is the one
list, versioned with this endpoint. The frontend downloads bytes; it does
not know the column order and cannot disagree with it. Two column lists —
one here and one in the table component — is a support ticket nobody can
reproduce, because the file the user sends and the screen they describe
come from different code.

## Three of the prototype's twenty-six columns are not here

`calls.html` exports 26 columns. Three cannot be filled honestly:

- **Handling (archetype)** — conflict **C8a**. Not one of the sixteen
  schema fields and it has no source in the workbook. §2A.4 forbids
  inventing a definition, so the column is absent rather than blank.
- **Member effort** and **Complexity** — conflict **C8b**. Our composites,
  and not built. `indicators.py` already refuses to compute the
  `high_effort` family for the same reason.

They are **absent, not empty**. An empty column in a spreadsheet reads as
"no value for this call"; a missing column reads as "we do not publish
this", which is the true statement. `omittedColumns` on the list response
says so in the API rather than leaving the discrepancy to be noticed.

Two more are named differently on purpose: the prototype's **Caller** is
the member's name, and this exports `callerRef` instead. A CSV leaves the
application and gets mailed around; a member's name in it is personal data
travelling with no control attached, and the reference identifies the call
just as well for every use this screen supports.

## The BOM

The file opens with `\\ufeff`. Excel on Windows reads a UTF-8 CSV without
one as the system codepage, and every employer whose name carries an
accent arrives mangled. The prototype does the same thing for the same
reason.
"""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from pydantic import Field

from application.use_cases.list_calls import (
    DEFAULT_PER_PAGE,
    MAX_PER_PAGE,
    CallsQuery,
    Sort,
)
from domain.value_objects.outcome import Outcome
from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.dependencies import ListCallsDep, ReadCallEvidenceDep
from frameworks_drivers.api.v1.insights.call_analysis import (
    CallAnalysisResponse,
    analysis_response,
)
from frameworks_drivers.api.v1.insights.envelope import ScopeResponse
from frameworks_drivers.api.v1.insights.labels import CodedValue, coded, touchpoint_label
from frameworks_drivers.api.v1.insights.query import InsightsQueryDep

if TYPE_CHECKING:
    from application.use_cases.list_calls import CallRowView, CallsPage
    from application.use_cases.read_call_evidence import CallEvidence

router = APIRouter(prefix="/insights", tags=["insights"])


class CallRowResponse(CamelModel):
    """One row of the workbench."""

    reference: str
    occurred_on: str
    employer_ref: str | None = None
    employer_name: str | None = None
    caller_ref: str | None = None
    caller_name: str | None = Field(
        default=None,
        description=(
            "Who rang, from the Member and Contact sheets. Null where the "
            "reference matches nobody — a gap in reference data, not an "
            "anonymous caller, which is why the reference is sent as well."
        ),
    )
    caller_kind: str | None = Field(
        default=None,
        description="'member' or 'employer contact'. They carry different authority.",
    )
    agent_name: str | None = Field(
        default=None,
        description=(
            "From the Agent Roster. Null for an agent the roster does not know, "
            "which is why the reference travels with it rather than being replaced."
        ),
    )
    broker_ref: str | None = None
    broker_agency: str | None = None
    region: str | None = None
    agent_ref: str | None = None
    category: str | None = None
    product_lines: list[str] = Field(default_factory=list)
    touchpoint: str | None = Field(
        default=None,
        description="Words, not the Touchpoints-sheet reference — see `touchpoint_label`.",
    )
    outcome: CodedValue | None = None
    quality_score: int | None = Field(
        default=None,
        description="Null means not recorded, never a score of zero.",
    )
    aht_seconds: int | None = Field(
        default=None, description="Talk time only, so every figure from it is a floor."
    )
    complaint: bool
    complaint_against: str | None = None
    signals: list[str] = Field(default_factory=list)
    escalation_triggered: bool
    escalation_handled: bool
    control_exceptions: list[str] = Field(default_factory=list)
    knowledge_failure: bool
    intents: list[str] = Field(default_factory=list)


class CallsPageResponse(CamelModel):
    scope: ScopeResponse
    rows: list[CallRowResponse]
    total: int = Field(description="Rows matching the filters and search, before paging.")
    page: int
    per_page: int
    pages: int
    considered: int = Field(
        description=(
            "Calls in the corpus before filters and search. Filters slice, never hide: "
            "a reader must be able to tell a narrow result from an empty corpus."
        )
    )
    omitted_columns: list[str] = Field(
        default_factory=list,
        description=(
            "Columns the prototype's export has that this one does not, and why. "
            "Stated rather than left as blank columns, which would read as "
            "'no value for this call' instead of 'we do not publish this'."
        ),
    )
    unresolved_count: int = Field(description="Over every matching call, not only the page shown.")
    escalations_missed_count: int = Field(
        description="Warranted and not handled, over every matching call."
    )
    average_quality: float | None = Field(
        default=None,
        description="Null when no matching call carries a recorded score, never zero.",
    )


class TurnResponse(CamelModel):
    sequence: int
    role: str
    text: str


class CallEvidenceResponse(CamelModel):
    reference: str
    caller_type: str
    caller_ref: str
    caller_name: str | None = Field(
        default=None,
        description=(
            "Who rang, from the Member or Contact sheet. Null where the reference "
            "matches nobody -- a gap in reference data, not an anonymous caller, "
            "which is why the reference is sent as well and never replaced by it."
        ),
    )
    agent_ref: str
    agent_name: str | None = None
    employer_ref: str | None = None
    employer_name: str | None = None
    resolution_status: str
    resolution_reason: str | None = None
    turns: list[TurnResponse] = Field(default_factory=list)
    transcript_missing: bool = Field(
        description=(
            "True when the call is stored without a transcript. Distinct from an "
            "empty conversation, which is not a thing that happens."
        )
    )
    rules_unavailable: str = Field(
        description=(
            "Why the prototype's 'Rules in play' (every rule_ref the call cites, "
            "quoted from the rulebook) has no counterpart here. Said rather than "
            "rendered as an empty section beside a full one."
        )
    )
    analysis: CallAnalysisResponse = Field(
        description=(
            "What the pipeline made of this call, in five panels: L1, L2, L3, L4 "
            "and the values derived in code afterwards. Always present — a call "
            "nothing has run on gets five panels saying so, because that is the "
            "answer to what we know about it, and a null would render as a section "
            "that failed to load."
        )
    )


#: Why "Rules in play" has no counterpart in the evidence drawer. `rule_ref`
#: exists only as ground-truth data for scoring the extraction model against
#: (`domain.entities.ground_truth`) — it is not part of a call's own tags in
#: the live corpus, and the Rules sheets carry no quotable rule text, only
#: metadata (layer, area, confidence). Absent rather than invented.
RULES_UNAVAILABLE = (
    "The prototype also quotes every rule_ref this call cites, in full, from the "
    "rulebook. A cited rule is only recorded here when it names a knowledge "
    "failure, which the L3 panel carries, and even then the Rules sheets hold no "
    "rule text to quote — only which layer, area and confidence grade it has."
)

#: Why each prototype column is absent. Shipped to the client so the gap is
#: visible where the export is offered, not only in this docstring.
OMITTED_COLUMNS = (
    "Handling (archetype) — not one of the sixteen schema fields and it has no "
    "workbook source (conflict C8a). Absent rather than invented.",
    "Member effort — our composite, not a v9 field, and not built yet (C8b).",
    "Complexity — our composite, not a v9 field, and not built yet (C8b).",
)

#: The export contract. One list, versioned with this endpoint (I2).
CSV_COLUMNS: tuple[tuple[str, str], ...] = (
    ("Call ID", "reference"),
    ("Date", "occurred_on"),
    ("Employer ID", "employer_ref"),
    ("Employer", "employer_name"),
    ("Broker", "broker_agency"),
    ("Region", "region"),
    ("Agent", "agent_ref"),
    ("Topic", "category"),
    ("Product lines", "product_lines"),
    ("Touchpoint", "touchpoint"),
    ("Outcome", "outcome"),
    ("Quality score", "quality_score"),
    ("Handling time (sec)", "aht_seconds"),
    ("Complaint", "complaint"),
    ("Complaint against", "complaint_against"),
    ("Signals", "signals"),
    ("Escalation warranted", "escalation_triggered"),
    ("Escalation handled", "escalation_handled"),
    ("Control exceptions", "control_exceptions"),
    ("Knowledge failure", "knowledge_failure"),
    ("Intent", "intents"),
)


class CallsPagingQuery:
    """Search, sort and paging, separate from the shared filter set.

    `InsightsQuery` is shared by every insights endpoint because the filter
    bar is one filter bar. These four mean something on this screen alone,
    so they live here — the same reasoning that keeps `flagged` and
    `minIndicators` on the risk router.
    """

    def __init__(
        self,
        q: Annotated[
            str,
            Query(
                max_length=200,
                description=(
                    "Free text over references, names, topic and outcome — never "
                    "over transcript text. Every term must match."
                ),
            ),
        ] = "",
        sort: Annotated[Sort, Query()] = Sort.DATE,
        order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
        page: Annotated[int, Query(ge=1)] = 1,
        per_page: Annotated[int, Query(alias="perPage", ge=1, le=MAX_PER_PAGE)] = DEFAULT_PER_PAGE,
        ref: Annotated[
            list[str] | None,
            Query(
                description=(
                    'Specific calls, repeated. Powers "download selected" without '
                    "moving the column list into the browser. Applied after the "
                    "corpus filters, so a selected call the period excludes stays "
                    "excluded."
                )
            ),
        ] = None,
    ) -> None:
        self.q = q
        self.sort = sort
        self.order = order
        self.page = page
        self.per_page = per_page
        self.references = frozenset(ref or ())

    @property
    def descending(self) -> bool:
        return self.order == "desc"


CallsPagingDep = Annotated[CallsPagingQuery, Depends()]


@router.get(
    "/calls",
    response_model=CallsPageResponse,
    status_code=status.HTTP_200_OK,
    summary="The filtered corpus, one row per call",
)
async def list_calls(
    use_case: ListCallsDep,
    query: InsightsQueryDep,
    paging: CallsPagingDep,
) -> CallsPageResponse:
    page = await use_case.execute(_query(query, paging))
    return _page_response(page, query)


@router.get(
    "/calls.csv",
    status_code=status.HTTP_200_OK,
    summary="The filtered corpus as CSV",
    response_class=StreamingResponse,
)
async def export_calls(
    use_case: ListCallsDep,
    query: InsightsQueryDep,
    paging: CallsPagingDep,
) -> StreamingResponse:
    """Every matching call, not the current page.

    Paging is a reading convenience; an export of "page 2 of 7" is a file
    whose contents depend on a control the recipient cannot see. The search
    and the filters still apply, because those are the question asked.
    """
    request = _query(query, paging)
    whole = await use_case.execute(
        CallsQuery(
            request=request.request,
            q=request.q,
            sort=request.sort,
            descending=request.descending,
            page=1,
            per_page=MAX_PER_PAGE,
            references=request.references,
        )
    )
    return StreamingResponse(
        _csv(await _all_rows(use_case, request, whole)),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="nanovox-calls.csv"'},
    )


@router.get(
    "/calls/{reference}",
    response_model=CallEvidenceResponse,
    status_code=status.HTTP_200_OK,
    summary="One call and the turns behind it",
)
async def read_call(
    use_case: ReadCallEvidenceDep,
    reference: str,
) -> CallEvidenceResponse:
    return _evidence_response(await use_case.execute(reference))


def _query(query: InsightsQueryDep, paging: CallsPagingQuery) -> CallsQuery:
    return CallsQuery(
        request=query.to_request(),
        q=paging.q,
        sort=paging.sort,
        descending=paging.descending,
        page=paging.page,
        per_page=paging.per_page,
        references=paging.references,
    )


async def _all_rows(
    use_case: ListCallsDep, request: CallsQuery, first: CallsPage
) -> tuple[CallRowView, ...]:
    """Every matching row, by walking the pages the use case already serves.

    Deliberately not a second, unpaged code path: one query shape means the
    export and the table can never select different calls for the same
    filters, which is the whole point of settling I2 server-side.
    """
    rows = list(first.rows)
    for page in range(2, first.pages + 1):
        more = await use_case.execute(
            CallsQuery(
                request=request.request,
                q=request.q,
                sort=request.sort,
                descending=request.descending,
                page=page,
                per_page=MAX_PER_PAGE,
                references=request.references,
            )
        )
        rows.extend(more.rows)
    return tuple(rows)


def _csv(rows: tuple[CallRowView, ...]) -> io.StringIO:
    buffer = io.StringIO()
    # \r\n, which is what RFC 4180 says and what Excel expects.
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([heading for heading, _ in CSV_COLUMNS])
    for row in rows:
        writer.writerow([_cell(getattr(row, attribute)) for _, attribute in CSV_COLUMNS])
    # The BOM goes in front of the written content rather than being the
    # first thing written, so `csv` never quotes or escapes it.
    return io.StringIO("﻿" + buffer.getvalue())


def _cell(value: object) -> str:
    """One value as a cell. Empty for absent, never a stand-in."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, tuple):
        # Semicolons, because the field separator is a comma and a category
        # name may contain one.
        return "; ".join(str(item) for item in value)
    return str(value)


def _page_response(page: CallsPage, query: InsightsQueryDep) -> CallsPageResponse:
    return CallsPageResponse(
        scope=ScopeResponse.of(
            page.scope.corpus,
            page.scope.filtered,
            query.corpus_query(),
        ),
        rows=[_row_response(row) for row in page.rows],
        total=page.total,
        page=page.page,
        per_page=page.per_page,
        pages=page.pages,
        considered=len(page.scope.corpus.calls),
        omitted_columns=list(OMITTED_COLUMNS),
        unresolved_count=page.unresolved_count,
        escalations_missed_count=page.escalations_missed_count,
        average_quality=page.average_quality,
    )


def _row_response(row: CallRowView) -> CallRowResponse:
    return CallRowResponse(
        reference=row.reference,
        occurred_on=row.occurred_on.isoformat(),
        employer_ref=row.employer_ref,
        employer_name=row.employer_name,
        caller_ref=row.caller_ref,
        caller_name=row.caller_name,
        agent_name=row.agent_name,
        caller_kind=row.caller_kind,
        broker_ref=row.broker_ref,
        broker_agency=row.broker_agency,
        region=row.region,
        agent_ref=row.agent_ref,
        category=row.category,
        product_lines=list(row.product_lines),
        touchpoint=touchpoint_label(row.touchpoint) if row.touchpoint is not None else None,
        outcome=coded(Outcome(row.outcome)) if row.outcome is not None else None,
        quality_score=row.quality_score,
        aht_seconds=row.aht_seconds,
        complaint=row.complaint,
        complaint_against=row.complaint_against,
        signals=list(row.signals),
        escalation_triggered=row.escalation_triggered,
        escalation_handled=row.escalation_handled,
        control_exceptions=list(row.control_exceptions),
        knowledge_failure=row.knowledge_failure,
        intents=list(row.intents),
    )


def _evidence_response(evidence: CallEvidence) -> CallEvidenceResponse:
    return CallEvidenceResponse(
        reference=evidence.reference,
        caller_type=evidence.caller_type,
        caller_ref=evidence.caller_ref,
        caller_name=evidence.caller_name,
        agent_ref=evidence.agent_ref,
        agent_name=evidence.agent_name,
        employer_ref=evidence.employer_ref,
        employer_name=evidence.employer_name,
        resolution_status=evidence.resolution_status,
        resolution_reason=evidence.resolution_reason,
        turns=[
            TurnResponse(sequence=turn.sequence, role=turn.role, text=turn.text)
            for turn in evidence.turns
        ],
        transcript_missing=evidence.transcript_missing,
        rules_unavailable=RULES_UNAVAILABLE,
        analysis=analysis_response(evidence.analysis, caller_ref=evidence.caller_ref),
    )
