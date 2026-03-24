"""Race / CP goal endpoint."""
from fastapi import APIRouter

from api.deps import get_dashboard_data

router = APIRouter()


@router.get("/goal")
def get_goal():
    data = get_dashboard_data()
    return {
        "race_countdown": data["race_countdown"],
        "cp_trend": data["cp_trend"],
        "cp_trend_data": data["cp_trend_data"],
        "latest_cp": data["latest_cp"],
        "training_base": data["training_base"],
        "display": data["display"],
    }
