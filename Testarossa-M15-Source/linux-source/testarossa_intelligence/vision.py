"""Privacy-bounded visual observation and scene interpretation."""
from dataclasses import dataclass
import time


MAX_OBSERVATION_BYTES = 64_000
MAX_TEXT_LENGTH = 2_000
MAX_ITEMS = 100
MAX_AGE_SECONDS = 30


@dataclass(frozen=True)
class VisualObservation:
    observed_at: float
    source: str
    active_window: str
    application: str
    description: str
    visible_items: tuple[str, ...]
    screenshot_retained: bool = False


@dataclass(frozen=True)
class VisualAssessment:
    summary: str
    detected_context: tuple[str, ...]
    warnings: tuple[str, ...]
    requires_confirmation: bool


class ObservationSession:
    """An explicitly activated, in-memory-only observation session."""

    def __init__(self, clock=None):
        self._clock = clock or time.time
        self._active = False
        self._started_at = None
        self._last_observation = None

    @property
    def active(self):
        return self._active

    def start(self):
        self._active = True
        self._started_at = self._clock()
        self._last_observation = None
        return {"active": True, "screenshot_persistence": False}

    def stop(self):
        self._active = False
        self._started_at = None
        self._last_observation = None
        return {"active": False, "observation_cleared": True}

    def accept(self, payload):
        if not self._active:
            raise PermissionError("observation_session_not_active")

        if type(payload) is not dict:
            raise ValueError("observation_must_be_object")

        allowed = {
            "observed_at", "source", "active_window",
            "application", "description", "visible_items",
        }
        if set(payload) != allowed:
            raise ValueError("observation_schema_mismatch")

        observed_at = payload["observed_at"]
        if type(observed_at) not in (int, float):
            raise ValueError("invalid_observation_timestamp")

        now = self._clock()
        age = now - observed_at
        if age < -2 or age > MAX_AGE_SECONDS:
            raise ValueError("observation_stale_or_future")

        if self._started_at is None or observed_at < self._started_at - 2:
            raise ValueError("observation_predates_session")

        text_fields = (
            "source", "active_window", "application", "description"
        )
        for field in text_fields:
            value = payload[field]
            if type(value) is not str or len(value) > MAX_TEXT_LENGTH:
                raise ValueError("invalid_observation_text")

        items = payload["visible_items"]
        if type(items) is not list or len(items) > MAX_ITEMS:
            raise ValueError("invalid_visible_items")
        if any(
            type(item) is not str or len(item) > MAX_TEXT_LENGTH
            for item in items
        ):
            raise ValueError("invalid_visible_item")

        estimate = sum(
            len(value.encode("utf-8"))
            for value in (
                payload["source"],
                payload["active_window"],
                payload["application"],
                payload["description"],
                *items,
            )
        )
        if estimate > MAX_OBSERVATION_BYTES:
            raise ValueError("observation_too_large")

        observation = VisualObservation(
            observed_at=float(observed_at),
            source=payload["source"],
            active_window=payload["active_window"],
            application=payload["application"],
            description=payload["description"],
            visible_items=tuple(items),
        )
        self._last_observation = observation
        return observation

    def current(self):
        if not self._active:
            raise PermissionError("observation_session_not_active")
        return self._last_observation


class VisualReasoner:
    """Produces bounded context from an accepted observation."""

    def assess(self, observation):
        if not isinstance(observation, VisualObservation):
            raise ValueError("invalid_visual_observation")

        context = []
        warnings = []

        application = observation.application.lower()
        window = observation.active_window.lower()
        description = observation.description.lower()

        if "blender" in application or "blender" in window:
            context.append("blender")
        if any(word in description for word in (
            "object mode", "edit mode", "sculpt mode"
        )):
            context.append("3d_editing")
        if any(word in description for word in (
            "rendering", "render result"
        )):
            context.append("rendering")
        if any(word in description for word in (
            "error", "failed", "exception"
        )):
            warnings.append("possible_visible_error")

        if not context:
            context.append("general_desktop")

        summary = (
            f"Application: {observation.application or 'unknown'}. "
            f"Window: {observation.active_window or 'unknown'}. "
            f"Visible items: {len(observation.visible_items)}."
        )

        return VisualAssessment(
            summary=summary,
            detected_context=tuple(context),
            warnings=tuple(warnings),
            requires_confirmation=True,
        )
