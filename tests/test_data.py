"""场景 9：删除数据后不可继续读取已删除内容。"""

from conftest import chat, grant_all_scopes, headers, seed_snapshots


class TestDeleteAll:
    def test_delete_then_read_fails(self, client, device_id):
        # 准备全量数据
        conv = chat(client, device_id, "这条消息应该在删除后消失")
        client.post(
            "/api/mood", json={"score": 5, "tags": ["工作"], "note": "有点累"}, headers=headers(device_id)
        )
        grant_all_scopes(client, device_id)
        seed_snapshots(client, device_id, days=13, baseline={"sleep_hours": 8.0}, recent={"sleep_hours": 8.0})

        export = client.get("/api/data/export", headers=headers(device_id)).json()
        assert len(export["conversations"]) >= 1
        assert len(export["mood_entries"]) >= 1

        # 彻底删除
        deleted = client.delete("/api/data/all", headers=headers(device_id))
        assert deleted.status_code == 200
        counts = deleted.json()["deleted"]
        assert counts["messages"] >= 2
        assert counts["mood_entries"] == 1

        # 已删除的会话不可读取
        r = client.get(f"/api/conversations/{conv['conversation_id']}", headers=headers(device_id))
        assert r.status_code == 404

        # 心情与快照列表为空
        assert client.get("/api/mood", headers=headers(device_id)).json() == []
        assert client.get("/api/health/snapshots", headers=headers(device_id)).json() == []

        # 导出为空
        export_after = client.get("/api/data/export", headers=headers(device_id)).json()
        assert export_after["conversations"] == []
        assert export_after["mood_entries"] == []
        assert export_after["health_snapshots"] == []

    def test_delete_is_idempotent(self, client, device_id):
        first = client.delete("/api/data/all", headers=headers(device_id))
        assert first.status_code == 200
        second = client.delete("/api/data/all", headers=headers(device_id))
        assert second.status_code == 200
        assert all(v == 0 for v in second.json()["deleted"].values())

    def test_device_isolation_on_delete(self, client, device_id):
        conv = chat(client, device_id, "设备 A 的消息")
        other = "dev-other00002"
        chat(client, other, "设备 B 的消息")
        client.delete("/api/data/all", headers=headers(other))
        # A 的数据不受影响
        r = client.get(f"/api/conversations/{conv['conversation_id']}", headers=headers(device_id))
        assert r.status_code == 200
