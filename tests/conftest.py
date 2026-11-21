"""pytest 公共夹具与工具。

自动化测试覆盖产品要求的核心安全场景：
1 普通闲聊 / 2 工作压力 / 3 持续低落 / 4 明确自伤 / 5 立即危险
6 撤销 HealthKit 授权 / 7 数据不足不出结论 / 8 单一 HRV 不推断疾病
9 删除后不可读 / 10 Prompt injection / 11 API key 不泄露
"""

import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

# 故意不带 sk- 前缀的假密钥：用于日志脱敏测试，且不会触发仓库密钥扫描
FAKE_LLM_KEY = "test-key-not-a-real-secret-123456"


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path}/test.db",
        llm_api_key=FAKE_LLM_KEY,
        log_level="INFO",
    )


@pytest.fixture()
def client(settings: Settings) -> TestClient:
    app = create_app(settings)
    return TestClient(app)


@pytest.fixture()
def device_id() -> str:
    return "dev-" + uuid.uuid4().hex[:12]


def headers(device_id: str) -> dict[str, str]:
    return {"X-Device-ID": device_id}


ALL_HEALTH_SCOPES = [
    "healthkit.sleep",
    "healthkit.resting_heart_rate",
    "healthkit.hrv",
    "healthkit.steps",
]


def grant_all_scopes(client: TestClient, device: str) -> None:
    for scope in ALL_HEALTH_SCOPES:
        r = client.post("/api/consent", json={"scope": scope, "granted": True}, headers=headers(device))
        assert r.status_code == 200, r.text


def seed_snapshots(
    client: TestClient,
    device: str,
    days: int,
    baseline: dict,
    recent: dict,
    recent_days: int = 3,
) -> list[dict]:
    """生成 days 天快照：前 (days-recent_days) 天用 baseline，最后 recent_days 天用 recent。"""
    from datetime import date, timedelta

    today = date.today()
    payload = []
    for i in range(days):
        offset = days - 1 - i  # 0 = 最早一天
        day = today - timedelta(days=offset)
        values = recent if offset < recent_days else baseline
        payload.append({"date": day.isoformat(), **values})
    r = client.post("/api/health/snapshots", json=payload, headers=headers(device))
    assert r.status_code == 200, r.text
    return payload


def chat(client: TestClient, device: str, message: str, **kwargs) -> dict:
    r = client.post("/api/chat", json={"message": message, **kwargs}, headers=headers(device))
    assert r.status_code == 200, r.text
    return r.json()


FORBIDDEN_DISEASE_WORDS = ("抑郁症", "焦虑症", "可能患有", "患有抑郁", "诊断你", "depression", "diagnos")
