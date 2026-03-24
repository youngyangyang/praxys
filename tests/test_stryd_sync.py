from sync.stryd_sync import (
    parse_activity_detail,
    parse_calendar_button_text,
    parse_training_plan,
    _parse_duration_to_minutes,
    _parse_duration_to_seconds,
    _parse_distance_km,
    _parse_power_range,
    _parse_stat_value,
    _workout_type_from_name,
    _parse_structured_intervals,
)


# --- Training plan parsing ---


SAMPLE_PLAN_WORKOUT = {
    "date": "2026-03-15",
    "workout_type": "tempo",
    "duration_minutes": 60,
    "distance_km": 12.0,
    "power_target_low": 230,
    "power_target_high": 250,
    "workout_description": "Warmup 5min@189-216W | 2x(20min@251-262W + Recover 5min@162-189W) | Cooldown 5min@189-216W",
}


def test_parse_training_plan():
    rows = parse_training_plan([SAMPLE_PLAN_WORKOUT])
    assert len(rows) == 1
    r = rows[0]
    assert r["date"] == "2026-03-15"
    assert r["workout_type"] == "tempo"
    assert r["planned_duration_min"] == "60"
    assert r["target_power_min"] == "230"
    assert r["target_power_max"] == "250"
    assert "Warmup" in r["workout_description"]
    assert "Cooldown" in r["workout_description"]


# --- Calendar button text parsing ---


def test_parse_calendar_button_text():
    text = "stryd Day 46 - Steady Aerobic 1:00:00 11.38km 52RSS"
    result = parse_calendar_button_text(text)
    assert result is not None
    assert result["workout_name"] == "Day 46 - Steady Aerobic"
    assert result["workout_type"] == "steady aerobic"
    assert result["duration_minutes"] == 60.0
    assert result["distance_km"] == 11.38


def test_parse_calendar_button_text_short_duration():
    text = "stryd Day 47 - Recovery 45:00 7.34km 23RSS"
    result = parse_calendar_button_text(text)
    assert result is not None
    assert result["workout_type"] == "recovery"
    assert result["duration_minutes"] == 45.0
    assert result["distance_km"] == 7.34


def test_parse_calendar_button_text_long_run():
    text = "stryd Day 48 - Long 2:45:00 30.39km 133RSS"
    result = parse_calendar_button_text(text)
    assert result is not None
    assert result["workout_type"] == "long"
    assert result["duration_minutes"] == 165.0
    assert result["distance_km"] == 30.39


def test_parse_calendar_button_text_no_distance():
    """Card text without distance should still parse via fallback."""
    text = "Day 50 - Recovery\n45:00\n23RSS"
    result = parse_calendar_button_text(text)
    assert result is not None
    assert result["workout_type"] == "recovery"
    assert result["duration_minutes"] == 45.0
    assert result["distance_km"] is None


def test_parse_calendar_button_text_with_day_number_prefix():
    """Card text from calendar cell may have day number prefix."""
    text = "19\nDay 46 - Steady Aerobic\n1:00:00\n11.38km\n52RSS"
    result = parse_calendar_button_text(text)
    assert result is not None
    assert result["workout_type"] == "steady aerobic"
    assert result["duration_minutes"] == 60.0
    assert result["distance_km"] == 11.38


def test_parse_calendar_button_text_name_only():
    """Card text with just workout name and no metrics."""
    text = "Day 50 - Recovery"
    result = parse_calendar_button_text(text)
    assert result is not None
    assert result["workout_type"] == "recovery"
    assert result["duration_minutes"] is None
    assert result["distance_km"] is None


def test_parse_calendar_button_text_invalid():
    assert parse_calendar_button_text("not a workout") is None
    assert parse_calendar_button_text("") is None


# --- Activity detail parsing ---


def test_parse_activity_detail():
    stats = {
        "date_str": "2026-03-18",
        "start_time_str": "2026-03-18T16:21:00",
        "moving_time": "1:00:01",
        "distance": "11.22 km",
        "power": "220 W",
        "form_power": "63 W",
        "gct": "249 ms",
        "lss": "9.5 kN/m",
        "rss": "61",
        "cp": "270",
    }
    row = parse_activity_detail(stats)
    assert row["date"] == "2026-03-18"
    assert row["start_time"] == "2026-03-18T16:21:00"
    assert row["avg_power"] == "220"
    assert row["form_power"] == "63"
    assert row["ground_time_ms"] == "249"
    assert row["leg_spring_stiffness"] == "9.5"
    assert row["rss"] == "61"
    assert row["cp_estimate"] == "270"
    assert row["distance_km"] == "11.22"
    assert row["duration_sec"] == "3601"
    assert row["max_power"] == ""  # not available from detail view


def test_parse_activity_detail_minimal():
    stats = {"date_str": "2026-03-16", "start_time_str": "2026-03-16T11:45:00"}
    row = parse_activity_detail(stats)
    assert row["date"] == "2026-03-16"
    assert row["avg_power"] == ""
    assert row["rss"] == ""


# --- Helper function tests ---


def test_parse_duration_to_minutes():
    assert _parse_duration_to_minutes("1:00:00") == 60.0
    assert _parse_duration_to_minutes("45:00") == 45.0
    assert _parse_duration_to_minutes("2:30:00") == 150.0
    assert _parse_duration_to_minutes("invalid") is None


def test_parse_duration_to_seconds():
    assert _parse_duration_to_seconds("1:00:01") == 3601
    assert _parse_duration_to_seconds("30:22") == 1822
    assert _parse_duration_to_seconds("2:45:00") == 9900
    assert _parse_duration_to_seconds("invalid") is None


def test_parse_distance_km():
    assert _parse_distance_km("11.38km") == 11.38
    assert _parse_distance_km("11.22 km") == 11.22
    assert _parse_distance_km("no distance") is None


def test_parse_power_range():
    assert _parse_power_range("206 - 231 W") == (206, 231)
    assert _parse_power_range("206 – 231 W") == (206, 231)  # en-dash
    assert _parse_power_range("206 — 231 W") == (206, 231)  # em-dash
    assert _parse_power_range("no power") == (None, None)


def test_parse_stat_value():
    assert _parse_stat_value("220 W") == "220"
    assert _parse_stat_value("9.5 kN/m") == "9.5"
    assert _parse_stat_value("249 ms") == "249"
    assert _parse_stat_value("--") == ""


def test_workout_type_from_name():
    assert _workout_type_from_name("Day 46 - Steady Aerobic") == "steady aerobic"
    assert _workout_type_from_name("Day 48 - Long") == "long"
    assert _workout_type_from_name("Day 47 - Recovery") == "recovery"
    assert _workout_type_from_name("Custom Name") == "custom name"


# --- End-to-end: calendar → training plan CSV ---


def test_parse_calendar_to_training_plan():
    btn_text = "stryd Day 46 - Steady Aerobic 1:00:00 11.38km 52RSS"
    parsed = parse_calendar_button_text(btn_text)
    parsed["date"] = "2026-03-19"
    parsed["power_target_low"] = 206
    parsed["power_target_high"] = 231
    parsed["workout_description"] = ""

    rows = parse_training_plan([parsed])
    assert len(rows) == 1
    r = rows[0]
    assert r["date"] == "2026-03-19"
    assert r["workout_type"] == "steady aerobic"
    assert r["planned_duration_min"] == "60.0"
    assert r["planned_distance_km"] == "11.38"
    assert r["target_power_min"] == "206"
    assert r["target_power_max"] == "231"
    assert r["workout_description"] == ""


# --- Structured interval parsing ---


def test_parse_structured_intervals_threshold():
    modal_text = """
Warmup:
S:1  4:59  | Target: 189 - 216 W
Run/Recover:
x2  20:00 | Target: 251 - 262 W
5:00 | Target: 162 - 189 W
Cooldown:
S:6  5:01  | Target: 189 - 216 W
"""
    desc, p_low, p_high = _parse_structured_intervals(modal_text)
    assert "Warmup" in desc
    assert "Cooldown" in desc
    assert "251-262W" in desc
    # Main set should be the highest power (Run at 251-262W)
    assert p_low == 251
    assert p_high == 262


def test_parse_structured_intervals_simple_splits():
    modal_text = """
Splits:
S:1 1:00:00 Run | 206 - 231 W | 76 - 85%
"""
    desc, p_low, p_high = _parse_structured_intervals(modal_text)
    assert desc == ""  # Simple splits don't generate description
    assert p_low == 206
    assert p_high == 231


def test_parse_structured_intervals_no_sections():
    modal_text = "Some random text with 220 - 240 W power target"
    desc, p_low, p_high = _parse_structured_intervals(modal_text)
    assert desc == ""
    assert p_low == 220
    assert p_high == 240


def test_parse_structured_intervals_no_power():
    modal_text = "No power info here at all"
    desc, p_low, p_high = _parse_structured_intervals(modal_text)
    assert desc == ""
    assert p_low is None
    assert p_high is None
