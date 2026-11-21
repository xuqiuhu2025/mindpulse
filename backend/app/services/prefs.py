"""用户偏好（按 device_id 的轻量设置）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models.db import UserPrefs


def get_or_create_prefs(db: Session, device_id: str) -> UserPrefs:
    prefs = db.get(UserPrefs, device_id)
    if prefs is None:
        prefs = UserPrefs(device_id=device_id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs
