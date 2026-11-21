"""主动关心引擎（care engine）。

触发条件（全部满足才可能出现一条提示）：
1. 用户已授权相关指标（consent 有效）；
2. 有足够的历史基线（每个指标 ≥ care_min_baseline_days 天数据，不含最近窗口）；
3. 多项指标同时偏离基线，或单项指标偏离持续 ≥ care_sustained_min_days / 7 天；
4. 用户偏好未关闭主动关心。

语言原则：
- 永远使用不确定性表达（“和之前不太一样”“也可能只是……”）；
- 永远不出现疾病名称、诊断性分数或“HRV 下降所以……”式因果推断；
- 每条建议必须附带“为什么出现这条提示”的 reasons；
- 用户可以忽略/关闭（见 routes_health 的 dismiss 与 settings 接口）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models.db import HealthTrendSnapshot
from ..models.schemas import CareReason, CareSuggestion
from .consent_service import ConsentService
from .prefs import get_or_create_prefs

logger = logging.getLogger("mindpulse.care")


@dataclass(frozen=True)
class MetricSpec:
    key: str            # 对外名称（出现在建议的 metrics 列表里）
    field: str          # HealthTrendSnapshot 上的数据库字段名
    scope: str          # 对应 ConsentService 的 scope
    label: str          # 面向用户的中性名称
    unit: str
    kind: str           # "ratio"（按比例下降）| "delta"（按绝对值上升）
    threshold: Callable[[Settings], float]


METRIC_SPECS: tuple[MetricSpec, ...] = (
    MetricSpec("sleep", "sleep_hours", "healthkit.sleep", "睡眠", "小时", "ratio", lambda s: s.care_sleep_drop_ratio),
    MetricSpec("resting_hr", "resting_hr", "healthkit.resting_heart_rate", "静息心率", "次/分", "delta", lambda s: s.care_resting_hr_delta),
    MetricSpec("hrv", "hrv_sdnn", "healthkit.hrv", "心率变异性", "毫秒", "ratio", lambda s: s.care_hrv_drop_ratio),
    MetricSpec("steps", "steps", "healthkit.steps", "活动量", "步", "ratio", lambda s: s.care_steps_drop_ratio),
)

# 允许出现在建议文案里的中性词；同时用于测试断言输出中不存在疾病词汇
METRIC_LABELS = {m.key: m.label for m in METRIC_SPECS}


class CareEngine:
    def __init__(self, db: Session, *, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    # ------------------------------------------------------------------

    def _load_snapshots(self, device_id: str) -> list[HealthTrendSnapshot]:
        since = (datetime.now(timezone.utc) - timedelta(days=45)).date().isoformat()
        rows = (
            self.db.execute(
                select(HealthTrendSnapshot)
                .where(HealthTrendSnapshot.device_id == device_id, HealthTrendSnapshot.date >= since)
                .order_by(HealthTrendSnapshot.date.asc())
            )
            .scalars()
            .all()
        )
        return list(rows)

    @staticmethod
    def _metric_series(snapshots: list[HealthTrendSnapshot], attr: str) -> list[float]:
        return [getattr(s, attr) for s in snapshots if getattr(s, attr) is not None]

    def _metric_evaluation(self, device_id: str, spec: MetricSpec, snapshots: list[HealthTrendSnapshot], active_scopes: set[str]) -> dict:
        """返回该指标是否偏离、是否持续偏离，以及基线信息。"""
        if spec.scope not in active_scopes:
            return {"evaluated": False, "reason_code": "consent_gate"}

        values = self._metric_series(snapshots, spec.field)
        cfg = self.settings
        recent_n = cfg.care_recent_days
        baseline_values = values[:-recent_n]
        recent_values = values[-recent_n:]

        if len(baseline_values) < cfg.care_min_baseline_days or len(recent_values) < recent_n:
            return {
                "evaluated": False,
                "reason_code": "insufficient_data",
                "data_points": len(values),
            }

        baseline = mean(baseline_values)
        recent = mean(recent_values)
        threshold = spec.threshold(cfg)

        if spec.kind == "ratio":
            deviated = recent <= baseline * (1 - threshold)
        else:  # delta（静息心率上升）
            deviated = recent >= baseline + threshold

        # 持续性：最近 N 天窗口内逐日偏离天数
        sustained = False
        sustained_days = 0
        if deviated and len(values) >= cfg.care_sustained_window_days:
            window = values[-cfg.care_sustained_window_days:]
            for v in window:
                if spec.kind == "ratio":
                    if v <= baseline * (1 - threshold):
                        sustained_days += 1
                else:
                    if v >= baseline + threshold:
                        sustained_days += 1
            sustained = sustained_days >= cfg.care_sustained_min_days

        return {
            "evaluated": True,
            "deviated": deviated,
            "sustained": sustained,
            "sustained_days": sustained_days,
            "baseline": baseline,
            "recent": recent,
            "baseline_days": len(baseline_values),
            "data_points": len(values),
        }

    # ------------------------------------------------------------------

    def evaluate(self, device_id: str) -> CareSuggestion:
        prefs = get_or_create_prefs(self.db, device_id)
        if not prefs.care_enabled or prefs.care_frequency == "off":
            return CareSuggestion(should_notify=False, reasons=[], prompt_version="care/v1")

        snapshots = self._load_snapshots(device_id)
        active_scopes = ConsentService(self.db).active_scopes(device_id)

        evaluations: dict[str, dict] = {}
        for spec in METRIC_SPECS:
            evaluations[spec.key] = self._metric_evaluation(device_id, spec, snapshots, active_scopes)

        deviated: list[MetricSpec] = []
        sustained: list[MetricSpec] = []
        reasons: list[CareReason] = [
            CareReason(code="consent", detail="仅使用你已明确授权的指标，且随时可以关闭"),
        ]

        for key, ev in evaluations.items():
            if not ev.get("evaluated"):
                continue
            if ev.get("deviated"):
                deviated.append(next(s for s in METRIC_SPECS if s.key == key))
                if ev.get("sustained"):
                    sustained.append(next(s for s in METRIC_SPECS if s.key == key))

        if not deviated:
            return CareSuggestion(should_notify=False, reasons=reasons, prompt_version="care/v1")

        multi_metric = len(deviated) >= self.settings.care_multi_metric_count
        sustained_single = bool(sustained)

        if not (multi_metric or sustained_single):
            # 单一指标、非持续的变化不足以触发（例如单次 HRV 波动）
            return CareSuggestion(should_notify=False, reasons=reasons, prompt_version="care/v1")

        involved = list({*(s.label for s in deviated), *(s.label for s in sustained)})
        labels = "、".join(sorted(set(involved)))
        message = (
            f"我注意到你最近几天的{labels}和之前不太一样。"
            "也可能只是这段时间比较忙，或者身体在自然波动。你最近感觉怎么样？"
        )

        baseline_days = min(
            ev["baseline_days"] for ev in evaluations.values() if ev.get("evaluated") and ev.get("deviated")
        )
        reasons.append(CareReason(code="baseline", detail=f"基于你近 {baseline_days} 天的历史记录"))
        if multi_metric:
            reasons.append(
                CareReason(
                    code="multi_metric",
                    detail="、" .join(s.label for s in deviated) + " 等多项指标同时出现变化",
                )
            )
        if sustained_single:
            reasons.append(
                CareReason(
                    code="sustained",
                    detail=f"其中变化持续了 {self.settings.care_sustained_min_days} 天以上",
                )
            )
        reasons.append(
            CareReason(
                code="uncertainty",
                detail="这只是一次温和的观察，不是任何医学判断；也完全可能没有特别的原因",
            )
        )

        return CareSuggestion(
            should_notify=True,
            message=message,
            reasons=reasons,
            metrics=[s.key for s in deviated],
            prompt_version="care/v1",
        )
