"""Pydantic 请求/响应模型。

注意：HealthSnapshotIn 使用 extra="forbid"——客户端若意外上传逐分钟原始
序列等字段，将直接 422 拒绝，从接口层面保证“只收聚合数据”。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SafetyLevel = Literal["safe", "support", "urgent"]


# ---------- 聊天 ----------


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    country: str | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        pattern=r"^[A-Za-z]{2}$",
        description="ISO 3166-1 alpha-2 国家/地区代码，仅在危机场景用于返回当地资源",
    )
    locale: Literal["zh", "en"] = "zh"


class CrisisResource(BaseModel):
    name: str
    phone: str | None = None
    url: str | None = None
    hours: str | None = None
    source: str | None = None
    verified: str | None = None  # YYYY-MM，静态数据需定期人工核对


class CrisisInfo(BaseModel):
    show_resources: bool
    need_country: bool
    country: str | None = None
    emergency_number: str | None = None
    resources: list[CrisisResource] = []
    directories: list[str] = []
    note: str | None = None


class SafetyInfo(BaseModel):
    level: SafetyLevel
    signal_categories: list[str] = []
    prompt_injection: bool = False
    crisis: CrisisInfo | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    reply: str
    safety: SafetyInfo
    prompt_version: str


class ClearChatRequest(BaseModel):
    conversation_id: str | None = None


# ---------- 心情记录 ----------


class MoodEntryIn(BaseModel):
    score: int = Field(ge=1, le=10)
    tags: list[str] = Field(default_factory=list, max_length=6)
    note: str | None = Field(default=None, max_length=500)
    recorded_at: datetime | None = None


class MoodEntryOut(BaseModel):
    id: str
    score: int
    tags: list[str]
    note: str
    recorded_at: datetime


class MoodDayPoint(BaseModel):
    date: str
    average: float
    count: int


class MoodTrendOut(BaseModel):
    window_days: int
    count: int
    average: float | None = None
    previous_average: float | None = None
    per_day: list[MoodDayPoint] = []
    narrative: str | None = None
    insufficient_data: bool = False
    title: str = "心情记录趋势"  # 中性命名，禁止任何诊断性分数名称


# ---------- HealthKit 聚合快照 ----------


class HealthSnapshotIn(BaseModel):
    model_config = ConfigDict(extra="forbid")  # 拒绝逐分钟序列等原始数据

    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    resting_hr: float | None = Field(default=None, ge=20, le=220)
    hrv_sdnn: float | None = Field(default=None, ge=0, le=500)
    steps: int | None = Field(default=None, ge=0, le=200000)
    source: str = "apple_healthkit"


class HealthSnapshotOut(BaseModel):
    date: str
    sleep_hours: float | None
    resting_hr: float | None
    hrv_sdnn: float | None
    steps: int | None
    source: str


class MetricTrendOut(BaseModel):
    metric: str
    label: str
    unit: str
    consent_granted: bool
    data_points: int
    baseline_days: int
    recent_average: float | None = None
    baseline_average: float | None = None
    deviation_detected: bool = False
    description: str | None = None  # 中性描述，无疾病词汇
    insufficient_data: bool = False


class HealthTrendOut(BaseModel):
    metrics: list[MetricTrendOut]
    disclaimer: str = "以上仅为自我参考的聚合趋势，不是医学结论。MindPulse 不会、也不能根据这些数据判断任何疾病。"


# ---------- 主动关心 ----------


class CareReason(BaseModel):
    code: str  # consent / baseline / multi_metric / sustained / consent_gate
    detail: str


class CareSuggestion(BaseModel):
    should_notify: bool
    message: str | None = None
    reasons: list[CareReason] = []
    metrics: list[str] = []
    prompt_version: str


class CareSettingsOut(BaseModel):
    enabled: bool
    frequency: Literal["standard", "reduced", "off"]
    updated_at: datetime | None = None


class CareSettingsIn(BaseModel):
    enabled: bool | None = None
    frequency: Literal["standard", "reduced", "off"] | None = None


class DismissCareRequest(BaseModel):
    scope: Literal["this", "all"] = "this"


# ---------- 同意与数据管理 ----------


class ConsentIn(BaseModel):
    scope: str = Field(pattern=r"^healthkit\.(sleep|resting_heart_rate|hrv|steps)$")
    granted: bool
    policy_version: str = "v1"


class ConsentOut(BaseModel):
    scope: str
    granted: bool
    policy_version: str
    granted_at: datetime
    revoked_at: datetime | None = None


class DeleteResultOut(BaseModel):
    deleted: dict[str, int]
    message: str = "所有数据已删除。"


class ExportOut(BaseModel):
    exported_at: datetime
    format_version: str = "1"
    conversations: list[dict] = []
    mood_entries: list[dict] = []
    health_snapshots: list[dict] = []
    consent_records: list[dict] = []
    safety_events: list[dict] = []
    preferences: dict = {}
