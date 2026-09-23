"""Read `config/dashboard.yaml` into `domain.dashboard_config.DashboardConfig`.

Validated eagerly and strictly, for the same reason `settings.py` is: a bad
threshold does not fail, it publishes. A missing `min_n` read as None would
turn a gated figure into an ungated one silently, and nothing downstream
would have any way to notice — so an absent key is an error here, never a
default.

Unknown keys are errors too. A block named `quality_band` instead of
`quality_bands` would otherwise sit in the file looking configured while the
code used something else entirely.
"""

from __future__ import annotations

from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from typing import Any

import yaml

from domain.dashboard_config import (
    BrokerPatternTest,
    DashboardConfig,
    MetricThreshold,
    PeerSizeBand,
    QualityBands,
    RiskFlagConfig,
)
from domain.errors import ConfigurationError
from infrastructure.config.settings import get_settings

_METRIC_KEYS = frozenset({"key", "sheet_row", "name", "window_weeks", "min_n", "counts"})
_BAND_KEYS = frozenset({"label", "min_lives", "max_lives"})
_TOP_LEVEL_KEYS = frozenset(
    {
        "version",
        "metrics",
        "cost_per_call",
        "peer_size_bands",
        "broker",
        "quality_bands",
        "risk_flag",
    }
)


def _fail(detail: str, path: Path) -> ConfigurationError:
    return ConfigurationError(
        f"Invalid dashboard configuration in {path} — the application cannot start.",
        detail=detail,
    )


def _mapping(value: object, where: str, path: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail(f"{where}: expected a mapping, found {type(value).__name__}", path)
    return value


def _exact_keys(block: dict[str, Any], expected: frozenset[str], where: str, path: Path) -> None:
    missing = sorted(expected - block.keys())
    unknown = sorted(block.keys() - expected)
    if missing:
        raise _fail(f"{where}: missing {', '.join(missing)}", path)
    if unknown:
        raise _fail(f"{where}: unknown key(s) {', '.join(unknown)}", path)


def _int(block: dict[str, Any], key: str, where: str, path: Path, *, minimum: int = 1) -> int:
    value = block[key]
    # bool is an int subclass, and `min_n: true` is a typo worth catching.
    if not isinstance(value, int) or isinstance(value, bool):
        raise _fail(f"{where}.{key}: expected a whole number, found {value!r}", path)
    if value < minimum:
        raise _fail(f"{where}.{key}: expected at least {minimum}, found {value}", path)
    return value


def _optional_int(block: dict[str, Any], key: str, where: str, path: Path) -> int | None:
    if block[key] is None:
        return None
    return _int(block, key, where, path)


def _str(block: dict[str, Any], key: str, where: str, path: Path) -> str:
    value = block[key]
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"{where}.{key}: expected a non-empty string, found {value!r}", path)
    return value


def _metric(raw: object, index: int, path: Path) -> MetricThreshold:
    where = f"metrics[{index}]"
    block = _mapping(raw, where, path)
    _exact_keys(block, _METRIC_KEYS, where, path)
    return MetricThreshold(
        key=_str(block, "key", where, path),
        sheet_row=_str(block, "sheet_row", where, path),
        name=_str(block, "name", where, path),
        window_weeks=_optional_int(block, "window_weeks", where, path),
        min_n=_optional_int(block, "min_n", where, path),
        counts=_str(block, "counts", where, path),
    )


def _metrics(raw: object, path: Path) -> tuple[MetricThreshold, ...]:
    if not isinstance(raw, list) or not raw:
        raise _fail("metrics: expected a non-empty list", path)
    metrics = tuple(_metric(entry, index, path) for index, entry in enumerate(raw))
    keys = [metric.key for metric in metrics]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise _fail(f"metrics: duplicate key(s) {', '.join(duplicates)}", path)
    return metrics


def _size_band(raw: object, index: int, path: Path) -> PeerSizeBand:
    where = f"peer_size_bands[{index}]"
    block = _mapping(raw, where, path)
    _exact_keys(block, _BAND_KEYS, where, path)
    band = PeerSizeBand(
        label=_str(block, "label", where, path),
        min_lives=_int(block, "min_lives", where, path),
        max_lives=_optional_int(block, "max_lives", where, path),
    )
    if band.max_lives is not None and band.max_lives < band.min_lives:
        raise _fail(
            f"{where}: max_lives {band.max_lives} is below min_lives {band.min_lives}", path
        )
    return band


def _size_bands(raw: object, path: Path) -> tuple[PeerSizeBand, ...]:
    if not isinstance(raw, list) or not raw:
        raise _fail("peer_size_bands: expected a non-empty list", path)
    bands = tuple(_size_band(entry, index, path) for index, entry in enumerate(raw))
    # Contiguous and ascending, checked rather than assumed: a gap between two
    # bands is not a validation nicety, it is a set of employers that silently
    # have no peer group and therefore no comparison on the account page.
    for lower, upper in pairwise(bands):
        if lower.max_lives is None:
            raise _fail("peer_size_bands: only the last band may be open-ended", path)
        if upper.min_lives != lower.max_lives + 1:
            raise _fail(
                f"peer_size_bands: {lower.label} ends at {lower.max_lives} but "
                f"{upper.label} starts at {upper.min_lives} — bands must be contiguous",
                path,
            )
    if bands[-1].max_lives is not None:
        raise _fail("peer_size_bands: the last band must be open-ended (max_lives: null)", path)
    return bands


def _broker(raw: object, path: Path) -> tuple[int, BrokerPatternTest]:
    block = _mapping(raw, "broker", path)
    _exact_keys(block, frozenset({"ranking_floor_lives", "pattern_test"}), "broker", path)
    test = _mapping(block["pattern_test"], "broker.pattern_test", path)
    _exact_keys(
        test,
        frozenset({"min_adverse_mentions", "min_distinct_employers", "window_weeks"}),
        "broker.pattern_test",
        path,
    )
    return (
        _int(block, "ranking_floor_lives", "broker", path),
        BrokerPatternTest(
            min_adverse_mentions=_int(test, "min_adverse_mentions", "broker.pattern_test", path),
            min_distinct_employers=_int(
                test, "min_distinct_employers", "broker.pattern_test", path
            ),
            window_weeks=_int(test, "window_weeks", "broker.pattern_test", path),
        ),
    )


def _quality_bands(raw: object, path: Path) -> QualityBands:
    block = _mapping(raw, "quality_bands", path)
    _exact_keys(block, frozenset({"good_min", "average_min"}), "quality_bands", path)
    bands = QualityBands(
        good_min=_int(block, "good_min", "quality_bands", path),
        average_min=_int(block, "average_min", "quality_bands", path),
    )
    if bands.average_min >= bands.good_min:
        raise _fail(
            f"quality_bands: average_min {bands.average_min} must be below "
            f"good_min {bands.good_min}",
            path,
        )
    return bands


def _risk_flag(raw: object, path: Path) -> RiskFlagConfig:
    block = _mapping(raw, "risk_flag", path)
    _exact_keys(
        block,
        frozenset({"eligibility_min_calls", "flag_threshold", "quote_min_calls"}),
        "risk_flag",
        path,
    )
    flag = RiskFlagConfig(
        eligibility_min_calls=_int(block, "eligibility_min_calls", "risk_flag", path),
        flag_threshold=_int(block, "flag_threshold", "risk_flag", path),
        quote_min_calls=_int(block, "quote_min_calls", "risk_flag", path),
    )
    if flag.quote_min_calls < flag.eligibility_min_calls:
        raise _fail(
            f"risk_flag: quote_min_calls {flag.quote_min_calls} is below "
            f"eligibility_min_calls {flag.eligibility_min_calls} — an employer would be "
            "quotable before it is eligible",
            path,
        )
    return flag


def _cost_per_call(raw: object, path: Path) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise _fail(f"cost_per_call: expected a number or null, found {raw!r}", path)
    if raw <= 0:
        raise _fail(f"cost_per_call: expected a positive number or null, found {raw}", path)
    return float(raw)


def load_dashboard_config(path: Path) -> DashboardConfig:
    """Parse and validate the dashboard config at `path`."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise _fail(f"could not be read: {exc}", path) from exc

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise _fail(f"is not valid YAML: {exc}", path) from exc

    block = _mapping(document, "the document", path)
    _exact_keys(block, _TOP_LEVEL_KEYS, "the document", path)

    ranking_floor, pattern_test = _broker(block["broker"], path)
    return DashboardConfig(
        version=_str(block, "version", "the document", path),
        metrics=_metrics(block["metrics"], path),
        cost_per_call=_cost_per_call(block["cost_per_call"], path),
        peer_size_bands=_size_bands(block["peer_size_bands"], path),
        broker_ranking_floor_lives=ranking_floor,
        broker_pattern_test=pattern_test,
        quality_bands=_quality_bands(block["quality_bands"], path),
        risk_flag=_risk_flag(block["risk_flag"], path),
    )


@lru_cache(maxsize=1)
def get_dashboard_config() -> DashboardConfig:
    """Load and cache the dashboard config named by settings.

    Cached like `get_settings`: the thresholds are immutable for the lifetime
    of the process, and re-reading the file per request would let a figure
    published at the top of a page disagree with one at the bottom. Tests
    clear the cache explicitly.
    """
    return load_dashboard_config(get_settings().dashboard_config_path)
