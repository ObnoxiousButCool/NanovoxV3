"""Port for reading a corpus the aggregations can compute over.

`domain/aggregation/` is written against the Call Tag Schema and takes its
inputs as `CallContext`, `EmployerFacts` and `BrokerFacts` — deliberately,
so that the pipeline, the answer key and a test fixture all map into the
same shape and no figure can tell which it was handed. This is the port
that builds those values from what has actually been stored.

## What the slice refuses to do

Three things could each be papered over here, and each would produce a
confidently wrong number rather than a visible gap:

- **A call with no date** cannot be placed in any window, and every
  published metric is windowed. Guessing a date — today, the ingest time,
  the corpus midpoint — would put the call in a window it may not belong
  to. It is left out and its reference is reported.
- **A call with no extraction row** has not been analysed. Admitting it
  with empty tags would be worse than useless: `filters` reads an empty
  signal set as "no signals were raised", so an unanalysed call would
  silently enlarge the clean population of every signal-based figure. It
  is left out and its reference is reported.
- **A schema field the pipeline cannot yet produce** is named in
  `unavailable_fields` rather than arriving as an empty value. The
  difference matters most for `control_exceptions`, which has no column in
  `call_extractions` at all: as an empty set it reads as "no compliance
  exceptions occurred", which is a claim nobody has made.

None of these is an error to swallow. `CorpusSlice` carries all three out
so an endpoint can withhold a figure, and say why, instead of publishing a
zero.

## Why `source` lives here and not on the filter set

`InsightFilters` narrows calls that are already in the corpus.
`CorpusQuery.sources` decides what the corpus *is* — whether a pasted
one-off transcript counts alongside the ingested batch. That is a question
about which rows to read, answered before anything becomes a
`CallContext`, and keeping it here is what lets `CallContext` stay unable
to say where it came from.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

    from domain.aggregation.call_tags import BrokerFacts, CallContext, EmployerFacts
    from domain.value_objects.call_source import CallSource


@dataclass(frozen=True)
class CorpusQuery:
    """Which stored calls make up the corpus for one request."""

    #: Empty means every source. Named sources narrow to those — the
    #: published dashboard reads `CORPUS_PDF` alone, so that a transcript
    #: someone pasted to try the pipeline out never lands in a metric.
    sources: frozenset[CallSource] = frozenset()
    #: An optional outer bound on what is read, so a request for a twelve
    #: week window need not load four years of calls. Inclusive, and never
    #: a substitute for the per-metric window: `dashboard.yaml` sets
    #: `window_weeks` per metric, and `Window.calls_in` still applies it.
    since: date | None = None
    until: date | None = None


@dataclass(frozen=True)
class CorpusSlice:
    """Everything an aggregation needs, plus what could not be included.

    The two are deliberately one object. A caller that wanted only the
    calls would have to go out of its way to discard the caveats, which is
    the opposite of the usual arrangement where the caveats live somewhere
    a busy caller never looks.
    """

    calls: tuple[CallContext, ...] = ()
    #: Every employer in reference data, not only those that called. Peer
    #: comparisons and `book_lives_for` need the full population —
    #: restricting it to employers with calls would make each denominator
    #: move with call volume.
    employers: tuple[EmployerFacts, ...] = ()
    brokers: tuple[BrokerFacts, ...] = ()

    #: Calls left out for want of `occurred_at`, by reference.
    undated: tuple[str, ...] = ()
    #: Calls left out because nothing has analysed them, by reference.
    unanalysed: tuple[str, ...] = ()
    #: Call Tag Schema fields no included call can carry, because the
    #: pipeline has nowhere to store them. Named so a figure resting on one
    #: is withheld rather than computed over absence.
    unavailable_fields: tuple[str, ...] = field(default=())

    @property
    def excluded(self) -> int:
        """Calls that were stored but could not be measured."""
        return len(self.undated) + len(self.unanalysed)

    def caveats(self) -> tuple[str, ...]:
        """Plain sentences for whatever an endpoint puts its caveats in.

        Empty when there is nothing to say, so a screen with clean inputs
        carries no boilerplate — a caveat printed every time stops being
        read, and the one time it matters it will not be noticed.
        """
        notes: list[str] = []
        if self.undated:
            notes.append(
                f"{len(self.undated)} stored calls have no date and are in no window. "
                "They are counted in no figure."
            )
        if self.unanalysed:
            notes.append(
                f"{len(self.unanalysed)} stored calls have not been analysed and are "
                "excluded, rather than counted as having nothing to report."
            )
        if self.unavailable_fields:
            fields = ", ".join(self.unavailable_fields)
            notes.append(
                f"The pipeline does not produce {fields}. Figures resting on these are "
                "withheld, not zero."
            )
        return tuple(notes)


class InsightsSource(ABC):
    """Reads stored calls and reference data as aggregation inputs."""

    @abstractmethod
    async def load(self, query: CorpusQuery) -> CorpusSlice:
        """The corpus for one request, with its exclusions accounted for.

        Returns an empty slice rather than raising when nothing matches:
        "no calls from this source yet" is an ordinary answer, and the
        endpoints already have to render an empty dashboard honestly
        because most employers have too few calls to clear `min_n`.
        """
