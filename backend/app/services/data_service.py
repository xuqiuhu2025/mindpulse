"""数据导出与彻底删除（GDPR 式的“带走/抹掉”能力）。"""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..models.db import (
    ConsentRecord,
    Conversation,
    HealthTrendSnapshot,
    Message,
    MoodEntry,
    SafetyEvent,
    UserPrefs,
)
from ..models.db import utcnow
from ..models.schemas import ExportOut


class DataService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def export(self, device_id: str) -> ExportOut:
        conversations: list[dict] = []
        convs = (
            self.db.execute(select(Conversation).where(Conversation.device_id == device_id))
            .scalars()
            .all()
        )
        for conv in convs:
            conversations.append(
                {
                    "id": conv.id,
                    "created_at": conv.created_at.isoformat(),
                    "messages": [
                        {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
                        for m in conv.messages
                    ],
                }
            )

        moods = (
            self.db.execute(select(MoodEntry).where(MoodEntry.device_id == device_id)).scalars().all()
        )
        snapshots = (
            self.db.execute(select(HealthTrendSnapshot).where(HealthTrendSnapshot.device_id == device_id))
            .scalars()
            .all()
        )
        consents = (
            self.db.execute(select(ConsentRecord).where(ConsentRecord.device_id == device_id))
            .scalars()
            .all()
        )
        events = (
            self.db.execute(select(SafetyEvent).where(SafetyEvent.device_id == device_id)).scalars().all()
        )
        prefs = self.db.get(UserPrefs, device_id)

        return ExportOut(
            exported_at=utcnow(),
            conversations=conversations,
            mood_entries=[
                {
                    "score": m.score,
                    "tags": m.tags,
                    "note": m.note,
                    "recorded_at": m.recorded_at.isoformat(),
                }
                for m in moods
            ],
            health_snapshots=[
                {
                    "date": s.date,
                    "sleep_hours": s.sleep_hours,
                    "resting_hr": s.resting_hr,
                    "hrv_sdnn": s.hrv_sdnn,
                    "steps": s.steps,
                    "source": s.source,
                }
                for s in snapshots
            ],
            consent_records=[
                {
                    "scope": c.scope,
                    "granted": c.granted,
                    "policy_version": c.policy_version,
                    "granted_at": c.granted_at.isoformat(),
                    "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
                }
                for c in consents
            ],
            # SafetyEvent 只含分级与类别，本来就无原文
            safety_events=[
                {
                    "level": e.level,
                    "signal_categories": e.signal_categories,
                    "prompt_injection": e.prompt_injection,
                    "created_at": e.created_at.isoformat(),
                }
                for e in events
            ],
            preferences=(
                {
                    "care_enabled": prefs.care_enabled,
                    "care_frequency": prefs.care_frequency,
                    "country": prefs.country,
                }
                if prefs
                else {}
            ),
        )

    def delete_all(self, device_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}

        counts["messages"] = self._delete_messages(device_id)
        for name, model in (
            ("conversations", Conversation),
            ("mood_entries", MoodEntry),
            ("health_snapshots", HealthTrendSnapshot),
            ("safety_events", SafetyEvent),
            ("consent_records", ConsentRecord),
        ):
            res = self.db.execute(delete(model).where(model.device_id == device_id))
            counts[name] = res.rowcount or 0

        prefs = self.db.get(UserPrefs, device_id)
        if prefs is not None:
            self.db.delete(prefs)
            counts["preferences"] = 1
        else:
            counts["preferences"] = 0

        self.db.commit()
        return counts

    def _delete_messages(self, device_id: str) -> int:
        conv_ids = (
            self.db.execute(select(Conversation.id).where(Conversation.device_id == device_id))
            .scalars()
            .all()
        )
        if not conv_ids:
            return 0
        res = self.db.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
        return res.rowcount or 0
