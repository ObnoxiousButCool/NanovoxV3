"""Call Tag Schema field 6.

"`triggered` is the denominator for escalation integrity. Never use total
calls." That note is the whole reason this is an object rather than four
loose booleans on the call: the denominator has to travel with the numerator
or somebody eventually divides by the wrong thing. Against all calls a
handled rate of 0% reads as good news; against warranted calls it reads as
the control failure it is.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Escalation:
    triggered: bool
    trigger_type: str | None = None
    requested_by_caller: bool = False
    handled: bool = False

    def __post_init__(self) -> None:
        if not self.triggered and (self.trigger_type is not None or self.handled):
            raise ValueError(
                "An escalation that never triggered cannot carry a trigger type or be handled."
            )

    @property
    def missed(self) -> bool:
        """Warranted and not handled — the numerator of the refusal view.

        The inverse of integrity over the same denominator, not a separate
        measure, which is why it is derived here rather than tagged.
        """
        return self.triggered and not self.handled
