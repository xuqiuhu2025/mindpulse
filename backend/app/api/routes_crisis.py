"""危机资源路由（公开，无需设备标识）。

不硬编码单一热线：返回带来源与核对日期的本地资源 + 国际目录兜底；
无法确认所在地时返回 need_country=true，由客户端询问用户。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..models.schemas import CrisisInfo
from ..services.crisis_resources import CrisisResourceService
from .deps import get_ctx

router = APIRouter(tags=["crisis"])


@router.get("/crisis/resources", response_model=CrisisInfo)
def crisis_resources(
    country: str | None = Query(default=None, min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$"),
    ctx=Depends(get_ctx),
):
    crisis: CrisisResourceService = ctx.crisis
    return crisis.get(country)
