"""Call Tag Schema field 2. Single-valued.

Pharmacy is deliberately absent — ChoiceBuilder has no pharmacy line
(v9's own note on this field). Life & Beneficiary is new in this version.
"""

from __future__ import annotations

from enum import StrEnum


class Category(StrEnum):
    COVERAGE_AND_BENEFITS = "Coverage & Benefits"
    CLAIMS_AND_EOB = "Claims & EOB"
    PROVIDER_NETWORK = "Provider Network"
    BILLING_AND_PREMIUM = "Billing & Premium"
    ENROLLMENT_AND_ID_CARDS = "Enrollment & ID Cards"
    LIFE_AND_BENEFICIARY = "Life & Beneficiary"
    BROKER_CONDUCT = "Broker Conduct"
