"""Canonical data models for the provider layer."""
from dataclasses import dataclass
from datetime import date


@dataclass
class ThresholdEstimate:
    """Auto-detected or manually set threshold values."""

    cp_watts: float | None = None
    lthr_bpm: float | None = None
    threshold_pace_sec_km: float | None = None
    max_hr_bpm: float | None = None
    rest_hr_bpm: float | None = None
    source: str = "auto"  # "auto" | "manual"
    detected_date: date | None = None


# ---------------------------------------------------------------------------
# Canonical column name constants (documentation + validation)
# ---------------------------------------------------------------------------

ACTIVITY_REQUIRED = ["activity_id", "date", "distance_km", "duration_sec"]
ACTIVITY_OPTIONAL = [
    "start_time", "activity_type",
    "avg_power", "max_power",
    "avg_hr", "max_hr",
    "avg_pace_sec_km",
    "elevation_gain_m", "avg_cadence",
    "rss", "cp_estimate",
]

SPLIT_REQUIRED = ["activity_id", "split_num", "duration_sec"]
SPLIT_OPTIONAL = [
    "distance_km", "avg_power", "avg_hr", "max_hr",
    "avg_pace_sec_km", "avg_cadence", "elevation_change_m",
]

HEALTH_REQUIRED = ["date"]
HEALTH_OPTIONAL = [
    "sleep_score", "readiness_score", "hrv_avg", "resting_hr",
    "total_sleep_sec", "deep_sleep_sec", "rem_sleep_sec",
    "body_temp_delta",
]

PLAN_REQUIRED = ["date", "workout_type"]
PLAN_OPTIONAL = [
    "planned_duration_min", "planned_distance_km",
    "target_power_min", "target_power_max",
    "target_hr_min", "target_hr_max",
    "target_pace_min", "target_pace_max",
    "workout_description",
]
