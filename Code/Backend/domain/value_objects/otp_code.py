"""The six-digit OTP: how one is generated and how it is checked.

Generated with `secrets`, not `random` — a login code is a credential, and
`random` is predictable enough to guess from its own output. Checked with
`hmac.compare_digest` for the same reason a password hash is: a `==` on the
stored hash would return in a different number of microseconds depending on
how many leading bytes matched, which is a side channel an attacker can time.

Only the hash is ever persisted. The plaintext code exists for the seconds
between generation and sending, and nowhere after.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_LENGTH = 6
_FLOOR = 10 ** (_LENGTH - 1)
_CEILING = (10**_LENGTH) - 1


def generate_otp_code() -> str:
    """A fresh six-digit code, zero-padded, from a cryptographic RNG."""
    return str(secrets.randbelow(_CEILING - _FLOOR + 1) + _FLOOR)


def hash_otp_code(code: str) -> str:
    """A salt-free digest of a short-lived, single-use, six-digit secret.

    Unlike a password, this hash protects a value that is random (not
    guessable from a dictionary), expires in minutes and is invalidated after
    one use — the properties a slow, salted KDF exists for a password because
    it lacks. A fast hash here is the exchange that `sha256` already is, not
    a shortcut.
    """
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def otp_code_matches(code: str, *, hashed: str) -> bool:
    """Constant-time comparison of a submitted code against its stored hash."""
    return hmac.compare_digest(hash_otp_code(code), hashed)
