"""The evaluation CLI's report and its exit codes.

The exit code carries a decision, so it is worth pinning down. "The harness
broke" and "the pipeline has not run" are different conditions with
different fixes, and a caller running this in a pipeline needs to tell them
apart. What is deliberately *not* here is an exit code for a low agreement
rate — §8 gives that judgement to Minnie.
"""

from __future__ import annotations

import pytest

from application.ports.diagnostics_source import Diagnostics
from application.use_cases.evaluate_extraction import EvaluationReport
from domain.evaluation.agreement import Agreement, LayerAgreement
from domain.run_cost import RunCost, run_cost
from domain.value_objects.token_usage import TokenUsage
from frameworks_drivers.cli.evaluate_extraction import (
    EXIT_NOTHING_COMPARED,
    EXIT_OK,
    _report,
)


def _field(name: str, agreed: int, disagreed: int, *, silent: int = 0) -> Agreement:
    return Agreement(
        field=name,
        agreed=agreed,
        disagreed=disagreed,
        no_answer_key=0,
        no_pipeline_value=silent,
        neither=0,
    )


def _report_for(
    fields: tuple[Agreement, ...], *, calls: int = 10, scored: int = 10
) -> EvaluationReport:
    return EvaluationReport(
        calls=calls,
        scored=scored,
        unscored_calls=tuple(f"C-{i:04d}" for i in range(scored + 1, calls + 1)),
        fields=fields,
        layers=(LayerAgreement(layer="L2", fields=fields),),
    )


def test_the_headline_states_coverage_not_just_a_count(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _report(_report_for((_field("outcome", 9, 1),), calls=100, scored=10))

    output = capsys.readouterr().out
    assert "Scored 10 of 100 call(s) with an answer key (10% coverage)." in output


def test_unscored_calls_are_named(capsys: pytest.CaptureFixture[str]) -> None:
    _report(_report_for((_field("outcome", 2, 0),), calls=3, scored=2))

    assert "No pipeline output for 1 call(s): C-0003" in capsys.readouterr().out


def test_a_long_list_of_unscored_calls_is_truncated_with_a_count(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An operator needs the shape of the problem, not ninety lines of it."""
    _report(_report_for((_field("outcome", 5, 0),), calls=100, scored=5))

    output = capsys.readouterr().out
    assert "... and 75 more" in output


def test_every_field_line_carries_its_coverage(capsys: pytest.CaptureFixture[str]) -> None:
    """100% on four calls and 100% on ninety-eight are the same number and
    different findings.
    """
    _report(_report_for((_field("outcome", 4, 0, silent=96),)))

    output = capsys.readouterr().out
    assert "4 of 100 call(s)" in output
    assert "96 with no pipeline value" in output


def test_the_weakest_field_in_a_layer_is_named(capsys: pytest.CaptureFixture[str]) -> None:
    _report(_report_for((_field("outcome", 9, 1), _field("category", 2, 8))))

    assert "weakest: category" in capsys.readouterr().out


def test_fields_are_listed_worst_first(capsys: pytest.CaptureFixture[str]) -> None:
    """A reader scanning for what to fix should not have to scroll."""
    _report(_report_for((_field("outcome", 9, 1), _field("category", 2, 8))))

    output = capsys.readouterr().out
    assert output.index("category:") < output.index("outcome:")


def test_the_columns_that_cannot_be_scored_are_printed_with_their_reasons(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _report(_report_for((_field("outcome", 9, 1),)))

    output = capsys.readouterr().out
    assert "aht_seconds" in output
    assert "rule_refs" in output


def test_no_pass_mark_is_printed(capsys: pytest.CaptureFixture[str]) -> None:
    """The report says so out loud, because the absence of a verdict is
    easy to mistake for an oversight.
    """
    _report(_report_for((_field("outcome", 9, 1),)))

    assert "No pass mark is applied" in capsys.readouterr().out


def test_nothing_compared_says_run_the_extraction_first(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Not a bad score — the absence of one, and the fix is somewhere else
    entirely.
    """
    _report(_report_for((_field("outcome", 0, 0, silent=10),), calls=10, scored=0))

    output = capsys.readouterr().out
    assert "NOTHING COMPARED" in output
    assert "Run the extraction first." in output
    assert "Agreement by field" not in output


def test_the_two_outcomes_have_different_exit_codes() -> None:
    """Not a tautology: collapsing these would hide "the pipeline has not
    run" behind a generic failure, and the two are fixed in different
    places.
    """
    assert EXIT_OK != EXIT_NOTHING_COMPARED
    assert _report_for((_field("outcome", 9, 1),)).comparable is True
    assert _report_for((_field("outcome", 0, 0, silent=10),)).comparable is False


# --- Diagnostics -----------------------------------------------------------


def _diagnostics(
    *,
    rejected: tuple[tuple[str, int], ...] = (),
    raised: int = 0,
    unresolved: tuple[str, ...] = (),
    cost: RunCost | None = None,
) -> Diagnostics:
    return Diagnostics(
        rejected_evidence=rejected,
        markers_raised=raised,
        unresolved_callers=unresolved,
        last_run_cost=cost,
    )


def _with(diagnostics: Diagnostics) -> EvaluationReport:
    return EvaluationReport(
        calls=10,
        scored=10,
        unscored_calls=(),
        fields=(_field("outcome", 9, 1),),
        layers=(LayerAgreement(layer="L2", fields=(_field("outcome", 9, 1),)),),
        diagnostics=diagnostics,
    )


def test_refused_evidence_is_a_headline_with_its_reasons(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The Call Quality Framework treats refusals as a measurable property
    of the model, not an invisible error in the score.
    """
    _report(
        _with(
            _diagnostics(
                raised=40,
                rejected=(("quote_not_in_turn", 6), ("unknown_dimension", 2)),
            )
        )
    )

    output = capsys.readouterr().out
    assert "40 marker(s) raised, 20% refused" in output
    assert "quote_not_in_turn: 6" in output
    assert "unknown_dimension: 2" in output


def test_no_markers_raised_is_not_a_zero_percent_refusal_rate(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Zero refused would read as a model that never makes things up. It
    has not run.
    """
    _report(_with(_diagnostics(raised=0)))

    output = capsys.readouterr().out
    assert "no marker has been raised" in output
    assert "0% refused" not in output


def test_unresolved_callers_say_what_they_cost(capsys: pytest.CaptureFixture[str]) -> None:
    """They are counted, never dropped — but they can never be linked to a
    follow-up, so they silently weaken repeat contact and FCR.
    """
    _report(_with(_diagnostics(unresolved=("C-0004", "C-0009"))))

    output = capsys.readouterr().out
    assert "Unresolved callers: 2 call(s)" in output
    assert "never linkable to a follow-up" in output
    assert "C-0004, C-0009" in output


def test_a_cost_that_is_a_floor_says_so(capsys: pytest.CaptureFixture[str]) -> None:
    cost = run_cost([TokenUsage(input_tokens=900, output_tokens=100), TokenUsage.unreported()])

    _report(_with(_diagnostics(cost=cost)))

    output = capsys.readouterr().out
    assert "At least 1,000 tokens" in output
    assert "floor" in output


def test_no_run_recorded_is_stated_rather_than_shown_as_free(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _report(_with(_diagnostics()))

    assert "Last run: none recorded." in capsys.readouterr().out


def test_diagnostics_are_omitted_entirely_when_no_source_was_given(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Better an absent section than one full of zeroes that look measured."""
    _report(_report_for((_field("outcome", 9, 1),)))

    assert "Diagnostics" not in capsys.readouterr().out


def test_each_field_names_what_it_holds_up(capsys: pytest.CaptureFixture[str]) -> None:
    """§9's insight table is the checklist. A field scoring badly is hard to
    act on; the insights it holds up are a decision.
    """
    _report(_report_for((_field("outcome", 6, 4),)))

    output = capsys.readouterr().out
    assert "holds up:" in output
    assert "4 Failure-driven repeat contact" in output
    assert "15 Self-inflicted demand, costed" in output


def test_a_field_nothing_rests_on_says_so_rather_than_staying_silent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Silence would read as "no insights affected". It means nobody has
    mapped one, which is a question, not an all-clear.
    """
    _report(_report_for((_field("score", 6, 4),)))

    assert "nothing mapped" in capsys.readouterr().out
