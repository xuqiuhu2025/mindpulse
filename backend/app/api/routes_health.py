"""健康数据与主动关心路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models.schemas import (
    CareSettingsIn,
    CareSettingsOut,
    CareSuggestion,
    DismissCareRequest,
    HealthSnapshotIn,
    HealthSnapshotOut,
    HealthTrendOut,
)
from ..services.care_engine import CareEngine
from ..services.health_service import HealthService
from ..services.prefs import get_or_create_prefs
from .deps import get_ctx, get_db, get_device_id

router = APIRouter(tags=["health"])


@router.post("/health/snapshots", response_model=list[HealthSnapshotOut])
def ingest_snapshots(
    snapshots: list[HealthSnapshotIn],
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
    ctx=Depends(get_ctx),
):
    if not snapshots or len(snapshots) > 45:
        raise HTTPException(status_code=422, detail="单次最多上传 45 天的聚合快照")
    return HealthService(db, settings=ctx.settings).ingest(device_id, snapshots)


@router.get("/health/snapshots", response_model=list[HealthSnapshotOut])
def list_snapshots(
    days: int = 30,
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
    ctx=Depends(get_ctx),
):
    return HealthService(db, settings=ctx.settings).list_snapshots(device_id, days)


@router.get("/health/trends", response_model=HealthTrendOut)
def health_trends(
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
    ctx=Depends(get_ctx),
):
    return HealthService(db, settings=ctx.settings).trends(device_id)


@router.get("/care/suggestions", response_model=CareSuggestion)
def care_suggestions(
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
    ctx=Depends(get_ctx),
):
    return CareEngine(db, settings=ctx.settings).evaluate(device_id)


@router.get("/care/settings", response_model=CareSettingsOut)
def get_care_settings(
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
):
    prefs = get_or_create_prefs(db, device_id)
    return CareSettingsOut(enabled=prefs.care_enabled, frequency=prefs.care_frequency)


@router.put("/care/settings", response_model=CareSettingsOut)
def update_care_settings(
    req: CareSettingsIn,
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
):
    prefs = get_or_create_prefs(db, device_id)
    if req.enabled is not None:
        prefs.care_enabled = req.enabled
    if req.frequency is not None:
        prefs.care_frequency = req.frequency
    db.commit()
    return CareSettingsOut(enabled=prefs.care_enabled, frequency=prefs.care_frequency)


@router.post("/care/dismiss", response_model=CareSettingsOut)
def dismiss_care(
    req: DismissCareRequest,
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
):
    """忽略本条提示，或彻底关闭此类主动关心。"""
    prefs = get_or_create_prefs(db, device_id)
    if req.scope == "all":
        prefs.care_enabled = False
        prefs.care_frequency = "off"
    db.commit()
    return CareSettingsOut(enabled=prefs.care_enabled, frequency=prefs.care_frequency)
