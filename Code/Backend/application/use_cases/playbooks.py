"""Resolve the issue keys every screen links to (Revised plan Phase 4, I3).

The catalogue is loaded once at startup; resolving a key only reads the
Touchpoints sheet, because a `tp_` key is valid only for a touchpoint on it.
"""

from __future__ import annotations

from dataclasses import dataclass

from application.ports.reference_lookup import ReferenceLookup
from domain.playbooks import Playbook, PlaybookCatalogue, resolve


@dataclass(frozen=True)
class PlaybookResolution:
    """What a key resolved to. A held-back key names its reason instead."""

    key: str
    playbook: Playbook | None
    held_back_reason: str | None = None


class ListPlaybooks:
    def __init__(self, catalogue: PlaybookCatalogue) -> None:
        self._catalogue = catalogue

    def execute(self) -> PlaybookCatalogue:
        return self._catalogue


class GetPlaybook:
    def __init__(self, catalogue: PlaybookCatalogue, reference_lookup: ReferenceLookup) -> None:
        self._catalogue = catalogue
        self._lookup = reference_lookup

    async def execute(self, key: str) -> PlaybookResolution:
        held_back = self._catalogue.held_back_reason(key)
        if held_back is not None:
            return PlaybookResolution(key=key, playbook=None, held_back_reason=held_back)

        touchpoints = {tp.reference: tp for tp in await self._lookup.list_touchpoints()}
        return PlaybookResolution(key=key, playbook=resolve(self._catalogue, key, touchpoints))
