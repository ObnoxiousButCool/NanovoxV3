"""L2's structured-output schema — what the model must return.

Every field is required and non-nullable, deliberately: strict
schema-constrained decoding (every provider we use enforces one) handles
"always present, sometimes empty" far more reliably than an optional
field, so absence is its own literal value (``"NONE"``) or an empty list,
normalised into the domain shape by
:mod:`application.use_cases.classify_call_l2`, not by the model.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

OutcomeLiteral = Literal["RESOLVED", "PARTIALLY_RESOLVED", "ESCALATED", "UNRESOLVED"]
CategoryLiteral = Literal[
    "Coverage & Benefits",
    "Claims & EOB",
    "Provider Network",
    "Billing & Premium",
    "Enrollment & ID Cards",
    "Life & Beneficiary",
    "Broker Conduct",
]
ProductLineLiteral = Literal["dental", "vision", "life", "chiro", "program"]
ComplaintAttributionLiteral = Literal["CHOICE", "BROKER", "CARRIER", "PROVIDER", "NONE"]
IntentTypeLiteral = Literal["expansion", "market_test", "cancellation"]
BrokerSentimentLiteral = Literal["ADVERSE", "POSITIVE", "NONE"]


class ComplaintResponse(BaseModel):
    present: bool
    #: "NONE" when `present` is false.
    attributed_to: ComplaintAttributionLiteral


class IntentStatementResponse(BaseModel):
    type: IntentTypeLiteral
    quote: str
    turn_seq: int = Field(ge=0)


class BrokerNamedAloudResponse(BaseModel):
    present: bool
    #: Empty string when `present` is false.
    broker_ref: str
    #: "NONE" when `present` is false.
    sentiment: BrokerSentimentLiteral


class L2Response(BaseModel):
    outcome: OutcomeLiteral
    category: CategoryLiteral
    product_lines: list[ProductLineLiteral]
    complaint: ComplaintResponse
    intent: list[IntentStatementResponse]
    escalation_triggered: bool
    escalation_requested_by_caller: bool
    broker_named_aloud: BrokerNamedAloudResponse
    #: A Touchpoints-sheet reference, or empty string if none applies.
    touchpoint: str
    summary: str
