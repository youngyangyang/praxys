"""Today's training signal endpoint."""
from fastapi import APIRouter

from api.deps import get_dashboard_data

router = APIRouter()


@router.get("/today")
def get_today():
    data = get_dashboard_data()
    return {
        "signal": data["signal"],
        "tsb_sparkline": data["tsb_sparkline"],
        "warnings": data["warnings"],
        "training_base": data["training_base"],
        "display": data["display"],
    }
