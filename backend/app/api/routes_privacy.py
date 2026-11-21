"""隐私路由：同意管理、数据导出、彻底删除。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models.schemas import ConsentIn, ConsentOut, DeleteResultOut, ExportOut
from ..services.consent_service import VALID_SCOPES, ConsentService
from ..services.data_service import DataService
from .deps import get_db, get_device_id

router = APIRouter(tags=["privacy"])


@router.get("/consent", response_model=list[ConsentOut])
def list_consent(db: Session = Depends(get_db), device_id: str = Depends(get_device_id)):
    return ConsentService(db).list_records(device_id)


@router.post("/consent", response_model=ConsentOut)
def set_consent(
    req: ConsentIn,
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
):
    if req.scope not in VALID_SCOPES:
        raise HTTPException(status_code=422, detail=f"未知 scope：{req.scope}")
    service = ConsentService(db)
    if req.granted:
        return service.grant(device_id, req.scope, req.policy_version)
    result = service.revoke(device_id, req.scope)
    if result is not None:
        return result
    # 没有生效授权也返回一次“已撤销”状态，保持客户端状态一致
    now = datetime.now(timezone.utc)
    return ConsentOut(
        scope=req.scope, granted=False, policy_version=req.policy_version, granted_at=now, revoked_at=now
    )


@router.get("/data/export", response_model=ExportOut)
def export_data(db: Session = Depends(get_db), device_id: str = Depends(get_device_id)):
    return DataService(db).export(device_id)


@router.delete("/data/all", response_model=DeleteResultOut)
def delete_all_data(db: Session = Depends(get_db), device_id: str = Depends(get_device_id)):
    counts = DataService(db).delete_all(device_id)
    return DeleteResultOut(deleted=counts)
