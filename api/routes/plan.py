"""Upcoming training plan endpoint."""
from datetime import date

import pandas as pd
from fastapi import APIRouter

from api.deps import get_dashboard_data

router = APIRouter()


@router.get("/plan")
def get_plan() -> dict:
    """Return upcoming planned workouts (today + next 14 days)."""
    data = get_dashboard_data()
    plan_df: pd.DataFrame = data.get("plan", pd.DataFrame())
    today = date.today()

    if plan_df.empty:
        return {"workouts": [], "cp_current": None}

    # Filter for today onwards
    upcoming = plan_df[plan_df["date"] >= today].sort_values("date").head(14)

    workouts = []
    for _, row in upcoming.iterrows():
        workout = {
            "date": row["date"].isoformat() if hasattr(row["date"], "isoformat") else str(row["date"]),
            "workout_type": row.get("workout_type", ""),
        }
        for field, csv_col in [
            ("duration_min", "planned_duration_min"),
            ("distance_km", "planned_distance_km"),
            ("power_min", "target_power_min"),
            ("power_max", "target_power_max"),
            ("description", "workout_description"),
        ]:
            val = row.get(csv_col)
            if pd.notna(val) and val != "":
                workout[field] = float(val) if field != "description" else str(val)
        workouts.append(workout)

    # Get current CP from the latest activity data if available
    cp_current = None
    signal = data.get("signal", {})
    if isinstance(signal, dict):
        plan = signal.get("plan", {})
        if isinstance(plan, dict) and plan.get("power_max"):
            cp_current = plan.get("power_max")

    return {"workouts": workouts, "cp_current": cp_current}
