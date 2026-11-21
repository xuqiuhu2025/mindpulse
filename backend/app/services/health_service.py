"""健康数据服务：只接受按天聚合快照，撤回即拒收。"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models.db import HealthTrendSnapshot
from ..models.schemas import (
    HealthSnapshotIn,
    HealthSnapshotOut,
    HealthTrendOut,
    MetricTrendOut,
)
from .care_engine import CareEngine, METRIC_SPECS
from .consent_service import ConsentService

# 指标字段 -> consent scope
FIELD_TO_SCOPE = {
    "sleep_hours": "healthkit.sleep",
    "resting_hr": "healthkit.resting_heart_rate",
    "hrv_sdnn": "healthkit.hrv",
    "steps": "healthkit.steps",
}


class HealthService:
    def __init__(self, db: Session, *, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def ingest(self, device_id: str, snapshots: list[HealthSnapshotIn]) -> list[HealthSnapshotOut]:
        consent = ConsentService(self.db)
        active = consent.active_scopes(device_id)

        missing: set[str] = set()
        for snap in snapshots:
            for field, scope in FIELD_TO_SCOPE.items():
                if getattr(snap, field) is not None and scope not in active:
                    missing.add(scope)
        if missing:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "consent_required",
                    "missing_scopes": sorted(missing),
                    "message": "尚未授权或已撤回授权的指标不会写入；请在客户端重新授权或去除对应字段。",
                },
            )

        out: list[HealthSnapshotOut] = []
        for snap in snapshots:
            existing = (
                self.db.execute(
                    select(HealthTrendSnapshot).where(
                        HealthTrendSnapshot.device_id == device_id,
                        HealthTrendSnapshot.date == snap.date,
                    )
                )
                .scalars()
                .first()
            )
            target = existing or HealthTrendSnapshot(device_id=device_id, date=snap.date)
            target.sleep_hours = snap.sleep_hours if snap.sleep_hours is not None else target.sleep_hours
            target.resting_hr = snap.resting_hr if snap.resting_hr is not None else target.resting_hr
            target.hrv_sdnn = snap.hrv_sdnn if snap.hrv_sdnn is not None else target.hrv_sdnn
            target.steps = snap.steps if snap.steps is not None else target.steps
            target.source = snap.source
            if existing is None:
                self.db.add(target)
            self.db.flush()
            out.append(
                HealthSnapshotOut(
                    date=target.date,
                    sleep_hours=target.sleep_hours,
                    resting_hr=target.resting_hr,
                    hrv_sdnn=target.hrv_sdnn,
                    steps=target.steps,
                    source=target.source,
                )
            )
        self.db.commit()
        return out

    def list_snapshots(self, device_id: str, days: int = 30) -> list[HealthSnapshotOut]:
        since = (date.today() - timedelta(days=days)).isoformat()
        rows = (
            self.db.execute(
                select(HealthTrendSnapshot)
                .where(HealthTrendSnapshot.device_id == device_id, HealthTrendSnapshot.date >= since)
                .order_by(HealthTrendSnapshot.date.desc())
            )
            .scalars()
            .all()
        )
        return [
            HealthSnapshotOut(
                date=r.date,
                sleep_hours=r.sleep_hours,
                resting_hr=r.resting_hr,
                hrv_sdnn=r.hrv_sdnn,
                steps=r.steps,
                source=r.source,
            )
            for r in rows
        ]

    def trends(self, device_id: str) -> HealthTrendOut:
        """聚合趋势视图。数据不足时明确说明，不做任何解读。"""
        consent = ConsentService(self.db)
        active = consent.active_scopes(device_id)
        engine = CareEngine(self.db, settings=self.settings)

        snapshots = engine._load_snapshots(device_id)
        metrics: list[MetricTrendOut] = []

        for spec in METRIC_SPECS:
            granted = spec.scope in active
            values = [getattr(s, spec.field) for s in snapshots if getattr(s, spec.field) is not None]
            ev = engine._metric_evaluation(device_id, spec, snapshots, active)

            if not granted:
                metrics.append(
                    MetricTrendOut(
                        metric=spec.key,
                        label=spec.label,
                        unit=spec.unit,
                        consent_granted=False,
                        data_points=0,
                        baseline_days=0,
                        description=None,
                        insufficient_data=True,
                    )
                )
                continue

            if not ev.get("evaluated"):
                metrics.append(
                    MetricTrendOut(
                        metric=spec.key,
                        label=spec.label,
                        unit=spec.unit,
                        consent_granted=True,
                        data_points=ev.get("data_points", len(values)),
                        baseline_days=0,
                        description=None,
                        insufficient_data=True,
                    )
                )
                continue

            baseline = ev["baseline"]
            recent = ev["recent"]
            if spec.kind == "ratio" and baseline > 0:
                pct = round((recent - baseline) / baseline * 100)
                direction = "低" if pct < 0 else "高"
                description = f"近 3 天平均{spec.label}比之前的基线{direction}约 {abs(pct)}%（自我参考趋势，非医学结论）。"
            elif spec.kind == "delta":
                diff = round(recent - baseline, 1)
                direction = "高" if diff > 0 else "低"
                description = f"近 3 天平均{spec.label}比之前的基线{direction}约 {abs(diff)} {spec.unit}（自我参考趋势，非医学结论）。"
            else:
                description = f"近 3 天平均{spec.label}与之前的基线接近。"

            metrics.append(
                MetricTrendOut(
                    metric=spec.key,
                    label=spec.label,
                    unit=spec.unit,
                    consent_granted=True,
                    data_points=ev.get("data_points", len(values)),
                    baseline_days=ev.get("baseline_days", 0),
                    recent_average=round(recent, 2),
                    baseline_average=round(baseline, 2),
                    deviation_detected=bool(ev.get("deviated")),
                    description=description,
                    insufficient_data=False,
                )
            )

        return HealthTrendOut(metrics=metrics)
