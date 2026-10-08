"""Read `config/approved_emails.yaml` into `domain.value_objects.ApprovedEmails`.

Strict, like the other config loaders: an entry that is not a string is an
error, not something silently skipped and forgotten about.
"""

from __future__ import annotations

from pathlib import Path

from domain.errors import ConfigurationError
from domain.value_objects.approved_emails import ApprovedEmails, approved_emails_from
from infrastructure.config.yaml_support import YamlReader, load_yaml_mapping

_SOURCE = "approved_emails.yaml"
_TOP_LEVEL = frozenset({"emails"})


def load_approved_emails(path: Path) -> ApprovedEmails:
    raw = load_yaml_mapping(path, description="Approved emails")
    unknown = sorted(set(raw) - _TOP_LEVEL)
    if unknown:
        raise ConfigurationError(f"{_SOURCE}: the document has unknown keys {unknown}.")

    document = YamlReader(raw, source=_SOURCE)
    entries = document.require("emails")
    if not isinstance(entries, list):
        raise ConfigurationError(f"{_SOURCE}: emails must be a list.")

    addresses: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, str) or not entry.strip():
            raise ConfigurationError(
                f"{_SOURCE}: emails[{index}] must be a non-empty string.", detail=f"Got {entry!r}."
            )
        addresses.append(entry)

    return approved_emails_from(addresses)
