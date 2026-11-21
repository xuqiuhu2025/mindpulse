"""场景 6：用户撤销 HealthKit 授权——撤回即时生效。"""

from conftest import grant_all_scopes, headers, seed_snapshots

BASELINE = {"sleep_hours": 8.0, "steps": 8000, "hrv_sdnn": 50.0, "resting_hr": 60.0}
RECENT_DROP = {"sleep_hours": 5.0, "steps": 3000, "hrv_sdnn": 30.0, "resting_hr": 75.0}


class TestRevokeConsent:
    def test_revoke_blocks_new_snapshots(self, client, device_id):
        grant_all_scopes(client, device_id)
        r = client.post(
            "/api/health/snapshots",
            json=[{"date": "2026-11-20", "sleep_hours": 7.0}],
            headers=headers(device_id),
        )
        assert r.status_code == 200

        revoke = client.post(
            "/api/consent", json={"scope": "healthkit.sleep", "granted": False}, headers=headers(device_id)
        )
        assert revoke.status_code == 200
        assert revoke.json()["granted"] is False

        denied = client.post(
            "/api/health/snapshots",
            json=[{"date": "2026-11-21", "sleep_hours": 6.5}],
            headers=headers(device_id),
        )
        assert denied.status_code == 403
        assert "healthkit.sleep" in denied.json()["detail"]["missing_scopes"]

    def test_revoke_stops_care_engine(self, client, device_id):
        # 有会触发建议的数据 → 先验证触发，再撤回 → 引擎静默
        grant_all_scopes(client, device_id)
        seed_snapshots(client, device_id, days=13, baseline=BASELINE, recent=RECENT_DROP)
        assert client.get("/api/care/suggestions", headers=headers(device_id)).json()["should_notify"] is True

        for scope in (
            "healthkit.sleep",
            "healthkit.resting_heart_rate",
            "healthkit.hrv",
            "healthkit.steps",
        ):
            client.post("/api/consent", json={"scope": scope, "granted": False}, headers=headers(device_id))

        data = client.get("/api/care/suggestions", headers=headers(device_id)).json()
        assert data["should_notify"] is False
        assert data["metrics"] == []

    def test_consent_audit_trail(self, client, device_id):
        grant = client.post(
            "/api/consent", json={"scope": "healthkit.hrv", "granted": True}, headers=headers(device_id)
        )
        revoke = client.post(
            "/api/consent", json={"scope": "healthkit.hrv", "granted": False}, headers=headers(device_id)
        )
        # 撤销接口返回的“当前生效状态”是未授权
        assert grant.json()["granted"] is True
        assert revoke.json()["granted"] is False
        assert revoke.json()["revoked_at"] is not None

        # 审计记录保留原始授权时间与撤回时间
        records = client.get("/api/consent", headers=headers(device_id)).json()
        assert len(records) == 1
        record = records[0]
        assert record["granted"] is True  # 记录的是“曾授权”
        assert record["revoked_at"] is not None  # 但已被撤回
