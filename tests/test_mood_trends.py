"""心情记录：1-10 分校验、中性趋势命名、数据不足不出结论。"""

from conftest import headers


class TestMoodEntry:
    def test_score_range_enforced(self, client, device_id):
        assert client.post("/api/mood", json={"score": 0}, headers=headers(device_id)).status_code == 422
        assert client.post("/api/mood", json={"score": 11}, headers=headers(device_id)).status_code == 422
        r = client.post("/api/mood", json={"score": 7, "tags": ["工作", "压力"]}, headers=headers(device_id))
        assert r.status_code == 200
        assert r.json()["entry"]["score"] == 7

    def test_note_with_crisis_content_is_flagged(self, client, device_id):
        r = client.post(
            "/api/mood", json={"score": 2, "note": "最近不想活了"}, headers=headers(device_id)
        )
        assert r.status_code == 200
        assert r.json()["safety"]["level"] == "urgent"


class TestMoodTrends:
    def _seed(self, client, device_id, scores):
        for s in scores:
            r = client.post("/api/mood", json={"score": s}, headers=headers(device_id))
            assert r.status_code == 200

    def test_insufficient_data_no_conclusion(self, client, device_id):
        # 数据不足 → 不生成任何趋势解读
        self._seed(client, device_id, [5, 6])
        data = client.get("/api/mood/trends?window=7", headers=headers(device_id)).json()
        assert data["insufficient_data"] is True
        assert data["narrative"] is None
        assert data["title"] == "心情记录趋势"

    def test_neutral_narrative_with_enough_data(self, client, device_id):
        self._seed(client, device_id, [4, 5, 6, 5, 7, 6, 5, 6])
        data = client.get("/api/mood/trends?window=7", headers=headers(device_id)).json()
        assert data["insufficient_data"] is False
        assert data["narrative"] is not None
        assert "自我报告" in data["narrative"]

        # 中性表述：任何响应都不允许出现诊断性词汇
        text = str(data)
        for word in ("抑郁指数", "焦虑指数", "抑郁", "焦虑", "诊断"):
            assert word not in text

    def test_window_validation(self, client, device_id):
        assert client.get("/api/mood/trends?window=14", headers=headers(device_id)).status_code == 422
