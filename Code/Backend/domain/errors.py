"""Domain error hierarchy.

Every error the application raises deliberately derives from
:class:`NanoVoxInsightsError`, which carries a stable machine-readable
``code``. The delivery layer maps these onto RFC 9457 problem responses
(``frameworks_drivers/api/errors.py``), so an error's HTTP representation is
decided in one place rather than at each raise site (plan §2A.3).

This is the base vocabulary Phase 0 needs. Later phases add to it as they
need it — ``InsufficientSample``, ``LayerUnavailable`` and
``LabelLeakDetected`` arrive with the phases that raise them, rather than as
unused classes now.
"""

from __future__ import annotations


class NanoVoxInsightsError(Exception):
    """Base class for every error raised deliberately by this application."""

    code = "nanovox_insights_error"

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class ConfigurationError(NanoVoxInsightsError):
    """Configuration is missing, malformed or mutually inconsistent.

    Raised during startup validation so the process fails fast with an
    actionable message instead of failing on first use.
    """

    code = "configuration_error"


class ValidationError(NanoVoxInsightsError):
    """Input failed a business rule."""

    code = "validation_error"


class NotFoundError(NanoVoxInsightsError):
    """A requested resource does not exist."""

    code = "not_found"


class ConflictError(NanoVoxInsightsError):
    """The request is valid but the system's current state forbids it."""

    code = "conflict"


class DependencyUnavailableError(NanoVoxInsightsError):
    """An external dependency (database, model provider) could not be reached."""

    code = "dependency_unavailable"
