"""心情记录路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..models.schemas import MoodEntryIn, MoodEntryOut, MoodTrendOut, SafetyInfo
from ..services.mood_service import MoodService
from .deps import get_ctx, get_db, get_device_id

router = APIRouter(tags=["mood"])


@router.post("/mood")
def add_mood(
    req: MoodEntryIn,
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
    ctx=Depends(get_ctx),
) -> dict:
    entry, safety = MoodService(db, guard=ctx.guard, crisis=ctx.crisis).add_mood(device_id, req)
    return {"entry": entry, "safety": safety}


@router.get("/mood", response_model=list[MoodEntryOut])
def list_moods(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
):
    return MoodService(db, guard=None, crisis=None).list_moods(device_id, limit)


@router.get("/mood/trends", response_model=MoodTrendOut)
def mood_trends(
    window: int = Query(default=7, description="统计窗口天数：7 或 30"),
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
    ctx=Depends(get_ctx),
):
    if window not in (7, 30):
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="window 仅支持 7 或 30")
    return MoodService(db, guard=None, crisis=None).trends(device_id, window)
