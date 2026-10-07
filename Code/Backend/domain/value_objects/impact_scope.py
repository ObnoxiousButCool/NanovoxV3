"""Call Tag Schema field 20 (v10) — how many people the caller says are
affected, in the schema's own four buckets, plus the count itself where
the bucket needs one.

`Documents/notes/Corpus-v10-Decisions.md` item D: capture both. The schema's own example
for why the field matters — "eleven of my people cannot find a
provider" — loses the eleven if only the bucket is stored, and the bucket
alone cannot turn "one member confused" into "a group-level incident" the
way the schema entry says this field is for.

The tracker's own written answers are messier than these four buckets —
"1 dependent" alone, "4 employees" and "four employees" both spelled out,
compound forms like "1 member + 2 dependents" — because it is free text
written by hand, not validated against this enum. `GroundTruth` keeps the
raw string rather than forcing it into one of these four (plan §3.0: the
workbook wins on definitions, but its own data does not always follow its
own schema's shorthand, and normalising past that would misrepresent what
the tracker actually says). This value object is the pipeline's *target*
shape — what the model is asked to produce — not a parser for what the
tracker already wrote.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from domain.errors import ValidationError


class ImpactScopeBucket(StrEnum):
    ONE_MEMBER = "1_member"
    ONE_GROUP = "1_group"
    N_EMPLOYEES = "n_employees"
    N_MEMBERS_AND_DEPENDENTS = "n_members_and_dependents"


#: Buckets the schema states as a plain count of people, where `count`
#: names how many. The other two buckets are inherently singular.
_NEEDS_COUNT = frozenset(
    {ImpactScopeBucket.N_EMPLOYEES, ImpactScopeBucket.N_MEMBERS_AND_DEPENDENTS}
)


@dataclass(frozen=True)
class ImpactScope:
    bucket: ImpactScopeBucket
    #: The N in "N employees" / "N members + dependents". `None` for the
    #: two buckets that are inherently one person.
    count: int | None = None

    def __post_init__(self) -> None:
        if self.bucket in _NEEDS_COUNT and (self.count is None or self.count < 1):
            raise ValidationError(
                f"impact_scope bucket {self.bucket.value!r} needs a count of at least 1.",
            )
        if self.bucket not in _NEEDS_COUNT and self.count is not None:
            raise ValidationError(
                f"impact_scope bucket {self.bucket.value!r} does not carry a count.",
            )
