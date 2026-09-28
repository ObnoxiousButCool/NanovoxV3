"""The questions this data cannot answer, stated rather than approximated.

Insights 9, 22 and 25 render withheld panels. (6 and 17 used to be here too —
`domain/derivations/root_cause.py`'s `root_cause_owner` closed both, and this
module dropping them the same day is that decision's other half: a panel
still claiming a question is unanswerable after the field that answers it
ships is the exact failure mode `Backend-Stream-B-Measurement.md` warns
about, just pointed the other way.) That doc is blunt about why this module
exists: "Do not build a partial version to fill the space." A panel that
answers three-quarters of a question, with no label saying which quarter is
missing, is worse than an empty one — the reader cannot tell which part to
distrust.

§8 asks each panel to state three things: the question, why it cannot be
answered, and exactly what data would unlock it. The third is what separates
a considered gap from an oversight, and it is also the agenda for the v10
schema conversation, so it is written here as a specific field rather than
as "more data".

Each of these is withheld because a *field does not exist*, not because the
sample is small. No amount of corpus growth changes any of them — which is
why the reason is NO_FIELD and the panel says "this needs a schema change"
rather than "check back at 600 calls".
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.aggregation.figure import Figure, WithheldReason, no_field_caveat


@dataclass(frozen=True)
class WithheldPanel:
    """One question the v9 schema cannot answer, and what would unlock it."""

    insight: int
    question: str
    why: str
    unlocked_by: str

    @property
    def figure(self) -> Figure:
        """An empty figure carrying the reason, so the panel is a figure like any other.

        Deliberately the same type the published panels return. A withheld
        panel that were a different shape would be easy for a screen to
        forget to render, and the withheld ones are the panels most worth
        not forgetting.
        """
        return Figure.withheld(
            WithheldReason.NO_FIELD,
            caveats=(no_field_caveat(self.question, self.unlocked_by),),
        )


#: Insight 9. `plan.md` §9: no termination or lapse outcome exists anywhere
#: in the corpus — v9 records what a call was about, never what an account
#: went on to do. Unlike 22, more calls in the *same* shape of batch cannot
#: unlock this: it needs a fact the schema does not carry at all, which is
#: why it sits with 25 rather than with 22.
BAND_CALIBRATION = WithheldPanel(
    insight=9,
    question="Whether the risk bands actually predict who leaves",
    why=(
        "Calibrating a band against renewal outcomes needs a renewal or lapse fact per "
        "employer. Nothing in the v9 schema records what an account did at renewal — "
        "only what its calls were about — so there is no outcome to calibrate against."
    ),
    unlocked_by=(
        "a termination/renewal outcome per employer, to compute lapse rate per band, "
        "lift over the base rate, and a caveat naming bands that don't separate or "
        "hold fewer than 10 groups"
    ),
)

#: Insight 25. A relative of insight 17 (now built via `root_cause_owner`),
#: but a different population: measuring how often each party is at fault
#: across the whole book still needs a per-fault record to count, which the
#: v9 schema never carried — `root_cause_owner` names one owner per call, not
#: every party at fault on it.
FAULT_BY_PARTY = WithheldPanel(
    insight=25,
    question="How often each party is at fault, across the book",
    why=(
        "There are no fault records to count. Complaint attribution names one party per "
        "complaining call, which is a different and much narrower population than "
        "'calls where this party was at fault'."
    ),
    unlocked_by="a per-fault record carrying party, role and fault type (the v10 proposal in §7A)",
)

#: Insight 22. Withheld for a different reason from the three above — the
#: fields exist, but a before and after do not yet. It is listed here so
#: every withheld panel is in one place, and its `why` says plainly that
#: this one does resolve itself with time, unlike the others.
DID_IT_WORK = WithheldPanel(
    insight=22,
    question="Whether a fix we made actually worked",
    why=(
        "It needs the same finding measured over a window before a change and a "
        "comparable window after it. The corpus is a single 12-week batch, so no "
        "'after' exists yet. Always a before-and-after, never a causal claim."
    ),
    unlocked_by="a second batch covering a window after a logged remediation",
)

WITHHELD_PANELS: tuple[WithheldPanel, ...] = (
    BAND_CALIBRATION,
    FAULT_BY_PARTY,
    DID_IT_WORK,
)
