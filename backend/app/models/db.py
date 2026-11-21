"""SQLAlchemy 数据模型。

隐私约定（与 PRIVACY.md 一致）：
- HealthKit 只存用户主动上传的“按天聚合值”，绝不存逐分钟原始数据。
- SafetyEvent 只存风险等级与信号类别，绝不存聊天原文。
- Message 存聊天内容本身（用于本地/服务端会话与用户导出、删除），
  但日志层禁止输出聊天原文（见 app/logging_setup.py）。
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    safety_level: Mapped[str] = mapped_column(String(16), default="safe")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class MoodEntry(Base):
    __tablename__ = "mood_entries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    score: Mapped[int] = mapped_column(Integer)  # 1-10，用户主动填写
    tags: Mapped[list] = mapped_column(JSON, default=list)  # 可选标签：压力/睡眠/工作/人际关系...
    note: Mapped[str] = mapped_column(Text, default="")
    safety_level: Mapped[str] = mapped_column(String(16), default="safe")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConsentRecord(Base):
    """用户对某类数据处理的同意/撤回记录。撤回后服务端不得再读取对应数据。"""

    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    scope: Mapped[str] = mapped_column(String(64))  # healthkit.sleep / healthkit.resting_heart_rate / ...
    granted: Mapped[bool] = mapped_column(Boolean)
    policy_version: Mapped[str] = mapped_column(String(16), default="v1")
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HealthTrendSnapshot(Base):
    """按天聚合的健康趋势快照（只存聚合值，无逐分钟数据）。"""

    __tablename__ = "health_trend_snapshots"
    __table_args__ = (UniqueConstraint("device_id", "date", name="uq_device_date"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD（用户本地日期）
    sleep_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    resting_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    hrv_sdnn: Mapped[float | None] = mapped_column(Float, nullable=True)
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="apple_healthkit")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SafetyEvent(Base):
    """安全事件审计。只记录分级结果与信号类别，不记录聊天原文。"""

    __tablename__ = "safety_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    level: Mapped[str] = mapped_column(String(16))  # safe | support | urgent
    signal_categories: Mapped[list] = mapped_column(JSON, default=list)
    prompt_injection: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserPrefs(Base):
    """按设备的轻量偏好。无账户体系，device_id 是唯一的伪匿名标识。"""

    __tablename__ = "user_prefs"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    care_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    care_frequency: Mapped[str] = mapped_column(String(16), default="standard")  # standard | reduced | off
    country: Mapped[str] = mapped_column(String(2), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
