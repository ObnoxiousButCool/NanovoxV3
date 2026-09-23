"""Domain error hierarchy.

Every error the application raises deliberately derives from
:class:`NanoVoxInsightsError`, which carries a stable machine-readable
``code``. The delivery layer maps these onto RFC 9457 problem responses
(``frameworks_drivers/api/errors.py``), so an error's HTTP representation is
decided in one place rather than at each raise site (plan §2A.3).

This is the base vocabulary Phase 0 needs, plus what Phase 1 and Phase 3
add. Later phases add more as they need it — ``InsufficientSample`` and
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


class ReferenceIntegrityError(ValidationError):
    """An imported reference row names a business key nothing else provides.

    E.g. an employer's broker of record, or a member's employer, that the
    same import didn't also include. Exposed to the caller — this is
    diagnostic information about the *source data* (the workbook), useful to
    whoever is running the import, not an internal detail to hide.
    """

    code = "reference_integrity_error"


class ProviderUnavailableError(DependencyUnavailableError):
    """A model provider could not be reached, or refused the request transiently.

    Distinct from a bad response: the request never produced an answer, so
    retrying it is meaningful.

    ``retry_after`` carries the provider's own instruction, in seconds, when
    it sent one. A rate limiter knows when its bucket refills and blind
    backoff does not, so honouring it is the difference between waiting once
    and burning every remaining attempt against a window that was never
    going to open in time.
    """

    code = "provider_unavailable"

    def __init__(
        self,
        message: str,
        *,
        detail: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.retry_after = retry_after


class ProviderResponseError(DependencyUnavailableError):
    """A model provider answered, but never with the structure that was demanded.

    Raised only after the repair attempt has also failed. The analysis is
    abandoned rather than stored partially: a half-parsed layer would be
    worse than no layer, because it would look like a result.
    """

    code = "provider_response_error"
