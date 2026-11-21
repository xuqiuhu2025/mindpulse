"""健康快照摄入：只收聚合值，逐分钟原始数据在接口层直接拒绝。"""

from conftest import grant_all_scopes, headers


class TestSnapshotIngestion:
    def test_accepts_daily_aggregates(self, client, device_id):
        grant_all_scopes(client, device_id)
        r = client.post(
            "/api/health/snapshots",
            json=[{"date": "2026-11-21", "sleep_hours": 7.2, "resting_hr": 62.0, "hrv_sdnn": 45.0, "steps": 8234}],
            headers=headers(device_id),
        )
        assert r.status_code == 200
        assert r.json()[0]["sleep_hours"] == 7.2

    def test_rejects_raw_minute_series(self, client, device_id):
        # extra="forbid"：任何试图上传原始逐分钟序列的字段都会 422
        grant_all_scopes(client, device_id)
        r = client.post(
            "/api/health/snapshots",
            json=[{"date": "2026-11-21", "sleep_hours": 7.2, "minute_heart_rates": [61, 62, 63]}],
            headers=headers(device_id),
        )
        assert r.status_code == 422

    def test_rejects_invalid_date(self, client, device_id):
        grant_all_scopes(client, device_id)
        r = client.post(
            "/api/health/snapshots",
            json=[{"date": "21/11/2026", "sleep_hours": 7.2}],
            headers=headers(device_id),
        )
        assert r.status_code == 422

    def test_upsert_same_date(self, client, device_id):
        grant_all_scopes(client, device_id)
        for steps in (5000, 9000):
            r = client.post(
                "/api/health/snapshots",
                json=[{"date": "2026-11-21", "steps": steps}],
                headers=headers(device_id),
            )
            assert r.status_code == 200
        snapshots = client.get("/api/health/snapshots", headers=headers(device_id)).json()
        assert len(snapshots) == 1
        assert snapshots[0]["steps"] == 9000

    def test_device_id_required(self, client):
        r = client.post("/api/mood", json={"score": 5})
        assert r.status_code == 422
