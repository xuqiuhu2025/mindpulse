"""同意（consent）服务：任何 HealthKit 数据读写前必须存在有效同意记录。

撤回是即时生效的：撤回后快照写入被拒绝、主动关心引擎忽略对应指标。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.db import ConsentRecord
from ..models.schemas import ConsentOut

VALID_SCOPES = {
    "healthkit.sleep",
    "healthkit.resting_heart_rate",
    "healthkit.hrv",
    "healthkit.steps",
}


class ConsentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def grant(self, device_id: str, scope: str, policy_version: str = "v1") -> ConsentOut:
        assert scope in VALID_SCOPES, f"unknown scope: {scope}"
        record = ConsentRecord(
            device_id=device_id, scope=scope, granted=True, policy_version=policy_version
        )
        self.db.add(record)
        self.db.commit()
        return ConsentOut(
            scope=record.scope,
            granted=True,
            policy_version=record.policy_version,
            granted_at=record.granted_at,
            revoked_at=None,
        )

    def revoke(self, device_id: str, scope: str) -> ConsentOut | None:
        assert scope in VALID_SCOPES, f"unknown scope: {scope}"
        active = (
            self.db.execute(
                select(ConsentRecord)
                .where(
                    ConsentRecord.device_id == device_id,
                    ConsentRecord.scope == scope,
                    ConsentRecord.granted.is_(True),
                    ConsentRecord.revoked_at.is_(None),
                )
                .order_by(ConsentRecord.granted_at.desc())
            )
            .scalars()
            .first()
        )
        if active is None:
            return None
        from ..models.db import utcnow

        active.revoked_at = utcnow()
        self.db.commit()
        return ConsentOut(
            scope=active.scope,
            granted=False,
            policy_version=active.policy_version,
            granted_at=active.granted_at,
            revoked_at=active.revoked_at,
        )

    def active_scopes(self, device_id: str) -> set[str]:
        rows = (
            self.db.execute(
                select(ConsentRecord).where(
                    ConsentRecord.device_id == device_id,
                    ConsentRecord.granted.is_(True),
                    ConsentRecord.revoked_at.is_(None),
                )
            )
            .scalars()
            .all()
        )
        return {r.scope for r in rows}

    def list_records(self, device_id: str) -> list[ConsentOut]:
        rows = (
            self.db.execute(
                select(ConsentRecord)
                .where(ConsentRecord.device_id == device_id)
                .order_by(ConsentRecord.granted_at.desc())
            )
            .scalars()
            .all()
        )
        return [
            ConsentOut(
                scope=r.scope,
                granted=r.granted,
                policy_version=r.policy_version,
                granted_at=r.granted_at,
                revoked_at=r.revoked_at,
            )
            for r in rows
        ]
