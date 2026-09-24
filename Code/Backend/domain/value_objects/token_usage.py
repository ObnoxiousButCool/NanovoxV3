"""Tokens consumed producing one answer.

Moved here from `application/ports/llm_provider.py` in E3: it is a pure
value about work done, with no dependency on the provider port or anything
else outward, and Phase 5's cost roll-up is a domain calculation that could
not otherwise reach it.

## Zero is three different things, and only one of them is "free"

The distinction this type exists to keep is that a total of zero can mean
any of:

1. **A cached stage.** The stage cache returned a stored response and no
   provider was called, so the call genuinely cost nothing. `reported` stays
   True: zero, and we know it.
2. **A provider that did not report usage.** Some do not. The tokens were
   spent and nobody counted them. `reported` is False, and any total
   containing one of these is a **floor**, not a cost.
3. **Nothing ran at all.**

Collapsing 2 into 1 quietly understates every cost figure downstream, and it
understates it invisibly — a run costing twice what it claims looks exactly
like a cheap run. So `reported` travels with the numbers, `__add__` keeps it
false once any part is unreported, and the diagnostics say "at least" when
it is.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class TokenUsage:
    """Tokens consumed by one request.

    Zero means "the provider did not report it" only when `reported` is
    False. The audit log keeps the distinction visible so a cost figure is
    never quietly understated.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    reported: bool = True

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @classmethod
    def unreported(cls) -> TokenUsage:
        return cls(input_tokens=0, output_tokens=0, reported=False)

    def __add__(self, other: TokenUsage) -> TokenUsage:
        """Sum two usages, keeping `reported` false once either part is.

        One unreported layer makes the whole call's total a floor. Summing
        `reported` with `and` rather than dropping it is what stops a run
        with one silent provider reporting a confident, wrong cost.
        """
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            reported=self.reported and other.reported,
        )

    @classmethod
    def total(cls, usages: Iterable[TokenUsage]) -> TokenUsage:
        """Sum a sequence. An empty sequence is a reported zero — nothing ran."""
        result = cls()
        for usage in usages:
            result = result + usage
        return result
