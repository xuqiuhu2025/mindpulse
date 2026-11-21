"""场景 7/8：主动关心引擎——基线不足不出结论；单一 HRV 短时变化不触发。"""

import pytest

from conftest import FORBIDDEN_DISEASE_WORDS, grant_all_scopes, headers, seed_snapshots

BASELINE = {"sleep_hours": 8.0, "steps": 8000, "hrv_sdnn": 50.0, "resting_hr": 60.0}
RECENT = {"sleep_hours": 7.8, "steps": 7800, "hrv_sdnn": 48.0, "resting_hr": 61.0}


def _no_disease_words(payload_text: str):
    for word in FORBIDDEN_DISEASE_WORDS:
        assert word not in payload_text, word


class TestInsufficientBaseline:
    def test_few_days_never_generates_conclusion(self, client, device_id):
        # 场景 7：没有足够历史数据 → 不生成健康趋势结论
        grant_all_scopes(client, device_id)
        seed_snapshots(client, device_id, days=3, baseline=BASELINE, recent=RECENT)

        care = client.get("/api/care/suggestions", headers=headers(device_id)).json()
        assert care["should_notify"] is False

        trends = client.get("/api/health/trends", headers=headers(device_id)).json()
        for metric in trends["metrics"]:
            assert metric["insufficient_data"] is True
            assert metric["description"] is None

    def test_no_data_at_all(self, client, device_id):
        care = client.get("/api/care/suggestions", headers=headers(device_id)).json()
        assert care["should_notify"] is False


class TestSingleMetricShortDeviation:
    def test_single_hrv_change_does_not_infer_illness(self, client, device_id):
        # 场景 8：单一 HRV 短时变化不能触发任何疾病判断
        grant_all_scopes(client, device_id)
        seed_snapshots(
            client,
            device_id,
            days=13,
            baseline=BASELINE,
            recent={**BASELINE, "hrv_sdnn": 30.0},  # 仅 HRV 下降，最近 3 天
        )

        care = client.get("/api/care/suggestions", headers=headers(device_id)).json()
        assert care["should_notify"] is False
        _no_disease_words(str(care))

        trends = client.get("/api/health/trends", headers=headers(device_id)).json()
        _no_disease_words(str(trends))
        hrv = next(m for m in trends["metrics"] if m["metric"] == "hrv")
        assert hrv["deviation_detected"] is True
        # 即使检测到偏离，描述也必须是中性趋势语言
        assert "非医学结论" in hrv["description"]
        _no_disease_words(hrv["description"])


class TestLegitimateTriggers:
    def test_multi_metric_simultaneous_change(self, client, device_id):
        grant_all_scopes(client, device_id)
        seed_snapshots(
            client,
            device_id,
            days=13,
            baseline=BASELINE,
            recent={**BASELINE, "sleep_hours": 5.5, "steps": 4000},
        )
        care = client.get("/api/care/suggestions", headers=headers(device_id)).json()
        assert care["should_notify"] is True
        assert care["message"] is not None

        message = care["message"]
        assert "和之前不太一样" in message
        assert "也可能只是" in message
        assert "你最近感觉怎么样" in message
        _no_disease_words(message)
        # 不出现数值化的诊断性表述
        assert "HRV" not in message

        codes = [r["code"] for r in care["reasons"]]
        assert "multi_metric" in codes
        assert "baseline" in codes

    def test_single_metric_short_deviation_does_not_trigger(self, client, device_id):
        grant_all_scopes(client, device_id)
        seed_snapshots(
            client,
            device_id,
            days=13,
            baseline=BASELINE,
            recent={**BASELINE, "sleep_hours": 5.0},  # 仅最近 3 天下降
        )
        care = client.get("/api/care/suggestions", headers=headers(device_id)).json()
        # 单指标近 3 天偏离：既不满足“多项同时”，也不满足“持续 5/7 天” → 不触发
        assert care["should_notify"] is False

    def test_single_metric_sustained_change_triggers_gently(self, client, device_id):
        grant_all_scopes(client, device_id)
        seed_snapshots(
            client,
            device_id,
            days=13,
            baseline=BASELINE,
            recent={**BASELINE, "sleep_hours": 5.0},
            recent_days=7,  # 连续 7 天偏离 → 满足“持续一段时间”
        )
        care = client.get("/api/care/suggestions", headers=headers(device_id)).json()
        assert care["should_notify"] is True
        codes = [r["code"] for r in care["reasons"]]
        assert "sustained" in codes
        assert "和之前不太一样" in care["message"]

    def test_opt_out_stops_all_care(self, client, device_id):
        grant_all_scopes(client, device_id)
        seed_snapshots(
            client,
            device_id,
            days=13,
            baseline=BASELINE,
            recent={**BASELINE, "sleep_hours": 5.5, "steps": 4000},
        )
        r = client.put("/api/care/settings", json={"enabled": False}, headers=headers(device_id))
        assert r.status_code == 200
        assert r.json()["enabled"] is False

        care = client.get("/api/care/suggestions", headers=headers(device_id)).json()
        assert care["should_notify"] is False

    def test_dismiss_all_endpoint(self, client, device_id):
        r = client.post("/api/care/dismiss", json={"scope": "all"}, headers=headers(device_id))
        assert r.status_code == 200
        assert r.json() == {"enabled": False, "frequency": "off", "updated_at": None} or \
            r.json()["enabled"] is False


@pytest.mark.parametrize("field,value", [("sleep_hours", 25), ("resting_hr", 500), ("steps", -5)])
def test_snapshot_value_bounds(client, device_id, field, value):
    grant_all_scopes(client, device_id)
    r = client.post(
        "/api/health/snapshots", json=[{"date": "2026-11-21", field: value}], headers=headers(device_id)
    )
    assert r.status_code == 422
