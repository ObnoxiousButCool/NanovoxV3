"""Group 1 — peer contact rate (metric 1, §9 insight 2).

"How often a given population picks up the phone, per 1,000 people covered,
per year."

The insight is not the rate. §9 insight 2: "Compared with the size-band peer
median; show '+25% vs peers', never a bare rate." A per-1,000 figure on its
own is a number nobody can act on, because nobody carries the distribution
of the other ninety-one employers in their head. The comparison is what
makes it a finding, so `PeerComparison` is what this module returns and the
bare rate is only ever a field on it.

Two denominators, one right: lives are the calls' *own* population. The
sheet names the alternative — "Dividing sample calls by book-wide enrollment
is the classic denominator error" — and `patterns.normalised_rate` takes the
population as a required argument for exactly that reason.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

from domain.aggregation.call_tags import CallContext, EmployerFacts, Window
from domain.aggregation.figure import Figure
from domain.aggregation.patterns import normalised_rate
from domain.dashboard_config import DashboardConfig, PeerSizeBand

#: Metric 1 is published per 1,000 enrolled lives.
PER_THOUSAND = 1_000


@dataclass(frozen=True)
class PeerComparison:
    """One employer's contact rate beside the median of its own size band."""

    employer_ref: str
    rate: Figure
    band: PeerSizeBand | None
    #: The band's median rate, over the employers in it that have a
    #: publishable rate of their own. `None` when the band has no such
    #: employer, which at batch-1 volume is the common case.
    peer_median: float | None
    #: How many employers stand behind that median. Shown, not hidden: a
    #: median of two is a different claim from a median of forty.
    peers: int

    @property
    def difference(self) -> float | None:
        """The employer's rate against its peers, as a proportion.

        `+0.25` is the "+25% vs peers" §9 asks for. `None` whenever either
        side is missing — which is a real answer and renders as "no peer
        comparison available", never as 0% (no difference).
        """
        if self.rate.value is None or self.peer_median is None or self.peer_median == 0:
            return None
        return (self.rate.value - self.peer_median) / self.peer_median


def employer_contact_rate(
    config: DashboardConfig,
    employer: EmployerFacts,
    calls: Sequence[CallContext],
    window: Window,
) -> Figure:
    """Metric 1 for one employer: its calls over its own enrolled lives."""
    mine = [
        call for call in window.calls_in(tuple(calls)) if call.employer_ref == employer.reference
    ]
    return normalised_rate(
        config.metric("contact_rate"),
        matching=mine,
        population=employer.enrolled,
        per=PER_THOUSAND,
        weeks=window.weeks,
    )


def peer_comparison(
    config: DashboardConfig,
    employer: EmployerFacts,
    employers: Sequence[EmployerFacts],
    calls: Sequence[CallContext],
    window: Window,
) -> PeerComparison:
    """One employer's rate against the median of its size band.

    The median is taken over *publishable* peer rates only. Folding a
    withheld rate in as zero would drag the median down and make every
    employer in a thin band look worse than its peers — the withheld-is-not-
    zero mistake, one level up, where it is much harder to see.

    The employer's own rate is excluded from its peer median. Comparing a
    figure against a set containing itself pulls the comparison toward zero,
    and does it hardest in exactly the small bands where the comparison is
    already weakest.
    """
    band = config.size_band_for(employer.enrolled)
    peer_rates = [
        rate
        for peer in employers
        if peer.reference != employer.reference
        and band is not None
        and band.contains(peer.enrolled)
        and (rate := employer_contact_rate(config, peer, calls, window).value) is not None
    ]
    return PeerComparison(
        employer_ref=employer.reference,
        rate=employer_contact_rate(config, employer, calls, window),
        band=band,
        peer_median=median(peer_rates) if peer_rates else None,
        peers=len(peer_rates),
    )
