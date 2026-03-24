"""Zone calculation for all training bases."""
from analysis.config import TrainingBase, DEFAULT_ZONES


def compute_zones(
    base: TrainingBase,
    threshold_value: float,
    custom_boundaries: list[float] | None = None,
) -> list[dict]:
    """Compute 5 training zones based on training base and threshold.

    Args:
        base: "power", "hr", or "pace"
        threshold_value: CP (W), LTHR (bpm), or threshold pace (sec/km)
        custom_boundaries: 4 fractions defining zone boundaries; defaults used if None

    Returns:
        List of 5 zone dicts with: name, lower, upper, unit
    """
    boundaries = custom_boundaries or DEFAULT_ZONES[base]
    if len(boundaries) != 4:
        boundaries = DEFAULT_ZONES[base]

    if base == "power":
        unit = "W"
        names = ["Easy", "Tempo", "Threshold", "Supra-CP", "VO2max"]
        # Boundaries are fractions of CP; zones go low → high
        vals = [round(b * threshold_value) for b in boundaries]
        return [
            {"name": names[0], "lower": 0, "upper": vals[0], "unit": unit},
            {"name": names[1], "lower": vals[0], "upper": vals[1], "unit": unit},
            {"name": names[2], "lower": vals[1], "upper": vals[2], "unit": unit},
            {"name": names[3], "lower": vals[2], "upper": vals[3], "unit": unit},
            {"name": names[4], "lower": vals[3], "upper": None, "unit": unit},
        ]
    elif base == "hr":
        unit = "bpm"
        names = ["Recovery", "Aerobic", "Tempo", "Threshold", "VO2max"]
        vals = [round(b * threshold_value) for b in boundaries]
        return [
            {"name": names[0], "lower": 0, "upper": vals[0], "unit": unit},
            {"name": names[1], "lower": vals[0], "upper": vals[1], "unit": unit},
            {"name": names[2], "lower": vals[1], "upper": vals[2], "unit": unit},
            {"name": names[3], "lower": vals[2], "upper": vals[3], "unit": unit},
            {"name": names[4], "lower": vals[3], "upper": None, "unit": unit},
        ]
    else:  # pace
        unit = "sec/km"
        names = ["Recovery", "Easy", "Tempo", "Threshold", "Interval"]
        # Pace boundaries are inverted: higher fraction = slower pace
        vals = [round(b * threshold_value) for b in boundaries]
        # Zone 1 is slowest (highest sec/km), Zone 5 is fastest (lowest)
        return [
            {"name": names[0], "lower": vals[0], "upper": None, "unit": unit},
            {"name": names[1], "lower": vals[1], "upper": vals[0], "unit": unit},
            {"name": names[2], "lower": vals[2], "upper": vals[1], "unit": unit},
            {"name": names[3], "lower": vals[3], "upper": vals[2], "unit": unit},
            {"name": names[4], "lower": 0, "upper": vals[3], "unit": unit},
        ]


def classify_intensity(
    base: TrainingBase,
    value: float,
    threshold: float,
    boundaries: list[float] | None = None,
) -> str:
    """Classify a value into an intensity zone name.

    Args:
        base: "power", "hr", or "pace"
        value: power (W), HR (bpm), or pace (sec/km)
        threshold: CP, LTHR, or threshold pace
        boundaries: custom zone boundaries (4 fractions); defaults used if None

    Returns:
        Zone key: "easy", "tempo", "threshold", "supra_threshold"
    """
    bounds = boundaries or DEFAULT_ZONES[base]

    if base in ("power", "hr"):
        ratio = value / threshold if threshold > 0 else 0
        if ratio >= bounds[3]:
            return "supra_threshold"
        if ratio >= bounds[2]:
            return "threshold"
        if ratio >= bounds[1]:
            return "tempo"
        return "easy"
    else:  # pace — lower value = faster
        ratio = threshold / value if value > 0 else 0
        # bounds for pace are inverted: [1.29, 1.14, 1.06, 1.00]
        # ratio > 1.0 means running faster than threshold
        if ratio >= 1.0 / bounds[3]:  # faster than threshold boundary
            return "supra_threshold"
        if ratio >= 1.0 / bounds[2]:
            return "threshold"
        if ratio >= 1.0 / bounds[1]:
            return "tempo"
        return "easy"
