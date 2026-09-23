"""Loading `config/dashboard.yaml`, and refusing to load a broken one.

The validation is the point of these tests. A dashboard config does not fail
loudly when it is wrong — it publishes. A `min_n` that quietly read as None
would turn a gated figure into an ungated one and nothing downstream could
tell, so every one of these cases has to raise rather than default.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from domain.errors import ConfigurationError
from infrastructure.config.dashboard_config import (
    get_dashboard_config,
    load_dashboard_config,
)
from infrastructure.config.paths import DEFAULT_CONFIG_DIR
from infrastructure.config.settings import get_settings

VALID = """
version: "1.0.0"
metrics:
  - key: contact_rate
    sheet_row: "1"
    name: Contact rate
    window_weeks: 12
    min_n: 30
    counts: calls
  - key: agent_quality_score
    sheet_row: "12"
    name: Agent quality score
    window_weeks: null
    min_n: null
    counts: calls
cost_per_call: null
peer_size_bands:
  - label: "2-24 lives"
    min_lives: 2
    max_lives: 24
  - label: "25+ lives"
    min_lives: 25
    max_lives: null
broker:
  ranking_floor_lives: 150
  pattern_test:
    min_adverse_mentions: 3
    min_distinct_employers: 2
    window_weeks: 12
quality_bands:
  good_min: 86
  average_min: 60
risk_flag:
  eligibility_min_calls: 3
  flag_threshold: 2
  quote_min_calls: 10
"""


@pytest.fixture(autouse=True)
def _isolated_caches() -> Iterator[None]:
    get_settings.cache_clear()
    get_dashboard_config.cache_clear()
    yield
    get_settings.cache_clear()
    get_dashboard_config.cache_clear()


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "dashboard.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _broken(tmp_path: Path, old: str, new: str) -> Path:
    assert old in VALID, f"the fixture no longer contains {old!r}"
    return _write(tmp_path, VALID.replace(old, new))


def _refusal(path: Path) -> str:
    """The reason a config was refused, as a plain string.

    Read from `detail`, not from the message. This codebase keeps the
    message generic and puts the specifics in `detail`, because
    `frameworks_drivers/api/errors.py` surfaces the message to HTTP clients
    and suppresses the detail -- which is what stops a bad DATABASE_URL
    putting a connection string in a response body. The reason still has to
    be right and actionable, so it is what every refusal below asserts on.
    """
    with pytest.raises(ConfigurationError) as raised:
        load_dashboard_config(path)
    detail = raised.value.detail
    assert detail is not None, "a refusal has to say why"
    return detail


def test_a_valid_document_loads(tmp_path: Path) -> None:
    config = load_dashboard_config(_write(tmp_path, VALID))

    assert config.version == "1.0.0"
    assert config.metric("contact_rate").min_n == 30
    assert config.metric("agent_quality_score").min_n is None
    assert config.cost_per_call is None
    assert config.broker_ranking_floor_lives == 150


def test_metrics_keep_the_sheets_order(tmp_path: Path) -> None:
    """Ordered like the Metrics sheet so a diff of the config reads like a
    diff of the workbook.
    """
    config = load_dashboard_config(_write(tmp_path, VALID))

    assert [metric.sheet_row for metric in config.metrics] == ["1", "12"]


# --- Refusals --------------------------------------------------------------


def test_a_missing_file_is_refused_and_names_the_path(tmp_path: Path) -> None:
    """The path is the whole answer here: an absent config almost always
    means the process is running from somewhere other than where it thinks.
    """
    absent = tmp_path / "absent.yaml"

    detail = _refusal(absent)

    assert "could not be read" in detail
    assert "absent.yaml" in detail


def test_invalid_yaml_is_refused(tmp_path: Path) -> None:
    assert "not valid YAML" in _refusal(_write(tmp_path, "version: [unclosed\n"))


def test_a_missing_top_level_block_is_refused(tmp_path: Path) -> None:
    text = VALID.replace("risk_flag:\n  eligibility_min_calls: 3\n", "")
    assert "missing risk_flag" in _refusal(_write(tmp_path, text))


def test_an_unknown_top_level_block_is_refused(tmp_path: Path) -> None:
    """A block named `quality_band` would otherwise sit in the file looking
    configured while the code read `quality_bands` and its own defaults.
    """
    assert "unknown key(s) min_n" in _refusal(_write(tmp_path, VALID + "min_n: 5\n"))


def test_a_metric_missing_min_n_is_refused_rather_than_defaulted(tmp_path: Path) -> None:
    """Absent is not null. `min_n: null` says "never withheld" deliberately;
    an omitted key is someone forgetting, and the two must not look alike.
    """
    text = VALID.replace("    min_n: 30\n", "")
    assert "metrics[0]: missing min_n" in _refusal(_write(tmp_path, text))


def test_a_duplicate_metric_key_is_refused(tmp_path: Path) -> None:
    """`metric()` returns the first match, so a duplicate would silently
    shadow whichever entry was edited second.
    """
    path = _broken(tmp_path, "key: agent_quality_score", "key: contact_rate")
    assert "duplicate key(s) contact_rate" in _refusal(path)


def test_a_boolean_where_a_number_belongs_is_refused(tmp_path: Path) -> None:
    """`bool` is an `int` subclass, so `min_n: true` would otherwise load as
    a min n of 1 — an effectively ungated metric.
    """
    assert "expected a whole number" in _refusal(_broken(tmp_path, "min_n: 30", "min_n: true"))


def test_a_gap_between_peer_bands_is_refused(tmp_path: Path) -> None:
    """Not tidiness: employers in the gap have no peer group at all, so
    their account page silently loses its comparison.
    """
    path = _broken(
        tmp_path, "min_lives: 25\n    max_lives: null", "min_lives: 30\n    max_lives: null"
    )
    assert "must be contiguous" in _refusal(path)


def test_a_closed_top_band_is_refused(tmp_path: Path) -> None:
    """The largest employers must land somewhere. A closed top band drops
    every group above it out of peer comparison entirely.
    """
    path = _broken(
        tmp_path, "min_lives: 25\n    max_lives: null", "min_lives: 25\n    max_lives: 999"
    )
    assert "must be open-ended" in _refusal(path)


def test_overlapping_quality_bands_are_refused(tmp_path: Path) -> None:
    assert "must be below" in _refusal(_broken(tmp_path, "average_min: 60", "average_min: 90"))


def test_quoting_below_eligibility_is_refused(tmp_path: Path) -> None:
    """An employer quotable before it is eligible is a contradiction the two
    numbers cannot express, and metric 10's own denominator rules out.
    """
    path = _broken(tmp_path, "quote_min_calls: 10", "quote_min_calls: 2")
    assert "before it is eligible" in _refusal(path)


def test_a_placeholder_cost_per_call_of_zero_is_refused(tmp_path: Path) -> None:
    """D4: null or a real number. Zero is the placeholder that makes every
    money figure render as free.
    """
    assert "positive number or null" in _refusal(
        _broken(tmp_path, "cost_per_call: null", "cost_per_call: 0")
    )


def test_a_real_cost_per_call_loads(tmp_path: Path) -> None:
    config = load_dashboard_config(_broken(tmp_path, "cost_per_call: null", "cost_per_call: 4.75"))

    assert config.cost_per_call == pytest.approx(4.75)
    assert config.money_withheld is False


def test_a_non_numeric_cost_per_call_is_refused(tmp_path: Path) -> None:
    """Including a string that looks like money. "$4.75" would load as a
    truthy value and make `money_withheld` False with nothing to multiply.
    """
    path = _broken(tmp_path, "cost_per_call: null", 'cost_per_call: "$4.75"')
    assert "expected a number or null" in _refusal(path)


# --- Shapes, rather than values --------------------------------------------
#
# Each of these is a way the file can be malformed rather than mistuned. They
# matter for the same reason the value checks do: YAML is permissive, and a
# block that parses into the wrong Python type would otherwise reach the
# dataclasses and fail somewhere with no connection to the file.


def test_a_document_that_is_not_a_mapping_is_refused(tmp_path: Path) -> None:
    assert "expected a mapping" in _refusal(_write(tmp_path, "- just\n- a list\n"))


def test_a_metric_entry_that_is_not_a_mapping_is_refused(tmp_path: Path) -> None:
    text = (
        VALID[: VALID.index("metrics:")]
        + "metrics:\n  - contact_rate\n"
        + VALID[VALID.index("cost_per_call:") :]
    )
    assert "metrics[0]: expected a mapping" in _refusal(_write(tmp_path, text))


def test_metrics_that_are_not_a_list_are_refused(tmp_path: Path) -> None:
    text = (
        VALID[: VALID.index("metrics:")] + "metrics: {}\n" + VALID[VALID.index("cost_per_call:") :]
    )
    assert "expected a non-empty list" in _refusal(_write(tmp_path, text))


def test_peer_size_bands_that_are_not_a_list_are_refused(tmp_path: Path) -> None:
    text = (
        VALID[: VALID.index("peer_size_bands:")]
        + "peer_size_bands: []\n"
        + VALID[VALID.index("broker:") :]
    )
    assert "expected a non-empty list" in _refusal(_write(tmp_path, text))


def test_an_empty_name_is_refused(tmp_path: Path) -> None:
    """Whitespace is not a name. These strings are what a reader sees beside
    a withheld figure, so a blank one is a panel that cannot explain itself.
    """
    path = _broken(tmp_path, "name: Contact rate", 'name: "  "')
    assert "expected a non-empty string" in _refusal(path)


def test_a_threshold_of_zero_is_refused(tmp_path: Path) -> None:
    """`min_n: 0` is not "no threshold" — `min_n: null` says that
    deliberately. Zero would read as a gate while gating nothing.
    """
    assert "expected at least 1" in _refusal(_broken(tmp_path, "min_n: 30", "min_n: 0"))


def test_a_band_whose_ceiling_is_below_its_floor_is_refused(tmp_path: Path) -> None:
    path = _broken(tmp_path, "min_lives: 2\n    max_lives: 24", "min_lives: 20\n    max_lives: 4")
    assert "is below min_lives" in _refusal(path)


def test_an_open_ended_band_before_the_last_is_refused(tmp_path: Path) -> None:
    """An open-ended band in the middle swallows every employer above its
    floor, so the bands after it are never reached and never say so.
    """
    path = _broken(tmp_path, "min_lives: 2\n    max_lives: 24", "min_lives: 2\n    max_lives: null")
    assert "only the last band may be open-ended" in _refusal(path)


# --- The shipped file ------------------------------------------------------


def test_the_shipped_config_loads_and_is_what_settings_points_at() -> None:
    """The file this repository ships, through the path settings resolves —
    not a fixture. A config that only ever loads in a test is not loaded.
    """
    assert get_settings().dashboard_config_path == DEFAULT_CONFIG_DIR / "dashboard.yaml"

    config = get_dashboard_config()

    assert config.metric("escalation_integrity").counts == "triggers"
    assert config.risk_flag.eligibility_min_calls == 3
    assert config.money_withheld is True
    assert config is get_dashboard_config(), "the config is cached, not re-read per call"
