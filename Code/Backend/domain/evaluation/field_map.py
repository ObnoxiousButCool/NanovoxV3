"""Which answer-key column pairs with which pipeline field, and how.

E1 built the comparators; this decides what to point them at. That sounds
clerical and is not: four of these pairings are wrong in a way that produces
a plausible number rather than an error, and one of them would read as a
catastrophic failure rate for a pipeline doing nothing wrong.

## The four traps, settled

**1. `rule_refs` is not `knowledge_failure_rule_ref`.** The tracker's
`rule_refs` column is every rule the call *cited*; the knowledge-failure
rule id is the one the agent got *wrong*. A call can cite four rules and
misstate none. Comparing the two scores the pipeline against the wrong
answer entirely.

Checked while mapping, and the answer is sharper than "keep them apart":
**nothing in the pipeline produces cited rules at all.** `CallExtraction`
has no such field, so `rule_refs` is answer-key-only and is not scored.

**2. `product_line` is singular in the tracker and plural in the schema.**
Schema field 3 is an array and warns that shares over it exceed 100%; the
Transcript Tracker column holds one value. Exact-set comparison is therefore
impossible — the tracker cannot express a two-line call.

Settled as **membership**: the pipeline agrees if it found the line the
tracker named. The full extracted set travels in the comparison's `actual`,
so a pipeline that emitted all five lines on every call passes this test
*visibly* rather than quietly, and a reader can see why.

**3. `aht_seconds` is telephony, not extraction.** Schema field 12 is
emitted by the phone system, not by any layer. There is nothing for the
pipeline to get right, so it is not scored — at most it is a join key.

**4. `score` is not an independent measurement.** The rubric is
deterministic given the markers, so score agreement is a *derived view* of
marker agreement rather than a second opinion about it. Two runs agreeing on
the score agree because they agreed on the markers. It is mapped and
reported, and flagged `derived` so nobody reads it as corroboration.

`archetype` was checked on the same pass: nothing in the pipeline produces
it either, so it joins `rule_refs` as answer-key-only.

## What the answer key knows and the pipeline does not

Three tracker columns have no pipeline counterpart. They are listed rather
than dropped, because "we did not score this" and "this scored badly" look
identical in a report that omits one of them, and only the second is the
pipeline's fault.

## `control_exceptions` is scored on two of its three types

Schema field 7 allows three. L1 detects the two a greeting check can prove
(`no_recording_disclosure`, `disclosure_before_verification`). Nothing
produces `missing_benefit_disclosure`, by decision: metric 7 is kept
deterministic (see `domain/extraction/l1_deterministic.py`). It is removed
from both sides before comparing and listed in `UNSCORED`, so it reads as
"not measured" rather than as a recall miss the pipeline was never asked
to avoid.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from domain.entities.call_extraction import CallExtraction
from domain.entities.ground_truth import GroundTruth
from domain.evaluation.comparison import (
    Comparison,
    MissingSide,
    SetComparison,
    Verdict,
    compare_exact,
    compare_presence_and_detail,
    compare_set,
)
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.impact_scope import ImpactScope, ImpactScopeBucket


class Layer(StrEnum):
    """Which extraction layer owns the field — §8's "agreement per layer"."""

    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


@dataclass(frozen=True)
class Unscored:
    """An answer-key column with nothing to compare it against."""

    field: str
    why: str


#: The control exception types metric 7 measures — the two L1's greeting
#: check can prove.
_DETECTED_CONTROL_EXCEPTIONS: frozenset[str] = frozenset(
    {
        ControlExceptionType.NO_RECORDING_DISCLOSURE.value,
        ControlExceptionType.DISCLOSURE_BEFORE_VERIFICATION.value,
    }
)

#: Every tracker column the pipeline cannot be scored on, and why.
UNSCORED: tuple[Unscored, ...] = (
    Unscored(
        "rule_refs",
        "The rules a call cited. Nothing in the pipeline produces them — and this is "
        "NOT knowledge_failure.rule_id, which is the rule the agent got wrong.",
    ),
    Unscored(
        "archetype",
        "The tracker's own summary label for the call. No layer produces one.",
    ),
    Unscored(
        "aht_seconds",
        "Telephony, not extraction (schema field 12). There is nothing for the "
        "pipeline to get right.",
    ),
    Unscored(
        "control_exceptions.missing_benefit_disclosure",
        "Metric 7 is deterministic and this type needs a model's judgement, so "
        "nothing produces it. Excluded from the control_exceptions comparison "
        "rather than counted as missed.",
    ),
)


@dataclass(frozen=True)
class MappedField:
    """One comparison, and what may be said about it."""

    field: str
    layer: Layer
    comparison: Comparison | SetComparison
    #: True for `score`: real, reported, and downstream of marker agreement
    #: rather than independent evidence about it.
    derived: bool = False


def compare_call(truth: GroundTruth, extraction: CallExtraction | None) -> tuple[MappedField, ...]:
    """Every scoreable field, for one call.

    `extraction` is `None` when the pipeline produced nothing for the call at
    all — a run that failed or never reached it. Every field then comes back
    NOT_COMPARABLE with `MissingSide.PIPELINE`, which is what stops a failed
    run reading as a set of fields nobody could score.
    """
    fields: list[MappedField] = []

    def add(
        name: str, layer: Layer, comparison: Comparison | SetComparison, *, derived: bool = False
    ) -> None:
        fields.append(MappedField(field=name, layer=layer, comparison=comparison, derived=derived))

    call = extraction
    complaint = call.complaint if call else None
    broker = call.broker_named_aloud if call else None
    knowledge = call.knowledge_failure if call else None
    gap = call.process_gap if call else None

    # --- L1: deterministic ---
    add("control_exceptions", Layer.L1, _control_exceptions(truth, call))

    # --- L1/L2: classification ---
    add(
        "outcome",
        Layer.L2,
        compare_exact("outcome", truth.outcome, call.outcome if call else None),
    )
    add(
        "category",
        Layer.L2,
        compare_exact("category", truth.category, call.category if call else None),
    )
    add(
        "touchpoint",
        Layer.L2,
        compare_exact("touchpoint", _blank(truth.touchpoint), call.touchpoint if call else None),
    )
    add("product_line", Layer.L2, _product_line(truth, call))
    add("intent", Layer.L2, _intent(truth, call))

    presence, detail = compare_presence_and_detail(
        "complaint",
        expected_present=truth.complaint_present,
        actual_present=complaint.present if complaint else None,
        expected_detail=_blank(truth.complaint_attributed_to),
        actual_detail=complaint.attributed_to if complaint else None,
    )
    add("complaint.present", Layer.L2, presence)
    add("complaint.attribution_target", Layer.L2, detail)

    add(
        "escalation.triggered",
        Layer.L2,
        compare_exact(
            "escalation.triggered",
            truth.escalation_triggered,
            call.escalation_triggered if call else None,
        ),
    )
    add(
        "escalation.requested_by_caller",
        Layer.L2,
        compare_exact(
            "escalation.requested_by_caller",
            truth.escalation_requested_by_caller,
            call.escalation_requested_by_caller if call else None,
        ),
    )

    broker_presence, broker_detail = compare_presence_and_detail(
        "broker_named_aloud",
        expected_present=truth.broker_named_present,
        actual_present=broker.present if broker else None,
        expected_detail=_blank(truth.broker_named_broker_ref),
        actual_detail=broker.broker_ref if broker else None,
    )
    add("broker_named_aloud.present", Layer.L1, broker_presence)
    add("broker_named_aloud.broker_ref", Layer.L1, broker_detail)

    # --- L3: quality and knowledge ---
    kf_presence, kf_detail = compare_presence_and_detail(
        "knowledge_failure",
        expected_present=truth.knowledge_failure_present,
        actual_present=knowledge.present if knowledge else None,
        expected_detail=_blank(truth.knowledge_failure_rule_ref),
        actual_detail=knowledge.rule_id if knowledge else None,
    )
    add("knowledge_failure.present", Layer.L3, kf_presence)
    add("knowledge_failure.rule_id", Layer.L3, kf_detail)
    add("score", Layer.L3, compare_exact("score", truth.score, _score_of(call)), derived=True)

    # --- L4: signals and gaps ---
    add("signals", Layer.L4, _signals(truth, call))
    add(
        "escalation.handled",
        Layer.L4,
        compare_exact(
            "escalation.handled",
            truth.escalation_handled,
            call.escalation_handled if call else None,
        ),
    )
    add(
        "escalation.trigger_type",
        Layer.L4,
        compare_exact(
            "escalation.trigger_type",
            _blank(truth.escalation_type),
            call.escalation_trigger_type if call else None,
        ),
    )
    add(
        "process_gap.present",
        Layer.L4,
        compare_exact(
            "process_gap.present", truth.process_gap_present, gap.present if gap else None
        ),
    )
    add(
        "root_cause_owner",
        Layer.L4,
        compare_exact(
            "root_cause_owner", truth.root_cause_owner, call.root_cause_owner if call else None
        ),
    )
    add(
        "preventable",
        Layer.L4,
        compare_exact("preventable", truth.preventable, call.preventable if call else None),
    )

    # --- L2: the other three v10 fields ---
    add("primary_issue", Layer.L2, _primary_issue(truth, call))
    add("secondary_issues", Layer.L2, _secondary_issues(truth, call))
    add("impact_scope", Layer.L2, _impact_scope(truth, call))

    return tuple(fields)


def fields_for(layer: Layer, mapped: Sequence[MappedField]) -> tuple[MappedField, ...]:
    """The fields one layer owns — §8's "agreement per layer"."""
    return tuple(field for field in mapped if field.layer is layer)


def _product_line(truth: GroundTruth, call: CallExtraction | None) -> Comparison:
    """Trap 2 — membership, because the tracker holds one value and the schema a set."""
    expected = _blank(truth.product_line)
    if call is None:
        return compare_exact("product_line", expected, None)
    found = sorted(line.value for line in call.product_lines)
    if expected is None:
        return compare_exact("product_line", None, ", ".join(found) or None)
    if not found:
        return Comparison(
            field="product_line",
            verdict=Verdict.NOT_COMPARABLE,
            expected=expected,
            missing=MissingSide.PIPELINE,
        )
    return Comparison(
        field="product_line",
        verdict=Verdict.AGREED if expected in found else Verdict.DISAGREED,
        expected=expected,
        actual=", ".join(found),
    )


def _intent(truth: GroundTruth, call: CallExtraction | None) -> Comparison:
    """Same shape as product line: one tracker value against a list."""
    expected = _blank(truth.intent_type)
    if call is None:
        return compare_exact("intent", expected, None)
    found = sorted(statement.type.value for statement in call.intent)
    if expected is None:
        return compare_exact("intent", None, ", ".join(found) or None)
    if not found:
        return Comparison(
            field="intent",
            verdict=Verdict.NOT_COMPARABLE,
            expected=expected,
            missing=MissingSide.PIPELINE,
        )
    return Comparison(
        field="intent",
        verdict=Verdict.AGREED if expected in found else Verdict.DISAGREED,
        expected=expected,
        actual=", ".join(found),
    )


def _signals(truth: GroundTruth, call: CallExtraction | None) -> SetComparison:
    """Set overlap on the signal codes.

    Severity and owner are fixed per code and derived from it, so comparing
    them would be comparing the taxonomy against itself.
    """
    expected = {signal.code for signal in truth.signals}
    actual = None if call is None else {signal.type.value for signal in call.signals}
    return compare_set("signals", expected, actual)


def _primary_issue(truth: GroundTruth, call: CallExtraction | None) -> Comparison:
    """Case-insensitive text equality — the only free-text field with no
    controlled vocabulary (`Documents/notes/Corpus-v10-Decisions.md` item C), so an exact
    case match would fail on capitalisation alone rather than on substance.
    """
    expected = _blank(truth.primary_issue)
    actual = call.primary_issue if call else None
    if expected is None or actual is None:
        return compare_exact("primary_issue", expected, actual)
    agreed = expected.strip().lower() == actual.strip().lower()
    return Comparison(
        field="primary_issue",
        verdict=Verdict.AGREED if agreed else Verdict.DISAGREED,
        expected=expected,
        actual=actual,
    )


def _secondary_issues(truth: GroundTruth, call: CallExtraction | None) -> Comparison:
    """Overlap, not exact-set equality: `secondary_issues` is free text on
    both sides, so the tracker and the pipeline rarely phrase an issue
    identically. Any shared item (case-insensitive) counts as agreement —
    the same "at least one word right" leniency `primary_issue` gets, but
    applied per-item across a set rather than to one string.
    """
    expected = {item.strip().lower() for item in truth.secondary_issues if item.strip()}
    if call is None:
        return compare_exact(
            "secondary_issues", ", ".join(sorted(expected)) if expected else None, None
        )
    actual = {item.strip().lower() for item in call.secondary_issues if item.strip()}
    expected_render = ", ".join(sorted(expected)) or None
    actual_render = ", ".join(sorted(actual)) or None
    if not expected and not actual:
        return Comparison(field="secondary_issues", verdict=Verdict.AGREED)
    if not expected or not actual:
        return compare_exact("secondary_issues", expected_render, actual_render)
    agreed = bool(expected & actual)
    return Comparison(
        field="secondary_issues",
        verdict=Verdict.AGREED if agreed else Verdict.DISAGREED,
        expected=expected_render,
        actual=actual_render,
    )


#: Words that name each `ImpactScopeBucket`'s subject, to look for in the
#: tracker's own free text (`GroundTruth.impact_scope`, deliberately unparsed
#: — see `domain/value_objects/impact_scope.py`). Best-effort only: this is
#: a keyword heuristic over prose, not a parse, so it under-reads phrasing
#: that avoids these exact words (e.g. "the whole team" for `1_group`).
_IMPACT_SCOPE_WORDS: dict[ImpactScopeBucket, tuple[str, ...]] = {
    ImpactScopeBucket.ONE_MEMBER: ("member",),
    ImpactScopeBucket.ONE_GROUP: ("group",),
    ImpactScopeBucket.N_EMPLOYEES: ("employee",),
    ImpactScopeBucket.N_MEMBERS_AND_DEPENDENTS: ("member", "dependent"),
}


def _impact_scope(truth: GroundTruth, call: CallExtraction | None) -> Comparison:
    """Best-effort comparison of the pipeline's `ImpactScope` (bucket +
    optional count) against the tracker's raw string.

    Heuristic, not exact: agreement means the bucket's characteristic
    word(s) appear in the tracker's text, and — when the bucket carries a
    count — that number's digits also appear there. This will miss a
    genuine agreement written in different words (a spelled-out "eleven"
    against a stored count of 11) and will not be fooled into a false
    disagreement by punctuation or case; it trades recall for never
    silently mis-scoring a call it can't confidently read.
    """
    expected = _blank(truth.impact_scope)
    scope = call.impact_scope if call else None
    actual = _render_impact_scope(scope)
    if expected is None or scope is None:
        return compare_exact("impact_scope", expected, actual)

    haystack = expected.lower()
    agreed = all(word in haystack for word in _IMPACT_SCOPE_WORDS[scope.bucket])
    if agreed and scope.count is not None:
        agreed = str(scope.count) in haystack
    return Comparison(
        field="impact_scope",
        verdict=Verdict.AGREED if agreed else Verdict.DISAGREED,
        expected=expected,
        actual=actual,
    )


def _render_impact_scope(scope: ImpactScope | None) -> str | None:
    if scope is None:
        return None
    if scope.count is None:
        return scope.bucket.value
    return f"{scope.bucket.value} (count={scope.count})"


def _control_exceptions(truth: GroundTruth, call: CallExtraction | None) -> SetComparison:
    """Set overlap on the exception types, so precision and recall stay apart
    — metric 7 is reported by type, never as one blended number.

    Only the types the pipeline is built to detect are compared; the rest
    are listed in `UNSCORED`.
    """
    expected = set(truth.control_exceptions) & _DETECTED_CONTROL_EXCEPTIONS
    actual = (
        None
        if call is None or call.control_exceptions is None
        else {item.value for item in call.control_exceptions} & _DETECTED_CONTROL_EXCEPTIONS
    )
    return compare_set("control_exceptions", expected, actual)


def _score_of(call: CallExtraction | None) -> int | None:
    if call is None or call.quality_score is None:
        return None
    return int(call.quality_score.value)


def _blank(value: str | None) -> str | None:
    """The tracker writes an absent value as an empty cell, not as null."""
    return value or None
