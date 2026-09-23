"""Call Tag Schema field 4. `attributed_to` is mandatory whenever `present`
is true — an unattributed complaint overstates CHOICE's own failure rate
(the schema's own note).
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.complaint_attribution import ComplaintAttribution


@dataclass(frozen=True)
class Complaint:
    present: bool
    attributed_to: ComplaintAttribution | None = None

    def __post_init__(self) -> None:
        if self.present and self.attributed_to is None:
            raise ValueError("A present complaint must carry an attribution.")
        if not self.present and self.attributed_to is not None:
            raise ValueError("An absent complaint must not carry an attribution.")
