"""The questions this data cannot answer, stated rather than approximated.

Insights 6, 17 and 25 render withheld panels. `Backend-Stream-B-Measurement.md`
is blunt about why this module exists: "Do not build a partial version to
fill the space." A panel that answers three-quarters of a question, with no
label saying which quarter is missing, is worse than an empty one — the
reader cannot tell which part to distrust.

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


#: Insight 6. `complaint.attributed_to` has CHOICE, BROKER, CARRIER and
#: PROVIDER — and no EMPLOYER. `test_real_answer_key.py` asserts that over
#: the real corpus, so if an EMPLOYER value ever appears this panel is what
#: needs revisiting rather than the test being relaxed. Confirmed against
#: `Insights-Worth-Building.docx`: an EMPLOYER value is named there as one of
#: the v10 schema changes being *proposed*, not something v9 has.
EMPLOYER_CAUSED_CONFUSION = WithheldPanel(
    insight=6,
    question="How much member confusion is caused by the employer rather than by us",
    why=(
        "Complaint attribution has four values — CHOICE, BROKER, CARRIER, PROVIDER "
        "— and EMPLOYER is not one of them. Calls where the employer was at fault are "
        "attributed to one of the four or carry no complaint at all, so they cannot be "
        "separated out."
    ),
    unlocked_by="an EMPLOYER value in complaint.attributed_to (a v10 proposal, not v9)",
)

#: Insight 17. Splitting a single call's fault between several parties needs
#: a per-fault record with a party, a role and a fault type. §7A established
#: that this is not a v9 concept at all — the docx names a second, per-fault
#: record as *the* schema change it is proposing.
SHARED_FAULT = WithheldPanel(
    insight=17,
    question="How fault on a single call divides between more than one party",
    why=(
        "A call carries one complaint with one attribution. Nothing records a second "
        "party's contribution, so a call where both the broker and the carrier "
        "contributed is indistinguishable from one where only the named party did."
    ),
    unlocked_by="a per-fault record carrying party, role and fault type (the v10 proposal in §7A)",
)

#: Insight 25. Same root cause as 17: measuring how often each party is at
#: fault needs fault records to count.
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
    EMPLOYER_CAUSED_CONFUSION,
    SHARED_FAULT,
    FAULT_BY_PARTY,
    DID_IT_WORK,
)
