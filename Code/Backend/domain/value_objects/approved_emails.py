"""The allowlist an email must be on to receive an OTP or sign in.

A static list, not a user table: the product the client was told about has
no self-service signup, and the small, slow-changing set of approved
contacts is a config file a developer edits and redeploys, like
`action_lifecycle.yaml` and `dashboard.yaml` already are — not a feature of
its own until someone needs to manage it without a developer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApprovedEmails:
    """A case- and whitespace-insensitive set of approved addresses."""

    _addresses: frozenset[str]

    def is_approved(self, email: str) -> bool:
        return _normalise(email) in self._addresses


def _normalise(email: str) -> str:
    return email.strip().lower()


def approved_emails_from(addresses: list[str]) -> ApprovedEmails:
    return ApprovedEmails(frozenset(_normalise(address) for address in addresses))
