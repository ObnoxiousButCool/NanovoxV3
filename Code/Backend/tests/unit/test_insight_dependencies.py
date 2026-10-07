"""The §9 checklist, kept honest against the fields actually scored.

A dependency map is the kind of thing that is right on the day it is written
and quietly wrong six weeks later. These tests tie it to `field_map` so that
adding or renaming a scored field fails here rather than silently leaving an
insight unaccounted for.
"""

from __future__ import annotations

from domain.entities.ground_truth import GroundTruth
from domain.evaluation.field_map import compare_call
from domain.evaluation.insight_dependencies import (
    INSIGHTS,
    UNMAPPED_FIELDS,
    WITHHELD_INSIGHTS,
    fields_in_use,
    insights_resting_on,
)


def _scored_fields() -> set[str]:
    return {mapped.field for mapped in compare_call(GroundTruth(reference="C-0001"), None)}


def test_every_dependency_names_a_field_that_is_actually_scored() -> None:
    """A dependency on a field nothing compares is a dependency nobody can
    check. Renaming a field in `field_map` fails here rather than leaving an
    insight pointing at a name that no longer exists.
    """
    unknown = sorted(set(fields_in_use()) - _scored_fields())

    assert unknown == []


def test_the_fields_no_insight_rests_on_are_the_ones_recorded() -> None:
    """A field nobody depends on is either a field the screens do not need
    or an insight nobody has mapped, and only Minnie can say which — so the
    set is pinned rather than allowed to grow unnoticed.
    """
    unmapped = sorted(_scored_fields() - set(fields_in_use()))

    assert unmapped == sorted(UNMAPPED_FIELDS)


def test_withheld_insights_are_not_listed_as_depending_on_anything() -> None:
    """They are withheld because a field does not exist, which no agreement
    figure can change. Listing them would imply a good score could unlock
    them.
    """
    listed = {insight.number for insight in INSIGHTS}

    assert listed.isdisjoint(WITHHELD_INSIGHTS)


def test_a_weak_field_names_the_insights_it_puts_at_risk() -> None:
    """The whole point of the map: `outcome` scoring badly is hard to act
    on, and "it puts these four insights at risk" is a decision.
    """
    at_risk = insights_resting_on("outcome")

    assert {insight.number for insight in at_risk} == {1, 4, 15, 29, 30}


def test_a_field_nothing_rests_on_returns_nothing_rather_than_guessing() -> None:
    assert insights_resting_on("score") == ()


def test_escalation_integrity_carries_its_own_dimension() -> None:
    """Metric 6's dimensions are "Agent · trigger type · queue", so the
    trigger type belongs to insight 5 rather than to nothing.
    """
    assert "escalation.trigger_type" in next(i for i in INSIGHTS if i.number == 5).fields


def test_every_insight_has_a_screen_and_a_name() -> None:
    """The write-up groups by screen, because "three of these are on the
    exec screen" is what turns a list of numbers into a priority.
    """
    for insight in INSIGHTS:
        assert insight.name.strip()
        assert insight.screen.startswith("/")


def test_no_insight_is_listed_twice() -> None:
    numbers = [insight.number for insight in INSIGHTS]

    assert len(numbers) == len(set(numbers))


# --- v10: root_cause_owner unblocks insights 6 and 17 -----------------------


def test_insights_6_and_17_are_no_longer_withheld() -> None:
    """`root_cause_owner` (v10) supplies exactly what each was withheld for
    lack of — see `Documents/notes/Corpus-v10-Schema-Update.md` §3's own table."""
    assert 6 not in WITHHELD_INSIGHTS
    assert 17 not in WITHHELD_INSIGHTS


def test_insight_6_depends_on_root_cause_owner() -> None:
    insight = next(i for i in INSIGHTS if i.number == 6)

    assert "root_cause_owner" in insight.fields


def test_insight_17_depends_on_root_cause_owner() -> None:
    insight = next(i for i in INSIGHTS if i.number == 17)

    assert "root_cause_owner" in insight.fields


def test_insight_25_stays_withheld() -> None:
    """`Documents/notes/Corpus-v10-Decisions.md` item F: `MEMBER_MISUNDERSTANDING` is
    adjacent in spirit but not the exact pair the insight specifies, so
    nothing here reinterprets it into BUILD."""
    assert 25 in WITHHELD_INSIGHTS
