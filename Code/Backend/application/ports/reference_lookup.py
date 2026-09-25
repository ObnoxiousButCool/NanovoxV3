"""Port for reading back the reference data Phase 1 imported.

Caller and agent resolution both go through this — never by trusting the
transcript's own header text as fact. An agent reference that isn't among
the 20 imported agents, or a caller reference that isn't a known member or
employer contact, resolves to `None`, not a guess.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.entities.agent import Agent
from domain.entities.broker import Broker
from domain.entities.employer import Employer
from domain.entities.employer_contact import EmployerContact
from domain.entities.member import Member
from domain.entities.rule import Rule
from domain.entities.touchpoint import Touchpoint


class ReferenceLookup(ABC):
    @abstractmethod
    async def find_agent(self, reference: str) -> Agent | None: ...

    @abstractmethod
    async def find_member(self, reference: str) -> Member | None: ...

    @abstractmethod
    async def find_employer_contact(self, reference: str) -> EmployerContact | None: ...

    @abstractmethod
    async def find_employer(self, reference: str) -> Employer | None: ...

    @abstractmethod
    async def list_brokers(self) -> tuple[Broker, ...]:
        """Every known broker — L1's `broker_named_aloud` candidate scan
        checks a caller's words against all of them, not just the
        employer's own broker of record (Data Model sheet: a mismatch
        between the two is itself a finding, not something to search
        around)."""

    @abstractmethod
    async def list_rules(self) -> tuple[Rule, ...]:
        """Every known rule — L3/L4 are shown only the subset
        `domain.extraction.rule_scoping.scope_rules` selects for a call's
        category and product lines (plan §7, "never all 122")."""

    @abstractmethod
    async def list_touchpoints(self) -> tuple[Touchpoint, ...]:
        """Every Touchpoints-sheet row. A `tp_<touchpoint>` playbook key
        resolves only for a touchpoint here, with its owner and controls."""
