"""Loading `config/rubric.yaml`: the real file loads cleanly, and a
malformed one fails with a message naming exactly what's wrong."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.errors import ConfigurationError
from domain.scoring.rubric import GateCondition, GateEffect
from infrastructure.config.rubric_loader import load_rubric

REAL_RUBRIC = Path(__file__).resolve().parents[2] / "config" / "rubric.yaml"

MINIMAL = """
version: "1.0.0"
base_score: 100
max_positive_offset: 15
dimensions:
  empathy:
    label: Empathy
    positive: 3
    negative: 8
    max_positive: 9
    max_negative: 24
tiers:
  good: 86
  average: 60
min_calls_for_tier_rating: 5
"""


def write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "rubric.yaml"
    path.write_text(content, encoding="utf-8")
    return path


class TestTheRealFile:
    def test_the_shipped_rubric_loads(self) -> None:
        rubric = load_rubric(REAL_RUBRIC)

        assert rubric.version == "1.0.0"

    def test_every_workbook_dimension_is_present_with_its_real_weights(self) -> None:
        # Copied verbatim from the Call Quality Framework sheet's "THE SIX
        # DIMENSIONS" table — a drift here is a drift from the workbook.
        rubric = load_rubric(REAL_RUBRIC)

        escalation = rubric.dimension("escalation_appropriateness")
        assert (escalation.positive, escalation.negative, escalation.max_negative) == (3, 20, 40)

        compliance = rubric.dimension("compliance_disclosure")
        assert (compliance.positive, compliance.negative, compliance.max_negative) == (2, 15, 45)

    def test_the_tiers_match_the_workbooks_banding(self) -> None:
        rubric = load_rubric(REAL_RUBRIC)

        assert (rubric.tiers.good, rubric.tiers.average) == (86, 60)

    def test_the_shipped_rubric_has_no_gates(self) -> None:
        # See domain/scoring/rubric.py's module docstring: the clinical
        # case needs L4's output, which L3 cannot see at scoring time.
        rubric = load_rubric(REAL_RUBRIC)

        assert rubric.gates == ()


class TestMinimalFile:
    def test_a_well_formed_minimal_file_loads(self, tmp_path: Path) -> None:
        rubric = load_rubric(write(tmp_path, MINIMAL))

        assert rubric.dimension("empathy").negative == 8

    def test_gates_are_parsed_when_present(self, tmp_path: Path) -> None:
        with_gate = (
            MINIMAL
            + """
gates:
  - id: low_score
    condition: score_below
    argument: "40"
    effect: suspend_score
    message: Review before publishing.
"""
        )

        rubric = load_rubric(write(tmp_path, with_gate))

        assert len(rubric.gates) == 1
        assert rubric.gates[0].condition is GateCondition.SCORE_BELOW
        assert rubric.gates[0].effect is GateEffect.SUSPEND_SCORE


class TestFailureModes:
    def test_a_missing_file_is_a_configuration_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="not found"):
            load_rubric(tmp_path / "absent.yaml")

    def test_invalid_yaml_is_a_configuration_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="not valid YAML"):
            load_rubric(write(tmp_path, "version: [unclosed"))

    def test_a_non_mapping_top_level_is_a_configuration_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="must contain a mapping"):
            load_rubric(write(tmp_path, "- just\n- a\n- list\n"))

    def test_a_missing_required_field_names_it(self, tmp_path: Path) -> None:
        missing_version = MINIMAL.replace('version: "1.0.0"\n', "")

        with pytest.raises(ConfigurationError, match="version"):
            load_rubric(write(tmp_path, missing_version))

    def test_an_invalid_dimension_reports_the_domain_reason(self, tmp_path: Path) -> None:
        bad_cap = MINIMAL.replace("max_negative: 24", "max_negative: 2")

        with pytest.raises(ConfigurationError, match="is invalid"):
            load_rubric(write(tmp_path, bad_cap))

    def test_a_gate_with_an_unknown_condition_names_the_allowed_values(
        self, tmp_path: Path
    ) -> None:
        bad_gate = (
            MINIMAL
            + """
gates:
  - id: low_score
    condition: not_a_real_condition
    argument: "40"
    effect: suspend_score
    message: Review.
"""
        )

        with pytest.raises(ConfigurationError, match="one of"):
            load_rubric(write(tmp_path, bad_gate))

    def test_an_empty_gates_list_is_accepted_not_an_error(self, tmp_path: Path) -> None:
        # A deliberate, real configuration (see config/rubric.yaml) — not
        # an omission the loader should reject.
        explicit_empty = MINIMAL + "gates: []\n"

        rubric = load_rubric(write(tmp_path, explicit_empty))

        assert rubric.gates == ()
