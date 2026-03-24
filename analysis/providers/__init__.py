"""Provider registry — maps provider names to implementations."""
from analysis.providers.base import (
    ActivityProvider,
    HealthProvider,
    PlanProvider,
    ThresholdProvider,
)

_ACTIVITY_PROVIDERS: dict[str, type[ActivityProvider]] = {}
_HEALTH_PROVIDERS: dict[str, type[HealthProvider]] = {}
_PLAN_PROVIDERS: dict[str, type[PlanProvider]] = {}
_THRESHOLD_PROVIDERS: dict[str, type[ThresholdProvider]] = {}


def register_activity(name: str, cls: type[ActivityProvider]) -> None:
    _ACTIVITY_PROVIDERS[name] = cls


def register_health(name: str, cls: type[HealthProvider]) -> None:
    _HEALTH_PROVIDERS[name] = cls


def register_plan(name: str, cls: type[PlanProvider]) -> None:
    _PLAN_PROVIDERS[name] = cls


def register_threshold(name: str, cls: type[ThresholdProvider]) -> None:
    _THRESHOLD_PROVIDERS[name] = cls


def get_activity_provider(name: str) -> ActivityProvider:
    _ensure_registered()
    return _ACTIVITY_PROVIDERS[name]()


def get_health_provider(name: str) -> HealthProvider:
    _ensure_registered()
    return _HEALTH_PROVIDERS[name]()


def get_plan_provider(name: str) -> PlanProvider:
    _ensure_registered()
    return _PLAN_PROVIDERS[name]()


def get_threshold_provider(name: str) -> ThresholdProvider:
    _ensure_registered()
    return _THRESHOLD_PROVIDERS[name]()


def available_providers() -> dict[str, list[str]]:
    """Return dict of category → list of registered provider names."""
    _ensure_registered()
    return {
        "activities": list(_ACTIVITY_PROVIDERS.keys()),
        "health": list(_HEALTH_PROVIDERS.keys()),
        "plan": list(_PLAN_PROVIDERS.keys()),
        "threshold": list(_THRESHOLD_PROVIDERS.keys()),
    }


_registered = False


def _ensure_registered() -> None:
    """Lazily import provider modules to trigger registration."""
    global _registered
    if _registered:
        return
    _registered = True
    # Import triggers register_*() calls at module level
    import analysis.providers.garmin  # noqa: F401
    import analysis.providers.stryd  # noqa: F401
    import analysis.providers.oura  # noqa: F401
