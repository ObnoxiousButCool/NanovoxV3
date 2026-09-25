"""The shipped `config/playbooks.yaml` is complete (Revised plan Phase 4, I3).

The completeness test mirrors `test_insights_labels.py`: a key with no steps
or no owner renders as an empty panel, which reads as "nothing to do" rather
than "we forgot to write this", so it has to fail in CI instead.
"""

from __future__ import annotations

import pytest

from domain.playbooks import PlaybookCatalogue, resolve
from domain.value_objects.category import Category
from domain.value_objects.product_line import ProductLine
from domain.value_objects.signal_type import SignalType, owner_team_of
from infrastructure.config.paths import DEFAULT_CONFIG_DIR
from infrastructure.config.playbook_loader import load_playbooks


@pytest.fixture(scope="module")
def catalogue() -> PlaybookCatalogue:
    return load_playbooks(DEFAULT_CONFIG_DIR / "playbooks.yaml")


def test_every_playbook_has_steps_and_an_owner(catalogue: PlaybookCatalogue) -> None:
    for playbook in catalogue.playbooks:
        assert playbook.steps, playbook.key
        assert playbook.owner_team.strip(), playbook.key


def test_the_steps_are_marked_unreviewed(catalogue: PlaybookCatalogue) -> None:
    """R7: the prototype's steps are generic and the owning teams have not
    reviewed them. Flipping this is a decision, not an edit."""
    assert catalogue.reviewed is False
    assert "not been reviewed" in catalogue.review_note


@pytest.mark.parametrize("category", list(Category), ids=lambda c: c.name)
def test_every_category_key_resolves(catalogue: PlaybookCatalogue, category: Category) -> None:
    assert resolve(catalogue, f"cat_{category.value}", {}) is not None


@pytest.mark.parametrize("signal", list(SignalType), ids=lambda s: s.name)
def test_every_signal_key_resolves_to_its_taxonomy_owner(
    catalogue: PlaybookCatalogue, signal: SignalType
) -> None:
    playbook = resolve(catalogue, f"sig_{signal.value}", {})

    assert playbook is not None
    assert playbook.owner_team == owner_team_of(signal)


@pytest.mark.parametrize("line", list(ProductLine), ids=lambda p: p.name)
def test_every_product_line_key_resolves(catalogue: PlaybookCatalogue, line: ProductLine) -> None:
    assert resolve(catalogue, f"pl_{line.value}", {}) is not None


def test_dynamic_templates_fill_every_placeholder(catalogue: PlaybookCatalogue) -> None:
    """A template naming a placeholder the resolver does not supply would
    raise at request time; resolving one of each kind proves it cannot."""
    for key in ("cat_Claims & EOB", "sig_billing_defect", "pl_dental"):
        playbook = resolve(catalogue, key, {})
        assert playbook is not None
        assert "{" not in playbook.meaning + playbook.why + "".join(playbook.steps)


def test_d12_wording_the_flag_is_metric_10(catalogue: PlaybookCatalogue) -> None:
    """D12: "flagged" means metric 10 and nothing else. The prototype's
    wording counted indicator families instead."""
    for key in ("flagged", "renew_soon", "unowned"):
        playbook = catalogue.static(key)
        assert playbook is not None
        assert "metric 10" in playbook.meaning, key


def test_the_held_back_keys_are_the_decided_ones(catalogue: PlaybookCatalogue) -> None:
    held = {entry.key: entry.reason for entry in catalogue.held_back}

    assert set(held) == {"high", "brush_off", "circular"}
    assert "D12" in held["high"]
    assert "C8a" in held["brush_off"] and "C8a" in held["circular"]
