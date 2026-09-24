"""The dashboard's filter set, as a predicate over calls.

The prototype states the rule this module exists to keep: **filters slice,
never hide.** The applied-filters row always shows the scope and the count,
so a figure can never quietly become a figure about a different population
than the reader thinks they are looking at.

Keeping that promise takes more than narrowing a list, because there are two
different reasons a call can fail a filter and they mean opposite things:

- The call's value *differs*. Filtering to Claims & EOB and the call is a
  billing call. The call is correctly out of scope.
- The call's value is *unknown*. Filtering to Claims & EOB and the call has
  no category at all, because extraction did not produce one. The call is
  not out of scope; it is unmeasurable against this filter.

Dropping both silently makes the second look like the first, and the reader
sees a smaller denominator with no way to tell that some of the shrinkage is
missing data rather than a narrower question. That is the same failure
`Figure` refuses when it will not let a withheld value be rendered as zero:
absence of evidence reading as evidence. So `apply` counts the second kind
separately and `FilteredCalls` carries it out to the applied-filters row.

## What is not here

**The period.** `config/dashboard.yaml` gives `window_weeks` per metric, not
per request — metric 1 looks back twelve weeks and metric 5 four, from the
same filter selection — so a single window on the filter set would be a
window that no metric could honestly use. The caller resolves each metric's
window and applies it with `Window.calls_in`.

**`source`.** `calls.source` is the transcript's origin — corpus PDF,
pasted, audio — so it decides what the corpus *is* rather than narrowing
calls already in it: whether a transcript someone pasted to try the pipeline
out counts alongside the ingested batch. That is answered before anything
becomes a `CallContext`, and it lives on `CorpusQuery` in
`application/ports/insights_source.py`.

Not to be confused with pipeline output versus the answer key, which is not
a filter in any form. The import-linter contract "Extraction and the
dashboard cannot read the answer key" means a figure has exactly one
possible provenance, and a `CallContext` deliberately cannot tell you what
it was.

**The derived filters** — risk band, repeat contact, effort, complexity.
None of them is a property of a call on its own: a repeat is a relationship
between calls, and a risk band is an assessment of an employer's whole
window. They are computed by `risk_flag` and `repeat_contact` over a corpus
and applied as a second stage, on the account references those modules
return. Putting them here would mean this module quietly needed the corpus
to answer a question about one call.

## A known ambiguity, recorded rather than hidden

`signals`, `intent` and `control_exceptions` are collections, and an empty
one is treated here as a real answer — no signals were raised — rather than
as unknown. That is right when the extractor ran and found nothing, and
wrong when it did not run. `CallTags` cannot presently tell the two apart,
so neither can this module. It is worth a schema field; until there is one,
a filter on these three can undercount rather than mark the call
unmeasurable, and that is the one place this module's promise is weaker
than it looks.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from typing import TYPE_CHECKING

from domain.aggregation.call_tags import CallContext, EmployerFacts
from domain.value_objects.category import Category
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.intent_type import IntentType
from domain.value_objects.outcome import Outcome
from domain.value_objects.product_line import ProductLine
from domain.value_objects.quality_band import QualityBand
from domain.value_objects.signal_type import SignalType

if TYPE_CHECKING:
    from collections.abc import Iterable

    from domain.dashboard_config import QualityBands


@dataclass(frozen=True)
class AppliedFilter:
    """One active filter, ready for the applied-filters row.

    Values are rendered to strings here rather than at the edge so that the
    row reads the same whoever draws it, and so that a filter's own labels
    travel with it.
    """

    field: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class Unmeasurable:
    """Calls excluded by a filter because the field was absent, not different.

    Reported per field, because the answer to "why did my denominator drop"
    is almost always one specific field that extraction did not fill.
    """

    field: str
    calls: int


@dataclass(frozen=True)
class FilteredCalls:
    """The result of narrowing a corpus, with the shrinkage accounted for.

    `considered` and `unmeasurable` exist so the applied-filters row can be
    honest about the difference between "you asked a narrower question" and
    "we could not tell for some of these calls".
    """

    calls: tuple[CallContext, ...]
    #: How many calls were offered to the filter, before any narrowing.
    considered: int
    #: Per field, the calls dropped for want of a value. Ordered by the
    #: field's position on `InsightFilters` so the row is stable between
    #: requests rather than reordering as counts change.
    unmeasurable: tuple[Unmeasurable, ...] = ()
    applied: tuple[AppliedFilter, ...] = ()

    @property
    def matched(self) -> int:
        return len(self.calls)

    @property
    def unmeasurable_calls(self) -> int:
        """Distinct calls dropped for a missing value.

        A call is blamed on the first filter it failed, so the per-field
        counts sum to this without double counting — at the cost that a call
        missing two filtered fields is only reported against one of them.
        """
        return sum(entry.calls for entry in self.unmeasurable)

    def summary(self) -> str:
        """The applied-filters row's count, in words.

        Says nothing at all when nothing was excluded for missing data,
        because a caveat that appears on every screen stops being read.
        """
        base = f"{self.matched} of {self.considered} calls"
        if not self.unmeasurable:
            return base
        detail = ", ".join(f"{entry.field} ({entry.calls})" for entry in self.unmeasurable)
        return f"{base} — {self.unmeasurable_calls} excluded for missing values: {detail}"


@dataclass(frozen=True)
class _Exclusion:
    field: str
    unknown: bool


@dataclass(frozen=True)
class InsightFilters:
    """The dashboard's filter selection.

    Values within one field are an OR — picking two categories asks for
    either — and the fields are an AND. That is what the prototype's filter
    bar does, and it is the only combination in which adding a value can
    never shrink the result and adding a field can never grow it.

    Every field defaults to empty, which means *no narrowing on that field*
    rather than *match nothing*. The distinction matters because the common
    case is a request with no filters at all, and an empty selection that
    matched nothing would make the unfiltered dashboard blank.
    """

    # --- Account scope. Resolved through reference data, not through tags.
    regions: frozenset[str] = frozenset()
    #: The employer's broker **of record**, from reference data — never
    #: `tags.broker_named_aloud`, which records only that a caller said a
    #: name out loud. Filtering on what was said aloud would answer a
    #: different question (who gets mentioned) than the one the filter bar
    #: asks (whose book is this).
    broker_refs: frozenset[str] = frozenset()
    employer_refs: frozenset[str] = frozenset()
    agent_refs: frozenset[str] = frozenset()

    # --- Call attributes, straight from the sixteen schema fields.
    categories: frozenset[Category] = frozenset()
    #: Membership, not primary line. The filter asks "calls that touched
    #: dental"; `primary_product_line` exists for the opposite job, keeping
    #: a two-line call from being counted twice in a per-line rate.
    product_lines: frozenset[ProductLine] = frozenset()
    touchpoints: frozenset[str] = frozenset()
    outcomes: frozenset[Outcome] = frozenset()
    signals: frozenset[SignalType] = frozenset()
    intents: frozenset[IntentType] = frozenset()
    complaint_targets: frozenset[ComplaintAttribution] = frozenset()
    quality_bands: frozenset[QualityBand] = frozenset()

    # --- Yes/no filters. `None` is unset; `False` is a real selection.
    escalated: bool | None = None
    complaint_present: bool | None = None
    compliance_exception: bool | None = None

    def __bool__(self) -> bool:
        """True when anything at all is selected."""
        return bool(self.applied())

    def applied(self) -> tuple[AppliedFilter, ...]:
        """Every active filter, in field order, for the applied-filters row."""
        active: list[AppliedFilter] = []
        for spec in fields(self):
            value = getattr(self, spec.name)
            if isinstance(value, bool):
                active.append(AppliedFilter(spec.name, ("yes" if value else "no",)))
            elif isinstance(value, frozenset) and value:
                rendered = tuple(sorted(_label(item) for item in value))
                active.append(AppliedFilter(spec.name, rendered))
        return tuple(active)

    def apply(
        self,
        calls: Iterable[CallContext],
        *,
        employers: tuple[EmployerFacts, ...] = (),
        quality_bands: QualityBands | None = None,
    ) -> FilteredCalls:
        """Narrow a corpus, keeping account of why each call left.

        `employers` is required only when an account-scope filter is active,
        and `quality_bands` only when a quality filter is — both raise
        rather than defaulting, because a region filter silently matching
        nothing for want of reference data is precisely the kind of quiet
        wrong answer this layer is built to make impossible.
        """
        self._require_context(employers=employers, quality_bands=quality_bands)
        by_ref = {employer.reference: employer for employer in employers}

        offered = 0
        kept: list[CallContext] = []
        missing: dict[str, int] = {}
        for call in calls:
            offered += 1
            exclusion = self._exclude(call, by_ref=by_ref, quality_bands=quality_bands)
            if exclusion is None:
                kept.append(call)
            elif exclusion.unknown:
                missing[exclusion.field] = missing.get(exclusion.field, 0) + 1

        order = [spec.name for spec in fields(self)]
        unmeasurable = tuple(Unmeasurable(name, missing[name]) for name in order if name in missing)
        return FilteredCalls(
            calls=tuple(kept),
            considered=offered,
            unmeasurable=unmeasurable,
            applied=self.applied(),
        )

    # -- internals ---------------------------------------------------------

    def _require_context(
        self,
        *,
        employers: tuple[EmployerFacts, ...],
        quality_bands: QualityBands | None,
    ) -> None:
        wants_accounts = bool(self.regions or self.broker_refs)
        if wants_accounts and not employers:
            raise ValueError(
                "A region or broker filter needs employer reference data to resolve "
                "against. Without it every call would be excluded as unmeasurable, "
                "which reads as an empty dashboard rather than as a missing input."
            )
        if self.quality_bands and quality_bands is None:
            raise ValueError(
                "A quality-band filter needs the Call Quality Framework's band "
                "thresholds from dashboard.yaml; a score cannot be placed in a band "
                "without them."
            )

    def _exclude(
        self,
        call: CallContext,
        *,
        by_ref: dict[str, EmployerFacts],
        quality_bands: QualityBands | None,
    ) -> _Exclusion | None:
        """The first filter this call fails, or None if it passes them all.

        Account scope is checked first so that a call belonging to another
        employer is reported as out of scope rather than as missing a
        category it was never going to be asked for.
        """
        employer = by_ref.get(call.employer_ref) if call.employer_ref else None

        checks: tuple[tuple[str, bool | None], ...] = (
            ("employer_refs", _in(call.employer_ref, self.employer_refs)),
            ("broker_refs", _in(employer.broker_ref if employer else None, self.broker_refs)),
            ("regions", _in(employer.region if employer else None, self.regions)),
            ("agent_refs", _in(call.agent_ref, self.agent_refs)),
            ("categories", _in(call.tags.category, self.categories)),
            ("product_lines", _overlaps(call.tags.product_lines, self.product_lines)),
            ("touchpoints", _in(call.tags.touchpoint, self.touchpoints)),
            ("outcomes", _in(call.tags.outcome, self.outcomes)),
            ("signals", _overlaps(call.tags.signals, self.signals, empty_is_known=True)),
            ("intents", self._intent_check(call)),
            ("complaint_targets", self._complaint_target_check(call)),
            ("quality_bands", self._quality_check(call, quality_bands)),
            ("escalated", self._escalated_check(call)),
            ("complaint_present", self._complaint_check(call)),
            ("compliance_exception", self._compliance_check(call)),
        )
        for name, verdict in checks:
            if verdict is None:
                return _Exclusion(name, unknown=True)
            if verdict is False:
                return _Exclusion(name, unknown=False)
        return None

    def _intent_check(self, call: CallContext) -> bool:
        if not self.intents:
            return True
        return any(statement.type in self.intents for statement in call.tags.intent)

    def _complaint_target_check(self, call: CallContext) -> bool | None:
        if not self.complaint_targets:
            return True
        complaint = call.tags.complaint
        if complaint is None:
            return None
        if not complaint.present:
            # A call with no complaint has no target, and that is an answer
            # rather than a gap: it is out of scope, not unmeasurable.
            return False
        # No third case. `Complaint.__post_init__` refuses to build a present
        # complaint without an attribution, so "complained, target unknown"
        # cannot reach here — the invariant lives in the value object and
        # re-checking it would be unreachable code.
        return complaint.attributed_to in self.complaint_targets

    def _quality_check(self, call: CallContext, bands: QualityBands | None) -> bool | None:
        if not self.quality_bands or bands is None:
            return True
        score = call.tags.quality_score
        if score is None:
            return None
        return bands.band_for(score) in self.quality_bands

    def _escalated_check(self, call: CallContext) -> bool | None:
        if self.escalated is None:
            return True
        escalation = call.tags.escalation
        if escalation is None:
            return None
        return escalation.triggered is self.escalated

    def _complaint_check(self, call: CallContext) -> bool | None:
        if self.complaint_present is None:
            return True
        complaint = call.tags.complaint
        if complaint is None:
            return None
        return complaint.present is self.complaint_present

    def _compliance_check(self, call: CallContext) -> bool:
        if self.compliance_exception is None:
            return True
        return bool(call.tags.control_exceptions) is self.compliance_exception


def _label(value: object) -> str:
    """How a filter value reads in the applied-filters row.

    The schema's enums are all `str, Enum`, whose `str()` renders as
    `Category.CLAIMS_AND_EOB` rather than as the label the sheet uses. The
    row wants the sheet's wording.
    """
    return str(value.value) if isinstance(value, Enum) else str(value)


def _in(value: object | None, wanted: frozenset[object]) -> bool | None:
    """Membership, with `None` meaning the call could not be asked."""
    if not wanted:
        return True
    if value is None:
        return None
    return value in wanted


def _overlaps(
    values: Iterable[object],
    wanted: frozenset[object],
    *,
    empty_is_known: bool = False,
) -> bool | None:
    """Whether a multi-valued field touches the selection.

    `empty_is_known` is the ambiguity this module's docstring records: for
    `signals`, an empty set is read as "none were raised" and so counts as a
    genuine non-match, while for `product_lines` an empty set means the call
    was never lined up against a product at all.
    """
    held = frozenset(values)
    if not wanted:
        return True
    if not held:
        return False if empty_is_known else None
    return bool(held & wanted)


#: The filter selection that narrows nothing, for callers that want to be
#: explicit rather than passing a bare constructor call.
NO_FILTERS = InsightFilters()

__all__ = [
    "NO_FILTERS",
    "AppliedFilter",
    "FilteredCalls",
    "InsightFilters",
    "Unmeasurable",
]
