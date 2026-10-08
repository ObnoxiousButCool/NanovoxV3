"""Password hashing: deterministic verification over a randomised hash."""

from __future__ import annotations

from domain.value_objects.password_hash import hash_password, password_matches


def test_a_matching_password_is_accepted() -> None:
    hashed = hash_password("Tech@2026")

    assert password_matches("Tech@2026", hashed=hashed)


def test_a_wrong_password_is_rejected() -> None:
    hashed = hash_password("Tech@2026")

    assert not password_matches("wrong-password", hashed=hashed)


def test_hashing_the_same_password_twice_produces_different_hashes() -> None:
    # A random salt per call — two readers who happened to share a password
    # must not be discoverable by comparing stored hashes.
    assert hash_password("Tech@2026") != hash_password("Tech@2026")


def test_both_hashes_of_the_same_password_still_verify() -> None:
    first = hash_password("Tech@2026")
    second = hash_password("Tech@2026")

    assert password_matches("Tech@2026", hashed=first)
    assert password_matches("Tech@2026", hashed=second)


def test_a_malformed_stored_hash_fails_closed() -> None:
    assert not password_matches("Tech@2026", hashed="not-a-valid-hash")


def test_an_empty_stored_hash_fails_closed() -> None:
    assert not password_matches("", hashed="")
