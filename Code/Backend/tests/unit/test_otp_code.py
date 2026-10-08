"""The OTP code's generation, hashing and comparison."""

from __future__ import annotations

from domain.value_objects.otp_code import generate_otp_code, hash_otp_code, otp_code_matches


def test_a_generated_code_is_six_digits() -> None:
    code = generate_otp_code()

    assert len(code) == 6
    assert code.isdigit()


def test_generated_codes_are_not_all_the_same() -> None:
    # Not a statistical test of the RNG — just a guard against a constant
    # or an off-by-one range that always produces the same leading digit.
    codes = {generate_otp_code() for _ in range(50)}

    assert len(codes) > 1


def test_hashing_is_deterministic() -> None:
    assert hash_otp_code("123456") == hash_otp_code("123456")


def test_different_codes_hash_differently() -> None:
    assert hash_otp_code("123456") != hash_otp_code("654321")


def test_a_matching_code_is_accepted() -> None:
    hashed = hash_otp_code("482913")

    assert otp_code_matches("482913", hashed=hashed)


def test_a_wrong_code_is_rejected() -> None:
    hashed = hash_otp_code("482913")

    assert not otp_code_matches("000000", hashed=hashed)
