"""Seed the action board from the corpus's own findings (Revised plan
Phase 4 — Vertical 1's last item, porting `add_action` from
`04_build_app_data.py`).

## What is ported, and what is not

The prototype groups its seeded actions at a fine grain it invents purely
for seeding: `process_gap` by touchpoint, `knowledge_failure` by rule id,
one `escalation_missed` action, one `retention_risk` action per call, one
`control_exception` action per type, one per broker adverse pattern. Six
different "one card per X" rules, none of them matching any other grouping
already on a screen.

Seeding here uses `domain.aggregation.actions.action_items` instead — the
same aggregation `GET /insights/actions` already reads: one item per
`SignalType` actually raised across the calls in scope. Coarser than the
prototype, deliberately: a seeded action then corresponds exactly to a row
the issues-to-act-on list already shows, rather than a different, finer cut
nothing else on the screen matches.

## What is never invented

`domain.actions`' own module docstring states decision D6 directly:
"Workflow fields start empty... A seeded action has none of them until
someone sets them." The prototype invents owner, assigned date, action
taken and outcome by cycling a fixture array (`WF[n % len(WF)]`). Nothing
here does that. `CreateAction`, reused unmodified below, already leaves
`owner`, `due`, `assigned_on`, `action_taken`, `outcome` and `measurement`
unset unless the caller supplies them, and this module supplies none of
them.

## Reused, not duplicated

`CreateAction.execute()` is exactly what a human raising a card from a
playbook link already triggers — `POST /insights/actions` with an
`issueKey` resolves the playbook, prefills its steps, owner team and
evidence, and refuses a dead key. Seeding calls it directly, once per
`ActionItem`, rather than re-deriving any of that. The two things seeding
decides for itself, and passes through explicitly, are:

- **Priority.** `CreateAction` derives priority from `PlaybookSeverity`,
  which `domain.playbooks.resolve` fixes at `MEDIUM` for every dynamic key
  (`sig_`, `tp_`, `cat_`, `pl_` alike) — it has nothing else to go on for a
  key nobody wrote a static entry for. That would flatten a
  `verification_failure` (CRITICAL) and a `network_adequacy` (MEDIUM) to the
  same priority. `_priority_for` maps the Signal Taxonomy's own
  `SignalSeverity` instead, so priority tracks the taxonomy that is
  authoritative for it.
- **Owner team.** Passed as `item.owner_team` — the Signal Taxonomy sheet's
  own mandatory column, already what `resolve()` would derive for a `sig_`
  key, but named explicitly here rather than left to re-derivation.

## Idempotent by construction

`issue_key = f"sig_{signal.value}"` doubles as the seed key: one
`ActionItem` exists per signal type in a given corpus state, so the key is
stable and naturally unique (`ActionRow.seed_key` also carries a unique
constraint as a backstop). `SeedActions` checks
`ActionRepository.seed_keys()` and skips a key already present *before*
calling `CreateAction`, rather than creating and catching the constraint
violation — a clean idempotent run reports a skip as a skip, not as a
recovered error.

## The window spans the whole corpus, not one metric's

`GetActions.execute()` (the read side) bounds `action_items` to
`control_exception_rate`'s own rolling window, anchored on `as_of`
(`domain.aggregation.patterns.window_for`) — right for a dashboard figure,
wrong here: for a historical corpus, a window of a few weeks ending today
would drop nearly everything. Seeding instead spans every dated call in the
corpus — `CorpusSlice.available_from` to `.available_until`, the pair
`application/ports/insights_source.py` documents existing precisely so a
caller can say "all of it" rather than substitute a window of its own.
`InsightsRequest(filters=InsightFilters())` is the unfiltered whole corpus:
the same object `InsightsQuery()` with no query parameters builds.
"""

from __future__ import annotations

from dataclasses import dataclass

from application.ports.action_repository import ActionRepository
from application.use_cases.manage_actions import CreateAction, CreateActionRequest
from application.use_cases.read_insights import InsightsReader, InsightsRequest
from domain.actions import Action, Priority
from domain.aggregation.actions import ActionItem, action_items
from domain.aggregation.call_tags import Window
from domain.aggregation.filters import InsightFilters
from domain.playbooks import PlaybookCatalogue, resolve
from domain.value_objects.signal_severity import SignalSeverity

#: Severities that read as Priority.HIGH; the rest read as MEDIUM or LOW.
#: Mirrors `SEVERITY_ORDER` (worst first: CRITICAL, HIGH, MEDIUM, LOW) —
#: the two worst collapse to HIGH, the two mildest keep their own name.
_HIGH_SEVERITIES = frozenset({SignalSeverity.CRITICAL, SignalSeverity.HIGH})


def _priority_for(severity: SignalSeverity) -> Priority:
    if severity in _HIGH_SEVERITIES:
        return Priority.HIGH
    if severity is SignalSeverity.MEDIUM:
        return Priority.MEDIUM
    return Priority.LOW


@dataclass(frozen=True)
class SeedActionsReport:
    """What one seeding run did. Printed, never silently discarded — a
    seed run reports what it did and what it left alone, the way
    `evaluate_extraction`'s CLI reports rather than judges."""

    #: Every `ActionItem` found across the whole corpus, whether or not it
    #: was already seeded. Empty means the corpus has nothing to seed from
    #: yet — no call has raised a signal — which is a different fact from
    #: "seeded, nothing new".
    found: int
    created: tuple[Action, ...]
    #: Issue keys already present, left alone.
    skipped: tuple[str, ...]


class SeedActions:
    def __init__(
        self,
        *,
        reader: InsightsReader,
        actions: ActionRepository,
        create_action: CreateAction,
        catalogue: PlaybookCatalogue,
    ) -> None:
        self._reader = reader
        self._actions = actions
        self._create_action = create_action
        self._catalogue = catalogue

    async def execute(self) -> SeedActionsReport:
        scope = await self._reader.scope(InsightsRequest(filters=InsightFilters()))
        corpus = scope.corpus
        if corpus.available_from is None or corpus.available_until is None:
            # No dated call in the corpus at all — nothing to window over.
            return SeedActionsReport(found=0, created=(), skipped=())

        window = Window(start=corpus.available_from, end=corpus.available_until)
        items = action_items(scope.filtered.calls, window)

        existing = await self._actions.seed_keys()
        created: list[Action] = []
        skipped: list[str] = []
        for item in items:
            issue_key = f"sig_{item.signal.value}"
            if issue_key in existing:
                skipped.append(issue_key)
                continue
            action = await self._create_action.execute(self._request_for(item, issue_key))
            created.append(action)

        return SeedActionsReport(found=len(items), created=tuple(created), skipped=tuple(skipped))

    def _request_for(self, item: ActionItem, issue_key: str) -> CreateActionRequest:
        return CreateActionRequest(
            title=self._title_for(item, issue_key),
            call_references=item.call_ids,
            issue_key=issue_key,
            owner_team=item.owner_team,
            priority=_priority_for(item.severity),
            # The one field `CreateActionRequest` carries that the human
            # path never sets — see its own docstring.
            seed_key=issue_key,
        )

    def _title_for(self, item: ActionItem, issue_key: str) -> str:
        # `resolve()` also runs inside `CreateAction.execute()`, which is
        # what actually validates the key and raises if it resolves to
        # nothing; this lookup only borrows the playbook's own label for
        # the title text, so a dead key still fails there, not here.
        playbook = resolve(self._catalogue, issue_key, {})
        label = playbook.label if playbook is not None else _humanise(item.signal.value)
        plural = "" if item.calls == 1 else "s"
        return f"{label} — {item.calls} call{plural}"


def _humanise(code: str) -> str:
    """Fallback title text for a key that fails to resolve here — `resolve()`
    inside `CreateAction.execute()` still refuses it properly."""
    words = code.replace("_", " ").strip()
    return words[:1].upper() + words[1:]
