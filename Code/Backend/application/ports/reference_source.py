"""Port for reading the workbook's master-data sheets into domain entities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from domain.entities.agent import Agent
from domain.entities.broker import Broker
from domain.entities.employer import Employer
from domain.entities.employer_contact import EmployerContact
from domain.entities.member import Member
from domain.entities.rule import Rule
from domain.entities.touchpoint import Touchpoint


@dataclass(frozen=True)
class ReferenceDataset:
    """Every reference entity read from one workbook, plus non-fatal warnings.

    Warnings (e.g. a row that didn't match any known reference pattern, or a
    missing premium lever) are collected rather than raised, so one bad row
    doesn't abort an otherwise-good import — the caller decides what to do
    with them (plan §8 Phase 1: "returns counts and warnings").
    """

    brokers: tuple[Broker, ...] = field(default_factory=tuple)
    employers: tuple[Employer, ...] = field(default_factory=tuple)
    members: tuple[Member, ...] = field(default_factory=tuple)
    employer_contacts: tuple[EmployerContact, ...] = field(default_factory=tuple)
    agents: tuple[Agent, ...] = field(default_factory=tuple)
    rules: tuple[Rule, ...] = field(default_factory=tuple)
    touchpoints: tuple[Touchpoint, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)


class ReferenceSource(ABC):
    """Reads the build-bible workbook's master-data sheets."""

    @abstractmethod
    def read(self) -> ReferenceDataset:
        """Parse the workbook into a `ReferenceDataset`.

        Synchronous and CPU-bound (local file, in-memory XML parsing) rather
        than async — this is a rare admin operation, not a request-path
        call, and the use case that calls it is free to run it in a thread
        if it ever needs to.
        """
