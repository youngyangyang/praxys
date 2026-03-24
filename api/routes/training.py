"""Training analysis endpoint."""
from fastapi import APIRouter

from api.deps import get_dashboard_data

router = APIRouter()


@router.get("/training")
def get_training():
    data = get_dashboard_data()
    return {
        "diagnosis": data["diagnosis"],
        "fitness_fatigue": data["fitness_fatigue"],
        "cp_trend": data["cp_trend"],
        "weekly_review": data["weekly_review"],
        "workout_flags": data["workout_flags"],
        "sleep_perf": data["sleep_perf"],
        "training_base": data["training_base"],
        "display": data["display"],
    }
