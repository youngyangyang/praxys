# Multi-Source Data Architecture & Training Base System

**Date:** 2026-03-23
**Status:** Approved
**Scope:** Sub-project 1 of 3 (core backend + settings API)

## Problem

The dashboard is hardcoded to Garmin + Stryd + Oura with power as the only training base. This prevents:
- Runners with different gear from using the app (e.g., Garmin-only, Polar+Stryd)
- Switching data sources without rewriting code
- HR-based or pace-based training approaches

## Solution: Provider Pattern

Abstract provider interfaces per data category. Each platform implements what it supports. Providers output canonical data models. User selects training base (power/HR/pace) which cascades through zones, load calculation, diagnosis, and display.

## Data Categories

| Category | Interface | Canonical output | Initial providers |
|----------|-----------|------------------|-------------------|
| Activities | `ActivityProvider` | distance, duration, HR, power, pace, cadence, elevation, splits | Garmin (primary), Stryd (power overlay) |
| Health | `HealthProvider` | sleep, HRV, readiness, resting HR, body temp | Oura |
| Plan | `PlanProvider` | planned workouts, targets | Stryd |
| Thresholds | `ThresholdProvider` | CP, LTHR, threshold pace | Stryd (CP), Garmin (LTHR) |

Stryd acts as a secondary activity provider that enriches Garmin data via existing `match_activities()` merge.

## Provider Interfaces

```python
class ActivityProvider(ABC):
    name: str
    def load_activities(self, data_dir: str, since: date | None = None) -> pd.DataFrame: ...
    def load_splits(self, data_dir: str, activity_ids: list[str] | None = None) -> pd.DataFrame: ...

class HealthProvider(ABC):
    name: str
    def load_health(self, data_dir: str, since: date | None = None) -> pd.DataFrame: ...

class PlanProvider(ABC):
    name: str
    def load_plan(self, data_dir: str, since: date | None = None) -> pd.DataFrame: ...

class ThresholdProvider(ABC):
    name: str
    def detect_thresholds(self, data_dir: str) -> ThresholdEstimate: ...
```

Registry: simple dict lookup in `analysis/providers/__init__.py`. No plugin framework.

## Canonical Data Models

All providers map platform-specific columns to these canonical names. Data stays as DataFrames.

**Activity columns:**
- Required: `activity_id`, `date`, `distance_km`, `duration_sec`
- Optional: `start_time`, `activity_type`, `avg_power`, `max_power`, `avg_hr`, `max_hr`, `avg_pace_sec_km`, `elevation_gain_m`, `avg_cadence`, `rss`, `trimp`, `rtss`, `cp_estimate`, `load_score`

**Split columns:**
- Required: `activity_id`, `split_num`, `duration_sec`
- Optional: `distance_km`, `avg_power`, `avg_hr`, `max_hr`, `avg_pace_sec_km`, `avg_cadence`, `elevation_change_m`

**Health day columns:**
- Required: `date`
- Optional: `sleep_score`, `readiness_score`, `hrv_avg`, `resting_hr`, `total_sleep_sec`, `deep_sleep_sec`, `rem_sleep_sec`, `body_temp_delta`

**Planned workout columns:**
- Required: `date`, `workout_type`
- Optional: `planned_duration_min`, `planned_distance_km`, `target_power_min/max`, `target_hr_min/max`, `target_pace_min/max`, `workout_description`

**ThresholdEstimate:**
- `cp_watts`, `lthr_bpm`, `threshold_pace_sec_km`, `max_hr_bpm`, `source` ("auto"|"manual"), `detected_date`

## Training Base System

User's foundational choice: `power | hr | pace`

### Load Formulas (computed internally)

- **Power → RSS:** `(duration/3600) * (power/CP)^2 * 100`
- **HR → TRIMP:** `duration_min * delta_ratio * 0.64 * exp(k * delta_ratio)` where k=1.92 male, delta_ratio = (avg_hr - rest_hr) / (max_hr - rest_hr)
- **Pace → rTSS:** `(duration/3600) * (threshold_pace/actual_pace)^2 * 100`

All three computed when data available. Training base selects which drives CTL/ATL/TSB.

### Configurable Zone Boundaries

4 boundaries define 5 zones. Stored in config as fractions of threshold.

| Base | Z1/Z2 | Z2/Z3 | Z3/Z4 | Z4/Z5 | Note |
|------|-------|-------|-------|-------|------|
| Power | 0.55 | 0.75 | 0.90 | 1.05 | Coggan-style |
| HR | 0.72 | 0.82 | 0.89 | 0.96 | Friel-style |
| Pace | 1.29 | 1.14 | 1.06 | 1.00 | Inverted (slower→faster) |

### Display Config

Included in every API response so frontend never hardcodes labels:

```json
{
  "threshold_label": "Critical Power",
  "threshold_abbrev": "CP",
  "threshold_unit": "W",
  "load_label": "RSS",
  "intensity_metric": "Power",
  "zone_names": ["Easy", "Tempo", "Threshold", "Supra-CP", "VO2max"],
  "trend_label": "CP Trend"
}
```

### Intensity Classification

Generalized from power-only to any base:

```python
def classify_intensity(base: TrainingBase, value: float, threshold: float) -> str:
    # Returns: "easy", "tempo", "threshold", "supra_threshold"
    # Uses configurable zone boundaries
```

Zone keys change from `supra_cp` to `supra_threshold` (base-agnostic).

## User Config

Stored as `data/config.json`. Database deferred to Sub-project 2.

```json
{
  "training_base": "power",
  "sources": {"activities": "garmin", "health": "oura", "plan": "stryd"},
  "thresholds": {
    "cp_watts": 280, "lthr_bpm": null, "threshold_pace_sec_km": null,
    "max_hr_bpm": 190, "rest_hr_bpm": 55, "source": "manual"
  },
  "zones": {
    "power": [0.55, 0.75, 0.90, 1.05],
    "hr": [0.72, 0.82, 0.89, 0.96],
    "pace": [1.29, 1.14, 1.06, 1.00]
  },
  "goal": {"race_date": "2026-04-15", "race_target_time_sec": 10800, "cp_target": 295}
}
```

### Settings API

- `GET /api/settings` — config + available providers + auto-detected thresholds + display config
- `PUT /api/settings` — partial update, invalidates dashboard cache

### Threshold Resolution

1. Auto-detect from all configured ThresholdProviders (Stryd → CP, Garmin → LTHR)
2. Manual overrides win
3. Settings UI shows both auto-detected and manual values

## New File Structure

```
analysis/
    config.py                    # UserConfig dataclass + JSON persistence
    zones.py                     # Zone calculation for all 3 bases
    training_base.py             # Display config per training base
    providers/
        __init__.py              # Registry
        base.py                  # ABCs
        models.py                # Canonical column defs + ThresholdEstimate
        garmin.py                # Garmin adapters
        stryd.py                 # Stryd adapters
        oura.py                  # Oura adapter
api/routes/
    settings.py                  # GET/PUT /api/settings
data/
    config.json                  # User configuration (gitignored)
web/src/
    contexts/SettingsContext.tsx  # App-wide display config
    hooks/useSettings.ts         # Settings fetch/update
    pages/Settings.tsx           # Settings page
```

## Migration Phases

1. **Config layer** — Add config module + settings endpoint. No behavior change.
2. **Provider interfaces** — Abstract providers wrapping existing CSV reading. Same data, new path.
3. **Training base system** — Add TRIMP/rTSS, parameterize diagnosis, configurable zones.
4. **Frontend adaptation** — Settings page, dynamic labels, SettingsContext.
5. **Threshold auto-detect** — ThresholdProviders, resolution logic, override UI.

Each phase independently deployable. System works at every intermediate state.

## Future Sub-projects

- **Sub-project 2:** User auth (JWT), multi-user (SQLAlchemy + PostgreSQL), cloud deployment
- **Sub-project 3:** Mobile app, WeChat miniprogram (consume same API)
