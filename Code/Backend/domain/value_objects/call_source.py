"""Where a call's transcript came from.

Every call carries one, from day one — plan §6.4's audio seam. `AUDIO`
exists now, unused: nothing implements a source for it yet, but the enum
member exists so nothing downstream has to change shape when one arrives.
"""

from __future__ import annotations

from enum import Enum


class CallSource(str, Enum):
    CORPUS_PDF = "CORPUS_PDF"
    PASTED = "PASTED"
    AUDIO = "AUDIO"
