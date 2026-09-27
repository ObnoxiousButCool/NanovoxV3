"""Which §9 insight rests on which scored field.

E6's checklist, as data rather than prose. The plan is explicit that "§9's
insight table is the checklist — every BUILD insight depends on named
fields, and this is where each one either earns its place or does not", so
the mapping belongs somewhere a later run can re-read rather than in a
document that goes stale the first time a field moves.

What this buys: a weak field stops being an abstract number. `outcome`
scoring 62% is hard to act on; "`outcome` scoring 62% puts insights 4, 5,
13 and 15 at risk, three of which are on the exec screen" is a decision.

**It carries no threshold.** Nothing here says what agreement is good
enough — §4 of the Phase 5 plan gives that to Minnie with the numbers in
hand. This only says which insights would be affected, whatever bar she
sets.

## What is listed, and what is not

Only insights §9 marks BUILD or PARTIAL. The WITHHELD ones — 6, 9, 17, 22,
25, 26 — are withheld because a field does not exist rather than because it
might score badly, so no amount of agreement changes them and listing them
would imply otherwise.

Dependencies are the *scored* fields only: the ones `field_map.compare_call`
actually compares. An insight resting on reference data (employer lives,
broker book size, renewal month) is not at risk from extraction agreement at
all, and several are listed with few or no field dependencies for exactly
that reason — insight 8's account facts and insight 14's exposure sums come
from Phase 1's master data, which was verified against the workbook and does
not depend on the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Insight:
    """One §9 entry and the pipeline fields it rests on."""

    number: int
    name: str
    screen: str
    #: Field names as `field_map` reports them. Empty where the insight
    #: rests on reference data rather than on anything the pipeline emits.
    fields: tuple[str, ...]
    #: §9's own status. PARTIAL entries build in part and are listed because
    #: the part that builds still depends on these fields.
    partial: bool = False


#: Every BUILD or PARTIAL insight in §9, with the scored fields behind it.
INSIGHTS: tuple[Insight, ...] = (
    # --- Screen 1: account risk ---
    Insight(
        1,
        "Account risk flag",
        "/risk",
        ("complaint.present", "complaint.attribution_target", "outcome", "intent"),
    ),
    Insight(2, "Size-matched contact rate", "/accounts", ()),
    Insight(
        6,
        "Employer-caused member confusion",
        "/accounts",
        ("root_cause_owner",),
    ),
    Insight(3, "Authority-weighted exit language", "/risk", ("intent",)),
    Insight(4, "Failure-driven repeat contact", "/accounts", ("outcome",)),
    Insight(
        5,
        "Escalation integrity",
        "/exec",
        # Metric 6's own dimensions are "Agent · trigger type · queue", so
        # the trigger type is a dimension of this insight rather than a
        # field nothing rests on.
        ("escalation.triggered", "escalation.handled", "escalation.trigger_type"),
    ),
    Insight(7, "Broker-of-record drift", "/accounts", ("broker_named_aloud.broker_ref",)),
    Insight(8, "Account facts that raise the stakes", "/accounts", ()),
    Insight(12, "Quiet-book warning", "/risk", ()),
    Insight(14, "Lives and revenue at risk by book", "/risk", ()),
    # --- Screen 2: broker and channel ---
    Insight(
        10,
        "Broker book friction, split by cause",
        "/hierarchy",
        ("broker_named_aloud.present", "broker_named_aloud.broker_ref", "touchpoint"),
    ),
    Insight(
        13, "Isolated or systemic", "/hierarchy", ("category", "broker_named_aloud.broker_ref")
    ),
    # --- Screen 3: where calls come from ---
    Insight(
        11,
        "Enrolment promise gap",
        "/demand",
        ("process_gap.present", "touchpoint"),
        partial=True,
    ),
    Insight(
        15,
        "Self-inflicted demand, costed",
        "/demand",
        ("outcome", "signals", "process_gap.present"),
    ),
    Insight(
        16,
        "Touchpoint defect ranking",
        "/demand",
        ("touchpoint", "complaint.present", "complaint.attribution_target"),
        partial=True,
    ),
    Insight(
        17,
        "Proximate vs root cause",
        "/demand",
        ("touchpoint", "complaint.attribution_target", "root_cause_owner"),
    ),
    Insight(18, "The unattributed bucket", "/demand", ("touchpoint", "complaint.present")),
    Insight(
        27,
        "Network adequacy clusters",
        "/demand",
        ("signals", "category"),
        partial=True,
    ),
    # --- Screen 4: action centre ---
    Insight(19, "Compliance exception exposure", "/actions", ("control_exceptions",)),
    Insight(20, "The action centre", "/actions", ("signals", "process_gap.present")),
    Insight(21, "Where the work came from", "/actions", ("signals",)),
    # --- Screen 5: rules, carriers and product ---
    Insight(
        23,
        "Rules we fail to explain",
        "/rules",
        ("knowledge_failure.present", "knowledge_failure.rule_id", "touchpoint"),
    ),
    Insight(24, "Rule provenance and confidence", "/rules", ("knowledge_failure.rule_id",)),
    # --- Screen 6: agent and handling ---
    Insight(28, "Agent conduct against expected band", "/agents", ("signals",)),
    Insight(29, "Member effort and complexity", "/agents", ("outcome", "escalation.triggered")),
    # --- Screen 7: value pack ---
    Insight(
        31,
        "Commercial intent routing",
        "/value-pack",
        ("intent",),
        partial=True,
    ),
    Insight(32, "Ancillary attach opportunity", "/value-pack", ("intent", "product_line")),
    Insight(
        30,
        "Quarterly value pack",
        "/value-pack",
        ("complaint.present", "outcome"),
        partial=True,
    ),
)

#: §9's WITHHELD insights. Listed so a reader can see they were considered
#: and excluded on purpose: each is withheld because a field does not exist,
#: which no agreement figure can change.
#:
#: 6 and 17 moved off this list once `root_cause_owner` (v10) shipped — see
#: `Corpus-v10-Schema-Update.md` §3's own table: `EMPLOYER` is precisely the
#: value insight 6 was withheld for lack of, and `root_cause_owner` is the
#: second, root-level record insight 17 was missing. 25 stays withheld
#: (`Corpus-v10-Decisions.md` item F: `MEMBER_MISUNDERSTANDING` is adjacent
#: in spirit but not the `PLAN_AS_DESIGNED`/`MEMBER_COMPREHENSION` pair the
#: insight specifies).
WITHHELD_INSIGHTS: tuple[int, ...] = (9, 22, 25, 26)


def insights_resting_on(field: str) -> tuple[Insight, ...]:
    """Every BUILD or PARTIAL insight that depends on one field.

    Ordered by insight number, which is how §9 lists them — a reader
    checking a finding against the plan reads down, not by screen.
    """
    return tuple(
        sorted(
            (insight for insight in INSIGHTS if field in insight.fields),
            key=lambda insight: insight.number,
        )
    )


def fields_in_use() -> tuple[str, ...]:
    """Every scored field at least one insight rests on.

    A field nobody depends on is worth knowing about too: it is either a
    field the screens do not need, or an insight nobody has mapped yet.
    """
    return tuple(sorted({field for insight in INSIGHTS for field in insight.fields}))


#: Scored fields no BUILD or PARTIAL insight was found to rest on. Recorded
#: rather than left implicit, because each is one of two things and they
#: need different answers:
#:
#: - `score` may be correct. The prototype's agents screen is explicitly
#:   "events, not scores", and §9 insight 28 reads agent conduct from the
#:   `knowledge_error` signal rather than from metric 12. If no screen
#:   quotes a call score, its agreement does not gate anything.
#: - `escalation.requested_by_caller` reaches the screens only through the
#:   `escalation_missed` signal ("an explicit escalation request went
#:   nowhere"), so it is scored but never read directly.
#: - `preventable`, `primary_issue`, `secondary_issues` and `impact_scope`
#:   are the v10 fields with no insight mapped yet — `root_cause_owner` is
#:   the one insights 6 and 17 needed, but nothing in §9 names these four
#:   directly. Recorded rather than left implicit for the same reason as
#:   the other two: a field nobody depends on is either a field the screens
#:   do not need, or an insight nobody has mapped yet.
#:
#: Both are questions for the check-in, not findings. A field nobody depends
#: on is either a field the screens do not need or an insight nobody has
#: mapped yet, and only Minnie can say which.
UNMAPPED_FIELDS: tuple[str, ...] = (
    "escalation.requested_by_caller",
    "impact_scope",
    "preventable",
    "primary_issue",
    "score",
    "secondary_issues",
)
