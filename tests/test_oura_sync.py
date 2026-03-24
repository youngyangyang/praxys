import json
from unittest.mock import patch, MagicMock
from sync.oura_sync import fetch_sleep_data, fetch_readiness_data, parse_sleep_records, parse_readiness_records

SAMPLE_SLEEP_RESPONSE = {
    "data": [
        {
            "day": "2026-03-10",
            "total_sleep_duration": 28800,
            "deep_sleep_duration": 7200,
            "rem_sleep_duration": 5400,
            "light_sleep_duration": 16200,
            "efficiency": 92,
            "readiness": {"score": 85},
            "average_hrv": 45,
            "average_heart_rate": 52,
        }
    ],
    "next_token": None,
}

SAMPLE_READINESS_RESPONSE = {
    "data": [
        {
            "day": "2026-03-10",
            "score": 82,
            "temperature_deviation": 0.1,
            "timestamp": "2026-03-10T08:00:00+00:00",
        }
    ],
    "next_token": None,
}


def test_parse_sleep_records():
    records = parse_sleep_records(SAMPLE_SLEEP_RESPONSE["data"])
    assert len(records) == 1
    r = records[0]
    assert r["date"] == "2026-03-10"
    assert r["total_sleep_sec"] == "28800"
    assert r["deep_sleep_sec"] == "7200"
    assert r["efficiency"] == "92"
    assert r["sleep_score"] == "85"


def test_parse_readiness_records():
    records = parse_readiness_records(SAMPLE_READINESS_RESPONSE["data"])
    assert len(records) == 1
    r = records[0]
    assert r["date"] == "2026-03-10"
    assert r["readiness_score"] == "82"
    assert r["body_temperature_delta"] == "0.1"


@patch("sync.oura_sync.requests.get")
def test_fetch_sleep_data(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_SLEEP_RESPONSE
    mock_get.return_value = mock_resp

    data = fetch_sleep_data("fake_token", "2026-03-01", "2026-03-10")
    assert len(data) == 1
    mock_get.assert_called_once()
    call_url = mock_get.call_args[0][0]
    assert "/sleep" in call_url


@patch("sync.oura_sync.requests.get")
def test_fetch_readiness_data(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_READINESS_RESPONSE
    mock_get.return_value = mock_resp

    data = fetch_readiness_data("fake_token", "2026-03-01", "2026-03-10")
    assert len(data) == 1
