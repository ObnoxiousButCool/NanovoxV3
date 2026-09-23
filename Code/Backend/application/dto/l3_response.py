"""L3's structured-output schema — what the model must return.

Every field is required and non-nullable, for the same reason as L2's
(see ``application/dto/l2_response.py``'s module docstring): absence is
its own literal value, normalised into the domain shape by
``application.use_cases.classify_call_l3``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DimensionLiteral = Literal[
    "empathy",
    "accuracy",
    "proactivity",
    "compliance_disclosure",
    "resolution_ownership",
    "escalation_appropriateness",
]
PolarityLiteral = Literal["POSITIVE", "NEGATIVE"]


class MarkerResponse(BaseModel):
    dimension: DimensionLiteral
    polarity: PolarityLiteral
    description: str
    quote: str
    turn_seq: int = Field(ge=0)


class KnowledgeFailureResponse(BaseModel):
    present: bool
    #: Empty string when `present` is false.
    rule_id: str
    #: Empty string when `present` is false.
    correct_statement: str


class L3Response(BaseModel):
    markers: list[MarkerResponse]
    knowledge_failure: KnowledgeFailureResponse
