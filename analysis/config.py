"""User configuration: training base, data sources, thresholds, zones, goals."""
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Literal

TrainingBase = Literal["power", "hr", "pace"]

# Default zone boundaries as fractions of threshold value.
# 4 boundaries define 5 zones (Z1..Z5).
DEFAULT_ZONES: dict[str, list[float]] = {
    "power": [0.55, 0.75, 0.90, 1.05],   # Coggan-style
    "hr": [0.72, 0.82, 0.89, 0.96],       # Friel-style
    "pace": [1.29, 1.14, 1.06, 1.00],     # Inverted (slower → faster)
}


@dataclass
class UserConfig:
    """Top-level user configuration stored as JSON."""

    training_base: TrainingBase = "power"

    sources: dict[str, str] = field(default_factory=lambda: {
        "activities": "garmin",
        "health": "oura",
        "plan": "stryd",
    })

    thresholds: dict = field(default_factory=lambda: {
        "cp_watts": None,
        "lthr_bpm": None,
        "threshold_pace_sec_km": None,
        "max_hr_bpm": None,
        "rest_hr_bpm": None,
        "source": "auto",
    })

    zones: dict[str, list[float]] = field(
        default_factory=lambda: {k: list(v) for k, v in DEFAULT_ZONES.items()}
    )

    goal: dict = field(default_factory=lambda: {
        "race_date": "",
        "distance": "marathon",
        "target_time_sec": 0,
    })

    source_options: dict = field(default_factory=lambda: {
        "garmin_region": "international",  # "international" or "cn"
    })


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "config.json"
)


def load_config(config_path: str | None = None) -> UserConfig:
    """Load user config from JSON file. Returns defaults if file missing."""
    path = config_path or _DEFAULT_CONFIG_PATH
    if not os.path.exists(path):
        return UserConfig()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return UserConfig(**data)


def save_config(config: UserConfig, config_path: str | None = None) -> None:
    """Persist user config to JSON file."""
    path = config_path or _DEFAULT_CONFIG_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(config), f, indent=2)
