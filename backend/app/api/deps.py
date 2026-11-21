"""路由公共依赖：AppContext、数据库会话、伪匿名设备标识。"""

from __future__ import annotations

import re

from fastapi import Header, HTTPException, Request
from sqlalchemy.orm import Session

_DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def get_ctx(request: Request):
    return request.app.state.ctx


def get_db(request: Request):
    ctx = request.app.state.ctx
    db: Session = ctx.sessionmaker()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_device_id(x_device_id: str = Header(default="")) -> str:
    """伪匿名设备标识：客户端本地生成 UUID，不含任何真实身份信息。"""
    if not _DEVICE_ID_RE.match(x_device_id):
        raise HTTPException(
            status_code=422,
            detail="缺少或非法的 X-Device-ID 头（8-64 位字母/数字/连字符/下划线）",
        )
    return x_device_id
