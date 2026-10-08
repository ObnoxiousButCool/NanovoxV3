"""The allowlist's matching rule: case- and whitespace-insensitive."""

from __future__ import annotations

from domain.value_objects.approved_emails import approved_emails_from


def test_an_approved_address_matches_exactly() -> None:
    allowlist = approved_emails_from(["reader@example.com"])

    assert allowlist.is_approved("reader@example.com")


def test_matching_ignores_case() -> None:
    allowlist = approved_emails_from(["Reader@Example.com"])

    assert allowlist.is_approved("reader@example.com")
    assert allowlist.is_approved("READER@EXAMPLE.COM")


def test_matching_ignores_surrounding_whitespace() -> None:
    allowlist = approved_emails_from(["reader@example.com"])

    assert allowlist.is_approved("  reader@example.com  ")


def test_an_unlisted_address_does_not_match() -> None:
    allowlist = approved_emails_from(["reader@example.com"])

    assert not allowlist.is_approved("stranger@example.com")


def test_an_empty_list_approves_nobody() -> None:
    allowlist = approved_emails_from([])

    assert not allowlist.is_approved("reader@example.com")
