"""心情记录服务：用户主动记录 1-10 分心情 + 可选标签。

趋势只用中性表述（“心情记录趋势”“用户自我报告变化”），
数据不足时明确返回 insufficient_data，绝不生成结论。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.db import MoodEntry
from ..models.schemas import MoodEntryIn, MoodEntryOut, MoodTrendOut, MoodDayPoint, SafetyInfo
from ..safety.guard import SafetyGuard
from ..services.crisis_resources import CrisisResourceService

MIN_ENTRIES_FOR_NARRATIVE = 5


class MoodService:
    def __init__(self, db: Session, *, guard: SafetyGuard, crisis: CrisisResourceService) -> None:
        self.db = db
        self.guard = guard
        self.crisis = crisis

    def add_mood(self, device_id: str, req: MoodEntryIn) -> tuple[MoodEntryOut, SafetyInfo]:
        note = (req.note or "").strip()
        verdict = self.guard.classify(note) if note else None
        level = verdict.level if verdict else "safe"

        recorded_at = req.recorded_at or datetime.now(timezone.utc)
        entry = MoodEntry(
            device_id=device_id,
            score=req.score,
            tags=list(req.tags),
            note=note,
            safety_level=level,
            recorded_at=recorded_at,
        )
        self.db.add(entry)
        self.db.commit()

        safety = SafetyInfo(level=level, signal_categories=list(verdict.signal_categories) if verdict else [])
        return MoodEntryOut(
            id=entry.id, score=entry.score, tags=entry.tags, note=entry.note, recorded_at=entry.recorded_at
        ), safety

    def list_moods(self, device_id: str, limit: int = 100) -> list[MoodEntryOut]:
        rows = (
            self.db.execute(
                select(MoodEntry)
                .where(MoodEntry.device_id == device_id)
                .order_by(MoodEntry.recorded_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [
            MoodEntryOut(id=r.id, score=r.score, tags=r.tags, note=r.note, recorded_at=r.recorded_at)
            for r in rows
        ]

    @staticmethod
    def _as_utc(dt: datetime) -> datetime:
        """SQLite 读回的是 naive UTC，统一补上 tzinfo 再比较。"""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def _window_stats(self, entries: list[MoodEntry], now: datetime, days: int, offset_windows: int = 0) -> list[MoodEntry]:
        end = now - timedelta(days=days * offset_windows)
        start = end - timedelta(days=days)
        return [e for e in entries if start <= self._as_utc(e.recorded_at) < end]

    def trends(self, device_id: str, window_days: int) -> MoodTrendOut:
        now = datetime.now(timezone.utc)
        rows = (
            self.db.execute(
                select(MoodEntry)
                .where(MoodEntry.device_id == device_id)
                .order_by(MoodEntry.recorded_at.desc())
                .limit(500)
            )
            .scalars()
            .all()
        )
        rows = list(rows)

        current = self._window_stats(rows, now, window_days, offset_windows=0)
        previous = self._window_stats(rows, now, window_days, offset_windows=1)

        per_day: list[MoodDayPoint] = []
        buckets: dict[str, list[int]] = {}
        for e in current:
            key = e.recorded_at.date().isoformat()
            buckets.setdefault(key, []).append(e.score)
        for day in sorted(buckets):
            scores = buckets[day]
            per_day.append(MoodDayPoint(date=day, average=round(mean(scores), 2), count=len(scores)))

        insufficient = len(current) < MIN_ENTRIES_FOR_NARRATIVE
        narrative: str | None = None
        average = round(mean([e.score for e in current]), 2) if current else None
        prev_average = round(mean([e.score for e in previous]), 2) if previous else None

        if not insufficient and average is not None:
            narrative = (
                f"过去 {window_days} 天你主动记录了 {len(current)} 次心情，平均 {average} 分（满分 10）。"
            )
            if prev_average is not None:
                diff = round(average - prev_average, 2)
                direction = "上升" if diff > 0 else ("下降" if diff < 0 else "持平")
                narrative += f" 与上一个 {window_days} 天相比{direction}约 {abs(diff)} 分。"
            narrative += "这是你的自我报告变化，仅供参考。"

        return MoodTrendOut(
            window_days=window_days,
            count=len(current),
            average=average,
            previous_average=prev_average,
            per_day=per_day,
            narrative=narrative,
            insufficient_data=insufficient,
        )
