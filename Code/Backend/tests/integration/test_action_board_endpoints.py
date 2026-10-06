"""The action centre's write side over HTTP (Revised plan Phase 4).

Create → assign → tick → log → action taken → measure → complete, against a
real database, plus every refusal the lifecycle makes.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.reference_source import ReferenceDataset
from domain.entities.ingested_call import IngestedCall
from domain.value_objects.call_resolution_status import CallResolutionStatus
from domain.value_objects.caller_type import CallerType
from domain.value_objects.category import Category
from domain.value_objects.outcome import Outcome
from infrastructure.persistence.repositories.call_repository import SqlCallRepository
from infrastructure.persistence.repositories.reference_repository import SqlReferenceRepository
from infrastructure.persistence.tables import CallExtractionRow, CallRow
from infrastructure.system_clock import SystemClock
from tests.integration.test_reference_lookup import _BROKER, _EMPLOYER

URL = "/api/v1/insights/actions"
_WINDOW = {"start": "2026-10-01", "end": "2026-10-28"}


def _call(reference: str) -> IngestedCall:
    return IngestedCall(
        reference=reference,
        caller_type=CallerType.MEMBER,
        caller_ref="CB-7700205",
        agent_ref="AGT-01",
        transcript=None,
        resolution_status=CallResolutionStatus.RESOLVED,
        resolution_reason=None,
        member_ref=None,
        employer_contact_ref=None,
        employer_ref=None,
    )


@pytest.fixture
async def seeded(session_factory: async_sessionmaker[AsyncSession]) -> None:
    await SqlCallRepository(session_factory, SystemClock()).upsert_all(
        (_call("C-0001"), _call("C-0002"))
    )
    await SqlReferenceRepository(session_factory).upsert(
        ReferenceDataset(brokers=(_BROKER,), employers=(_EMPLOYER,))
    )


def _create(client: TestClient, **body: Any) -> dict[str, Any]:
    response = client.post(URL, json={"title": "Fix escalations", **body})
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def _patch(client: TestClient, action_id: int, **body: Any) -> Any:
    return client.patch(f"{URL}/{action_id}", json=body)


# --- Create ------------------------------------------------------------------


def test_raising_from_an_issue_key_prefills_from_its_playbook(
    seeded: None, client: TestClient
) -> None:
    action = _create(client, issueKey="escalation_missed", callIds=["C-0001", "C-0002"])

    assert action["ownerTeam"] == "Operations"
    assert action["priority"] == "high"
    assert action["sourceKind"] == "escalation_missed"
    assert action["steps"][0] == {
        "text": "Team lead reviews each call within 48 hours.",
        "done": False,
    }
    assert action["recommendation"] == {
        "text": "Team lead reviews each call within 48 hours.",
        "claim": "recommendation",
    }
    assert action["evidence"].startswith("A supervisor was warranted")
    assert action["callIds"] == ["C-0001", "C-0002"]
    assert action["reference"] == f"ACT-{action['id']:03d}"


def test_a_new_action_starts_in_the_first_lane_with_nothing_invented(
    seeded: None, client: TestClient
) -> None:
    """D6: no owner, due date or outcome until someone sets one."""
    action = _create(client, issueKey="unresolved")

    assert action["status"] == "needs_action"
    assert action["statusLabel"] == "Needs action"
    assert action["owner"] is None and action["due"] is None and action["assignedOn"] is None
    assert action["actionTaken"] is None and action["outcome"] is None
    assert [entry["text"] for entry in action["log"]] == ["Card created"]


def test_raising_by_hand_needs_an_owner_team(seeded: None, client: TestClient) -> None:
    response = client.post(URL, json={"title": "Something"})

    assert response.status_code == 400
    assert "owner team" in response.json()["title"]

    manual = _create(client, ownerTeam="Compliance", steps=["Log it."])
    assert manual["sourceKind"] == "manual"
    assert manual["priority"] == "medium"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"issueKey": "tp_made_up"}, "no playbook"),
        ({"issueKey": "unresolved", "callIds": ["C-9999"]}, "ingested"),
        ({"issueKey": "unresolved", "employerRef": "EMP-0000"}, "no employer"),
        ({"issueKey": "unresolved", "status": "archived"}, "not a lifecycle state"),
        ({"issueKey": "unresolved", "status": "completed"}, "Completed"),
        ({"issueKey": "unresolved", "title": "  "}, "title"),
    ],
)
def test_bad_creates_are_refused(
    seeded: None, client: TestClient, body: dict[str, Any], message: str
) -> None:
    response = client.post(URL, json={"title": "x", **body})

    assert response.status_code == 400
    assert message in response.json()["title"]


def test_an_action_can_name_a_real_employer(seeded: None, client: TestClient) -> None:
    action = _create(client, issueKey="exit_language", employerRef=_EMPLOYER.reference)

    assert action["employerRef"] == _EMPLOYER.reference


# --- The whole lifecycle ------------------------------------------------------


def test_create_assign_tick_log_act_measure_complete(seeded: None, client: TestClient) -> None:
    action_id = _create(client, issueKey="escalation_missed", callIds=["C-0001"])["id"]

    assigned = _patch(client, action_id, owner="Rebekah Vance", due="2026-10-09", status="assigned")
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["assignedOn"] is not None

    ticked = _patch(client, action_id, ticks=[{"index": 0, "done": True}])
    assert ticked.json()["steps"][0]["done"] is True

    noted = _patch(client, action_id, note="Called the carrier.")
    assert noted.json()["log"][-1]["text"] == "Called the carrier."

    taken = _patch(client, action_id, actionTaken="Briefed the team.", status="action_taken")
    assert taken.json()["status"] == "action_taken"

    monitoring = _patch(client, action_id, measurementWindow=_WINDOW, status="monitoring")
    assert monitoring.json()["measurementWindow"] == _WINDOW

    completed = _patch(client, action_id, outcome="Refusals fell to zero.", status="completed")
    body = completed.json()
    assert completed.status_code == 200, completed.text
    assert body["status"] == "completed"
    assert [entry["text"] for entry in body["log"]] == [
        "Card created",
        "Owner Rebekah Vance",
        "Due 2026-10-09",
        "Moved to Assigned",
        "Completed step: Team lead reviews each call within 48 hours.",
        "Called the carrier.",
        "Action taken: Briefed the team.",
        "Moved to Action taken",
        "Measurement window: 2026-10-01 to 2026-10-28",
        "Moved to Monitoring",
        "Outcome recorded: Refusals fell to zero.",
        "Moved to Completed",
    ]

    reread = client.get(f"{URL}/{action_id}").json()
    assert reread == body


@pytest.mark.parametrize("target", ["monitoring", "completed"])
def test_monitoring_and_completed_are_refused_without_a_measurement(
    seeded: None, client: TestClient, target: str
) -> None:
    """The plan's hard rule, at the API."""
    action_id = _create(client, issueKey="unresolved")["id"]
    _patch(client, action_id, actionTaken="Did it.")

    response = _patch(client, action_id, status=target)

    assert response.status_code == 400
    assert "measurement window" in response.json()["title"]
    assert client.get(f"{URL}/{action_id}").json()["status"] == "needs_action"


def test_a_refused_edit_changes_nothing(seeded: None, client: TestClient) -> None:
    """One edit is all or nothing: the owner in a refused move is not saved."""
    action_id = _create(client, issueKey="unresolved")["id"]

    _patch(client, action_id, owner="Someone", status="completed")

    after = client.get(f"{URL}/{action_id}").json()
    assert after["owner"] is None
    assert len(after["log"]) == 1


def test_owner_and_due_can_be_cleared(seeded: None, client: TestClient) -> None:
    action_id = _create(client, issueKey="unresolved", owner="A Person", due="2026-10-09")["id"]

    cleared = _patch(client, action_id, clearOwner=True, clearDue=True).json()

    assert cleared["owner"] is None and cleared["due"] is None


def test_an_open_action_past_its_due_date_reads_as_past_due(
    seeded: None, client: TestClient
) -> None:
    """Whatever lane it is in — nobody has to move it to Overdue."""
    action_id = _create(client, issueKey="unresolved", due="2000-01-01")["id"]

    assert client.get(f"{URL}/{action_id}").json()["pastDue"] is True


def test_a_measurement_window_that_ends_before_it_starts_is_refused(
    seeded: None, client: TestClient
) -> None:
    action_id = _create(client, issueKey="unresolved")["id"]

    response = _patch(
        client, action_id, measurementWindow={"start": "2026-10-02", "end": "2026-10-01"}
    )

    assert response.status_code == 400


def test_an_unknown_action_is_a_404(seeded: None, client: TestClient) -> None:
    assert client.get(f"{URL}/999").status_code == 404
    assert _patch(client, 999, note="x").status_code == 404


# --- The board ---------------------------------------------------------------


def test_the_board_lists_the_lanes_and_says_who_can_edit(seeded: None, client: TestClient) -> None:
    first = _create(client, issueKey="unresolved")
    second = _create(client, issueKey="escalation_missed")

    board = client.get(f"{URL}/board").json()

    assert [lane["code"] for lane in board["lanes"]] == [
        "needs_action",
        "assigned",
        "in_progress",
        "overdue",
        "action_taken",
        "monitoring",
        "completed",
    ]
    completed = next(lane for lane in board["lanes"] if lane["code"] == "completed")
    assert completed["requires"] == ["action_taken", "measurement_window", "outcome"]
    assert "Trusted network" in board["trustNote"]
    assert [a["id"] for a in board["actions"]] == [second["id"], first["id"]]


def test_the_derived_findings_are_untouched(seeded: None, client: TestClient) -> None:
    """GET /insights/actions still returns findings, with no status on them."""
    _create(client, issueKey="unresolved")

    findings = client.get(URL).json()

    assert "items" in findings
    assert all("status" not in item for item in findings["items"])


# --- The board, scoped to one account ----------------------------------------


@pytest.fixture
async def with_employer_calls(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Two calls on EMP-1001 and one on nobody, so a scoped board has
    something to leave out as well as something to return.

    The three are **analysed**, not merely ingested. The board is scoped by
    the same corpus every other screen reads, and that corpus holds the
    calls the pipeline has extracted; three rows with no extraction are
    invisible to it, so a board scoped against them could not tell an
    account's calls from anybody else's. `in_scope` keeps an action citing
    such a call rather than dropping it — which is right, and would make
    this test pass whatever the scoping did.
    """
    await SqlReferenceRepository(session_factory).upsert(
        ReferenceDataset(brokers=(_BROKER,), employers=(_EMPLOYER,))
    )
    await SqlCallRepository(session_factory, SystemClock()).upsert_all(
        (
            _with_employer(_call("C-0001"), "EMP-1001"),
            _with_employer(_call("C-0002"), "EMP-1001"),
            _call("C-0003"),
        )
    )
    await _analyse(session_factory, ("C-0001", "C-0002", "C-0003"))


async def _analyse(
    session_factory: async_sessionmaker[AsyncSession], references: tuple[str, ...]
) -> None:
    """Give each call the extraction row that puts it in the corpus."""
    async with session_factory() as session, session.begin():
        rows = (
            (await session.execute(select(CallRow).where(CallRow.reference.in_(references))))
            .scalars()
            .all()
        )
        for row in rows:
            row.occurred_at = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
            session.add(
                CallExtractionRow(
                    call_id=row.id,
                    outcome=Outcome.RESOLVED.value,
                    category=Category.CLAIMS_AND_EOB.value,
                    complaint_present=False,
                    escalation_triggered=False,
                    knowledge_failure_present=False,
                )
            )


def _with_employer(call: IngestedCall, employer_ref: str) -> IngestedCall:
    return replace(call, employer_ref=employer_ref)


def test_an_action_reaches_an_account_through_the_calls_it_cites(
    with_employer_calls: None, client: TestClient
) -> None:
    """The defect this exists to stop.

    Every seeded signal-wide action carries no `employerRef` at all and
    reaches an account only through its calls, so an account board that
    matched on the reference alone came back empty and the page said
    "nothing in its calls has needed one" over eighteen calls' worth of
    signals.
    """
    cited = _create(client, title="Escalations missed", ownerTeam="Service", callIds=["C-0001"])
    _create(client, title="Somebody else's", ownerTeam="Service", callIds=["C-0003"])

    board = client.get(f"{URL}/board", params={"employer": "EMP-1001"}).json()

    assert [action["id"] for action in board["actions"]] == [cited["id"]]


def test_an_action_naming_the_account_is_returned_with_no_calls_cited(
    with_employer_calls: None, client: TestClient
) -> None:
    """The other half, and neither is redundant: an action raised against an
    account before any call is cited has the reference and nothing else."""
    named = _create(client, title="Renewal review", ownerTeam="Service", employerRef="EMP-1001")

    board = client.get(f"{URL}/board", params={"employer": "EMP-1001"}).json()

    assert [action["id"] for action in board["actions"]] == [named["id"]]


def test_an_action_is_not_returned_twice_when_it_both_names_and_cites(
    with_employer_calls: None, client: TestClient
) -> None:
    """`or`, not two queries concatenated. A card listed twice on an account
    reads as two pieces of work."""
    both = _create(
        client,
        title="Both",
        ownerTeam="Service",
        employerRef="EMP-1001",
        callIds=["C-0001", "C-0002"],
    )

    board = client.get(f"{URL}/board", params={"employer": "EMP-1001"}).json()

    assert [action["id"] for action in board["actions"]] == [both["id"]]


def test_the_lanes_stand_whether_or_not_the_account_has_cards(
    with_employer_calls: None, client: TestClient
) -> None:
    """The lanes are the lifecycle's, not a summary of what is on the board.
    An account with nothing in progress still shows the column, rather than
    a board whose shape changes per account."""
    whole = client.get(f"{URL}/board").json()

    scoped = client.get(f"{URL}/board", params={"employer": "EMP-1001"}).json()

    assert scoped["actions"] == []
    assert [lane["code"] for lane in scoped["lanes"]] == [lane["code"] for lane in whole["lanes"]]


def test_the_board_narrows_with_the_shared_filter_bar(
    with_employer_calls: None, client: TestClient
) -> None:
    """The defect: the bar read "87 calls in scope" and the board showed the
    whole book, with nothing saying the two were answering different
    questions. The findings panel beside it had narrowed.

    Any shared filter, not only employer. Here the outcome filter keeps
    every call, and a category nothing matches keeps none -- so the board
    follows the corpus rather than one special-cased parameter.
    """
    _create(client, title="Mine", ownerTeam="Service", callIds=["C-0001"])

    kept = client.get(f"{URL}/board", params={"outcome": "RESOLVED"}).json()
    dropped = client.get(f"{URL}/board", params={"outcome": "UNRESOLVED"}).json()

    assert [action["title"] for action in kept["actions"]] == ["Mine"]
    assert dropped["actions"] == []
    # The lanes are the lifecycle's, not a summary of what survived, so an
    # emptied board still shows its columns rather than losing them.
    assert [lane["code"] for lane in dropped["lanes"]] == [lane["code"] for lane in kept["lanes"]]


def test_an_action_citing_a_call_the_pipeline_has_not_reached_is_kept(
    seeded: None, client: TestClient
) -> None:
    """Drop an action only when the corpus can positively place it out of
    scope.

    `seeded` ingests C-0001 and never extracts it, so the call exists --
    an action may only cite one that does -- but the corpus every screen
    reads cannot see it. Nothing here can say whether it is in or out of the
    filter. Dropping it would make the board quietly narrower than the work
    people are actually doing, and would empty the unfiltered board
    entirely, which is how this rule was found.
    """
    _create(client, title="Unreachable", ownerTeam="Service", callIds=["C-0001"])

    whole = client.get(f"{URL}/board").json()
    narrowed = client.get(f"{URL}/board", params={"region": "Bay Area"}).json()

    assert [action["title"] for action in whole["actions"]] == ["Unreachable"]
    assert [action["title"] for action in narrowed["actions"]] == ["Unreachable"]


def test_an_unscoped_board_is_unchanged(with_employer_calls: None, client: TestClient) -> None:
    """No filters is the whole board, which is the common case."""
    _create(client, title="Mine", ownerTeam="Service", callIds=["C-0001"])
    _create(client, title="Theirs", ownerTeam="Service", callIds=["C-0003"])

    board = client.get(f"{URL}/board").json()

    assert len(board["actions"]) == 2


def test_a_scoped_card_carries_the_account_share_beside_its_own_figure(
    with_employer_calls: None, client: TestClient
) -> None:
    """The card's title counts the whole corpus and must keep doing so: it
    names the piece of work, which is done once by one team. What the account
    page needs is its own share beside that, not instead of it — otherwise a
    panel headed "Actions for this account" shows 179 calls to an account
    that has 18.
    """
    action = _create(
        client,
        title="Member communication gap — 3 calls",
        ownerTeam="Service",
        callIds=["C-0001", "C-0002", "C-0003"],
    )

    board = client.get(f"{URL}/board", params={"employer": "EMP-1001"}).json()

    card = next(a for a in board["actions"] if a["id"] == action["id"])
    assert card["title"] == "Member communication gap — 3 calls"
    assert len(card["callIds"]) == 3
    assert card["callsOnAccount"] == 2


def test_an_unscoped_card_has_no_account_share_rather_than_nought(
    with_employer_calls: None, client: TestClient
) -> None:
    """Nought would read as a card touching none of an account's calls. On
    the board there is no account to touch, which is a different statement
    and the one `null` makes."""
    _create(client, title="Anything", ownerTeam="Service", callIds=["C-0001"])

    board = client.get(f"{URL}/board").json()

    assert board["actions"][0]["callsOnAccount"] is None
