"""``HealthReport`` decides what "healthy" means; the transport layer only reads it."""

from __future__ import annotations

from datetime import datetime, timezone

from domain.value_objects.health import ComponentHealth, ComponentStatus, HealthReport

_NOW = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)


def test_healthy_when_every_component_is_up() -> None:
    report = HealthReport(
        components=(
            ComponentHealth("database", ComponentStatus.UP),
            ComponentHealth("cache", ComponentStatus.UP),
        ),
        checked_at=_NOW,
    )

    assert report.is_healthy
    assert report.status is ComponentStatus.UP


def test_unhealthy_when_any_component_is_down() -> None:
    report = HealthReport(
        components=(
            ComponentHealth("database", ComponentStatus.UP),
            ComponentHealth("cache", ComponentStatus.DOWN, detail="timeout"),
        ),
        checked_at=_NOW,
    )

    assert not report.is_healthy
    assert report.status is ComponentStatus.DOWN


def test_healthy_with_no_components_claimed() -> None:
    report = HealthReport(components=(), checked_at=_NOW)

    assert report.is_healthy
