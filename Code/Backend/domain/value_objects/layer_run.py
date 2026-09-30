"""When a pipeline layer last ran on a call, and what ran it.

Plan §7 requires provenance on every analysis — "provider, model, prompt
version per layer, rubric version, tokens in/out, duration, timestamp" —
and the `call_extractions` columns have carried it since Phase 4. What was
missing was a way to read it back: `CallExtraction` reconstructed a call's
tags and dropped the four provenance columns per layer on the floor, so
the only available answer to "did L3 run?" was "is `quality_score` null?".

Those are not the same question. A layer that ran and found nothing to
report leaves the same nulls as a layer that never ran, and the difference
is the whole of what a reader needs: one is a finding, the other is a gap.
This makes the distinction storable and therefore renderable.

`rubric_version` is L3's alone. It is on this shared shape rather than in
an L3-specific subclass because a version that is `None` for two of three
layers is a smaller lie than three near-identical classes, and the rubric
is genuinely part of "what produced this score".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LayerRun:
    """One layer's completed run over one call."""

    provider: str
    model: str
    prompt_version: str
    completed_at: datetime
    #: L3 only. `None` on layers that score nothing.
    rubric_version: str | None = None
