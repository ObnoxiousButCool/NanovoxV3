"""The domain error hierarchy carries a message, an optional detail and a stable code."""

from __future__ import annotations

import pytest

from domain.errors import (
    ConfigurationError,
    ConflictError,
    DependencyUnavailableError,
    NanoVoxInsightsError,
    NotFoundError,
    ValidationError,
)


@pytest.mark.parametrize(
    ("error_type", "code"),
    [
        (NanoVoxInsightsError, "nanovox_insights_error"),
        (ConfigurationError, "configuration_error"),
        (ValidationError, "validation_error"),
        (NotFoundError, "not_found"),
        (ConflictError, "conflict"),
        (DependencyUnavailableError, "dependency_unavailable"),
    ],
)
def test_carries_message_detail_and_its_own_code(
    error_type: type[NanoVoxInsightsError], code: str
) -> None:
    error = error_type("something went wrong", detail="more context")

    assert error.message == "something went wrong"
    assert error.detail == "more context"
    assert error.code == code
    assert str(error) == "something went wrong"


def test_detail_defaults_to_none() -> None:
    error = ValidationError("bad input")

    assert error.detail is None
