"""Call Tag Schema field 14.

"Only true when the caller says the name. `broker_ref` is validated
against the employer's broker of record; a mismatch is itself a finding.
Where `broker_ref` does not match the employer's broker of record... flag
the mismatch rather than overwriting either." `matches_employer_of_record`
is that flag — computed deterministically (a lookup, not a judgement),
never asked of the model.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.broker_sentiment import BrokerSentiment


@dataclass(frozen=True)
class BrokerNamedAloud:
    present: bool
    broker_ref: str | None = None
    sentiment: BrokerSentiment | None = None
    #: None when `present` is False, or when the employer's broker of
    #: record couldn't be determined. Otherwise: does the named broker
    #: match the employer's actual broker of record?
    matches_employer_of_record: bool | None = None

    def __post_init__(self) -> None:
        if self.present and (self.broker_ref is None or self.sentiment is None):
            raise ValueError("A present broker mention must carry a broker_ref and sentiment.")
        if not self.present and (
            self.broker_ref is not None
            or self.sentiment is not None
            or self.matches_employer_of_record is not None
        ):
            raise ValueError("An absent broker mention must not carry any of its other fields.")
