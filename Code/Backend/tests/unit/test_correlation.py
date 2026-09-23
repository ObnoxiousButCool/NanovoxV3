"""Correlation ID context: bound per request, and a sensible default outside one."""

from __future__ import annotations

import logging

from infrastructure.logging.correlation import (
    CorrelationIdFilter,
    get_correlation_id,
    new_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)


def test_no_correlation_id_bound_outside_a_request() -> None:
    assert get_correlation_id() is None


def test_set_and_reset_round_trips() -> None:
    token = set_correlation_id("abc123")
    try:
        assert get_correlation_id() == "abc123"
    finally:
        reset_correlation_id(token)

    assert get_correlation_id() is None


def test_new_correlation_id_is_unique() -> None:
    assert new_correlation_id() != new_correlation_id()


def test_filter_stamps_the_unset_marker_with_no_bound_id() -> None:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "message", None, None)

    accepted = CorrelationIdFilter().filter(record)

    assert accepted
    # correlation_id is stamped onto the record by the filter, not a stdlib
    # LogRecord attribute, so mypy doesn't know about it statically.
    assert record.correlation_id == "-"  # type: ignore[attr-defined]


def test_filter_stamps_the_bound_id() -> None:
    token = set_correlation_id("trace-me")
    try:
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "message", None, None)
        CorrelationIdFilter().filter(record)
        assert record.correlation_id == "trace-me"  # type: ignore[attr-defined]
    finally:
        reset_correlation_id(token)
