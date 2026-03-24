"""Activity history endpoint."""
from fastapi import APIRouter, Query

from api.deps import get_dashboard_data

router = APIRouter()


@router.get("/history")
def get_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    data = get_dashboard_data()
    activities = data["activities"]
    total = len(activities)
    page = activities[offset : offset + limit]
    return {
        "activities": page,
        "total": total,
        "limit": limit,
        "offset": offset,
        "training_base": data["training_base"],
        "display": data["display"],
    }
