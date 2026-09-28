"""The insight service's structured-output schema — what the model returns.

Required and non-nullable throughout, like L2's, L3's and L4's: absence is
its own literal value rather than a missing key, so a truncated answer
fails validation instead of arriving half-formed.

`issueKey` carries the sentinel `"none"` rather than being nullable, for
the same reason. A model that wants to say "no playbook applies" should
have to say it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

KindLiteral = Literal["INFERENCE", "RECOMMENDATION"]
SeverityLiteral = Literal["READ_FIRST", "WORTH_READING", "BACKGROUND"]
LensLiteral = Literal[
    "EMPLOYERS",
    "CHURN_AND_RETENTION",
    "PRODUCT_AND_SERVICE",
    "PAYER_AND_CARRIER",
]


class InsightItem(BaseModel):
    """One generated sentence and the figures it read."""

    key: str = Field(description="A short stable slug for this sentence.")
    sentence: str = Field(description="One sentence. No number absent from the facts.")
    kind: KindLiteral
    severity: SeverityLiteral
    lens: LensLiteral
    fact_keys: list[str] = Field(
        alias="factKeys",
        description="The `key` of every fact this sentence read. Never empty.",
    )
    issue_key: str = Field(
        alias="issueKey",
        description="A playbook key, or the literal 'none' when none applies.",
    )

    model_config = {"populate_by_name": True}


class InsightsResponse(BaseModel):
    """The model's whole answer for one screen."""

    insights: list[InsightItem]
