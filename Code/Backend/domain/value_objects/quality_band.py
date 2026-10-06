"""Call Quality Framework sheet, stage 4: the band a call score falls in.

Three bands, boundaries in `config/dashboard.yaml` rather than here. The
boundaries are the tunable part — that sheet's open decision 3 records that
86 is empirical rather than outcome-calibrated — but the set of bands is not,
so the names live in the domain and the numbers do not.
"""

from __future__ import annotations

from enum import StrEnum


class QualityBand(StrEnum):
    GOOD = "GOOD"
    AVERAGE = "AVERAGE"
    POOR = "POOR"
