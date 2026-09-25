"""`/api/v1/insights/playbooks` over the real catalogue."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.ports.reference_lookup import ReferenceLookup
from application.use_cases.playbooks import GetPlaybook
from domain.entities.agent import Agent
from domain.entities.broker import Broker
from domain.entities.employer import Employer
from domain.entities.employer_contact import EmployerContact
from domain.entities.member import Member
from domain.entities.rule import Rule
from domain.entities.touchpoint import Touchpoint
from frameworks_drivers.api.dependencies import get_playbook_use_case
from infrastructure.config.paths import DEFAULT_CONFIG_DIR
from infrastructure.config.playbook_loader import load_playbooks

URL = "/api/v1/insights/playbooks"


class _Touchpoints(ReferenceLookup):
    async def find_agent(self, reference: str) -> Agent | None:
        return None

    async def find_member(self, reference: str) -> Member | None:
        return None

    async def find_employer_contact(self, reference: str) -> EmployerContact | None:
        return None

    async def find_employer(self, reference: str) -> Employer | None:
        return None

    async def list_brokers(self) -> tuple[Broker, ...]:
        return ()

    async def list_rules(self) -> tuple[Rule, ...]:
        return ()

    async def list_touchpoints(self) -> tuple[Touchpoint, ...]:
        return (Touchpoint("denial_letter_eob", "Claims Operations", "the carrier"),)


def _with_touchpoints(app: FastAPI) -> None:
    catalogue = load_playbooks(DEFAULT_CONFIG_DIR / "playbooks.yaml")
    app.dependency_overrides[get_playbook_use_case] = lambda: GetPlaybook(catalogue, _Touchpoints())


def test_the_catalogue_lists_static_keys_dynamic_kinds_and_held_back_keys(
    client: TestClient,
) -> None:
    response = client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert body["reviewed"] is False
    assert "unresolved" in {p["key"] for p in body["playbooks"]}
    assert {k["prefix"] for k in body["dynamicKinds"]} == {"tp", "cat", "sig", "pl"}
    assert {h["key"] for h in body["heldBack"]} == {"high", "brush_off", "circular"}


def test_every_playbook_is_labelled_an_unreviewed_recommendation(client: TestClient) -> None:
    """D14 (C3a): a suggested step must not read back as a measurement."""
    for playbook in client.get(URL).json()["playbooks"]:
        assert playbook["claim"] == "recommendation"
        assert playbook["reviewed"] is False


def test_a_static_key_resolves(client: TestClient) -> None:
    response = client.get(f"{URL}/escalation_missed")

    assert response.status_code == 200
    body = response.json()
    assert body["ownerTeam"] == "Operations"
    assert body["source"] == "escalation_missed"
    assert body["steps"]


def test_a_touchpoint_key_resolves_with_the_sheets_owner(app: FastAPI, client: TestClient) -> None:
    _with_touchpoints(app)

    response = client.get(f"{URL}/tp_denial_letter_eob")

    assert response.status_code == 200
    assert response.json()["ownerTeam"] == "Claims Operations"
    assert response.json()["dynamic"] is True


def test_a_key_naming_nothing_is_a_404_not_an_empty_panel(app: FastAPI, client: TestClient) -> None:
    _with_touchpoints(app)

    assert client.get(f"{URL}/tp_made_up").status_code == 404
    assert client.get(f"{URL}/nonsense").status_code == 404


def test_a_held_back_key_is_a_404_that_says_why(client: TestClient) -> None:
    response = client.get(f"{URL}/brush_off")

    assert response.status_code == 404
    assert "C8a" in response.json()["detail"]


def test_a_category_key_with_spaces_and_ampersand_resolves(client: TestClient) -> None:
    response = client.get(f"{URL}/cat_Claims%20%26%20EOB")

    assert response.status_code == 200
    assert response.json()["label"] == "Claims & EOB"
