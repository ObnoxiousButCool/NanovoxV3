"""§9 insight 7 — broker-of-record drift.

The sheet's whole instruction is three sentences, and two of them are about
what *not* to do: "A flag, not a ranking. Zero mismatches renders as a
finding." Both are tested here, because both are easy to get wrong in a way
that still looks like working code.
"""

from __future__ import annotations

from datetime import date

from domain.aggregation.broker_drift import drift
from domain.aggregation.call_tags import CallContext, CallTags
from domain.value_objects.broker_named_aloud import BrokerNamedAloud
from domain.value_objects.broker_sentiment import BrokerSentiment


def _call(
    reference: str,
    *,
    named: str | None,
    on_record: str | None,
    present: bool = True,
) -> CallContext:
    # `named=None` with `present=True` is not expressible: the value object
    # refuses a present mention that names nobody. So the only unresolved
    # side is the broker of record, which is what the tests below exercise.
    mention = (
        BrokerNamedAloud(
            present=True,
            broker_ref=named,
            sentiment=BrokerSentiment.POSITIVE,
        )
        if present and named is not None
        else BrokerNamedAloud(present=False)
    )
    return CallContext(
        tags=CallTags(reference=reference, broker_named_aloud=mention),
        occurred_on=date(2026, 9, 14),
        broker_of_record_ref=on_record,
    )


def test_a_named_broker_that_is_not_on_record_is_drift() -> None:
    result = drift([_call("C-1", named="BRK-09", on_record="BRK-02")])

    assert result.flagged is True
    assert result.mismatches == ("C-1",)
    assert "Drift on 1 of 1" in result.finding


def test_zero_mismatches_renders_as_a_finding() -> None:
    """The sheet's own instruction.

    A clean book is a result. Rendering it as an empty panel would throw
    away the one case where the answer is "we checked, and it is fine".
    """
    result = drift(
        [
            _call("C-1", named="BRK-02", on_record="BRK-02"),
            _call("C-2", named="BRK-02", on_record="BRK-02"),
        ]
    )

    assert result.flagged is False
    assert result.checked == 2
    assert "No drift" in result.finding
    assert "2 broker mention(s) matched" in result.finding


def test_no_mentions_is_a_different_sentence_from_no_drift() -> None:
    """Nothing checked is not the same as nothing wrong.

    Both have zero mismatches. Only one of them is good news, and a panel
    that collapsed them would report an unexamined book as a clean one.
    """
    result = drift([_call("C-1", named=None, on_record="BRK-02", present=False)])

    assert result.checked == 0
    assert result.flagged is False
    assert "nothing to check" in result.finding
    assert "No drift" not in result.finding


def test_an_employer_with_no_broker_of_record_is_not_drift() -> None:
    """An unknown is not a disagreement.

    Counting it as drift would manufacture a finding out of a gap in
    reference data — the failure most likely to look correct, because the
    two values genuinely are not equal.
    """
    result = drift([_call("C-2", named="BRK-02", on_record=None)])

    assert result.mismatches == ()
    assert result.unresolved == ("C-2",)
    assert result.checked == 0
    assert "not counted as drift" in result.finding


def test_it_is_a_flag_and_never_a_rate() -> None:
    """No denominator anywhere on the object.

    At this volume a rate would be two calls over three. The sheet asks for
    the flag, and a share would invite exactly the ranking it rules out.
    """
    result = drift([_call("C-1", named="BRK-09", on_record="BRK-02")])

    assert not hasattr(result, "rate")
    assert not hasattr(result, "share")
    assert "%" not in result.finding
