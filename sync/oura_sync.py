"""Sync sleep and readiness data from Oura Ring API v2."""
import argparse
import os
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

from sync.csv_utils import append_rows

OURA_BASE = "https://api.ouraring.com/v2/usercollection"


def fetch_sleep_data(token: str, start_date: str, end_date: str) -> list[dict]:
    """Fetch detailed sleep records from Oura API v2."""
    url = f"{OURA_BASE}/sleep"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"start_date": start_date, "end_date": end_date}
    all_data = []
    while True:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        body = resp.json()
        all_data.extend(body.get("data", []))
        next_token = body.get("next_token")
        if not next_token:
            break
        params["next_token"] = next_token
    return all_data


def fetch_readiness_data(token: str, start_date: str, end_date: str) -> list[dict]:
    """Fetch daily readiness records from Oura API."""
    url = f"{OURA_BASE}/daily_readiness"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"start_date": start_date, "end_date": end_date}
    all_data = []
    while True:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        body = resp.json()
        all_data.extend(body.get("data", []))
        next_token = body.get("next_token")
        if not next_token:
            break
        params["next_token"] = next_token
    return all_data


def parse_sleep_records(raw_records: list[dict]) -> list[dict]:
    """Transform Oura sleep API response into our CSV schema."""
    rows = []
    for r in raw_records:
        readiness = r.get("readiness") or {}
        rows.append({
            "date": r.get("day", ""),
            "sleep_score": str(readiness.get("score", "")),
            "total_sleep_sec": str(r.get("total_sleep_duration", "")),
            "deep_sleep_sec": str(r.get("deep_sleep_duration", "")),
            "rem_sleep_sec": str(r.get("rem_sleep_duration", "")),
            "light_sleep_sec": str(r.get("light_sleep_duration", "")),
            "efficiency": str(r.get("efficiency", "")),
        })
    return rows


def parse_readiness_records(raw_records: list[dict]) -> list[dict]:
    """Transform Oura readiness API response into our CSV schema."""
    rows = []
    for r in raw_records:
        rows.append({
            "date": r.get("day", ""),
            "readiness_score": str(r.get("score", "")),
            "hrv_avg": "",
            "resting_hr": "",
            "body_temperature_delta": str(r.get("temperature_deviation", "")),
        })
    return rows


def sync(token: str, data_dir: str, from_date: str | None = None) -> None:
    """Pull Oura data and save to CSVs."""
    end = date.today().isoformat()
    start = from_date or (date.today() - timedelta(days=7)).isoformat()

    print(f"Oura: syncing {start} to {end}")

    sleep_raw = fetch_sleep_data(token, start, end)
    sleep_rows = parse_sleep_records(sleep_raw)
    sleep_path = os.path.join(data_dir, "oura", "sleep.csv")
    append_rows(sleep_path, sleep_rows, key_column="date")
    print(f"  Sleep: {len(sleep_rows)} records")

    hrv_by_date = {}
    for r in sleep_raw:
        d = r.get("day", "")
        hrv_by_date[d] = {
            "hrv_avg": str(r.get("average_hrv", "")),
            "resting_hr": str(r.get("average_heart_rate", "")),
        }

    readiness_raw = fetch_readiness_data(token, start, end)
    readiness_rows = parse_readiness_records(readiness_raw)
    for row in readiness_rows:
        extra = hrv_by_date.get(row["date"], {})
        row["hrv_avg"] = extra.get("hrv_avg", row["hrv_avg"])
        row["resting_hr"] = extra.get("resting_hr", row["resting_hr"])

    readiness_path = os.path.join(data_dir, "oura", "readiness.csv")
    append_rows(readiness_path, readiness_rows, key_column="date")
    print(f"  Readiness: {len(readiness_rows)} records")


if __name__ == "__main__":
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    parser = argparse.ArgumentParser(description="Sync Oura Ring data")
    parser.add_argument("--from-date", help="Start date (YYYY-MM-DD) for historical backfill")
    args = parser.parse_args()

    token = os.environ["OURA_TOKEN"]
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    sync(token, data_dir, args.from_date)
