"""The three diagnostics §8 Phase 5 asks for beside the agreement numbers.

Read together through one port rather than bolted onto three existing
repositories, because they answer one question — *how much should you trust
the agreement figures above?* — and a caller that had to assemble them from
three places would eventually show one without the others.

Each is a different way the numbers can be quietly weaker than they look:

- **Rejected evidence.** A score built on markers that failed verification
  is not a score. The Call Quality Framework treats refusals as a measurable
  property of the model rather than an invisible error, which is why they
  are a headline here and not a footnote.
- **Unresolved callers.** A call whose `caller_ref` matched no member or
  contact is counted, never dropped — but it can never be linked to a
  follow-up, so it silently weakens repeat contact and first-contact
  resolution wherever it appears.
- **The last run's cost.** What the numbers cost to produce, and whether
  that figure is a cost or a floor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from domain.run_cost import RunCost


@dataclass(frozen=True)
class Diagnostics:
    """What to know about the run behind an agreement figure."""

    #: Refusal reason to count, worst-first by count. Empty when no marker
    #: was ever refused, which is itself worth seeing.
    rejected_evidence: tuple[tuple[str, int], ...]
    #: Markers the model raised, refused and accepted together — the
    #: denominator the refusals are a share of.
    markers_raised: int
    #: Calls whose caller could not be resolved against reference data.
    #: Named rather than counted: they are excluded from employer metrics,
    #: so anyone reading an employer figure wants to know which.
    unresolved_callers: tuple[str, ...]
    #: `None` when no run has been recorded at all.
    last_run_cost: RunCost | None

    @property
    def rejection_rate(self) -> float | None:
        """Refused markers over markers raised. `None` when none were raised.

        `None` rather than 0.0: a pipeline that raised no markers has no
        rejection rate, and reporting zero would read as a model that never
        makes things up rather than one that has not run.
        """
        if not self.markers_raised:
            return None
        return sum(count for _, count in self.rejected_evidence) / self.markers_raised


class DiagnosticsSource(ABC):
    """Reads the three diagnostics from wherever a run left them."""

    @abstractmethod
    async def read(self) -> Diagnostics: ...
