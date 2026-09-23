"""Port for reading back the reference data Phase 1 imported.

Caller and agent resolution both go through this — never by trusting the
transcript's own header text as fact. An agent reference that isn't among
the 20 imported agents, or a caller reference that isn't a known member or
employer contact, resolves to `None`, not a guess.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.entities.agent import Agent
from domain.entities.employer_contact import EmployerContact
from domain.entities.member import Member


class ReferenceLookup(ABC):
    @abstractmethod
    async def find_agent(self, reference: str) -> Agent | None: ...

    @abstractmethod
    async def find_member(self, reference: str) -> Member | None: ...

    @abstractmethod
    async def find_employer_contact(self, reference: str) -> EmployerContact | None: ...
