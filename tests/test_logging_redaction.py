"""场景 11：API key、聊天原文与健康数值不得出现在日志中。"""

import logging

from conftest import FAKE_LLM_KEY, chat, grant_all_scopes, headers, seed_snapshots


class TestLogRedaction:
    def test_api_key_never_logged(self, client, caplog, device_id):
        with caplog.at_level(logging.INFO):
            chat(client, device_id, "你好")
            client.get("/api/data/export", headers=headers(device_id))
        assert FAKE_LLM_KEY not in caplog.text
        assert "test-key-not-a-real-secret" not in caplog.text

    def test_chat_text_never_logged(self, client, caplog, device_id):
        with caplog.at_level(logging.INFO):
            chat(client, device_id, "我最近焦虑到整晚睡不着")
            chat(client, device_id, "我想自杀")
        assert "我最近焦虑到整晚睡不着" not in caplog.text
        assert "我想自杀" not in caplog.text

    def test_health_values_never_logged(self, client, caplog, device_id):
        grant_all_scopes(client, device_id)
        with caplog.at_level(logging.INFO):
            client.post(
                "/api/health/snapshots",
                json=[{"date": "2026-11-21", "sleep_hours": 6.5, "resting_hr": 58.0, "hrv_sdnn": 43.0}],
                headers=headers(device_id),
            )
        assert "6.5" not in caplog.text
        assert "58.0" not in caplog.text
        assert "43.0" not in caplog.text

    def test_redaction_filter_masks_secret_shapes(self):
        # 直接验证 RedactionFilter：常见密钥形态都会被替换
        # 假密钥在运行时构造，避免仓库中出现任何形似密钥的字面量
        from app.logging_setup import RedactionFilter

        fake_openai_style = "sk-" + "a" * 32
        fake_bearer = "Bearer " + "t" * 24
        f = RedactionFilter([FAKE_LLM_KEY])
        for secret in (fake_openai_style, fake_bearer, FAKE_LLM_KEY):
            record = logging.LogRecord("test", logging.INFO, __file__, 1, f"leak {secret}", (), None)
            f.filter(record)
            assert secret not in record.getMessage()

    def test_access_log_has_no_query_or_body(self, client, caplog, device_id):
        with caplog.at_level(logging.INFO, logger="mindpulse.app"):
            chat(client, device_id, "这条话不会进日志")
        # 访问日志只包含 method/path/status
        http_lines = [r.getMessage() for r in caplog.records if "http POST" in r.getMessage()]
        assert http_lines, "应有访问日志"
        assert all("不会进日志" not in line for line in http_lines)
