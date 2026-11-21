"""欢迎页（根路径）：HTML 交付 + 免责声明 + API 健康。"""

from conftest import headers


class TestLandingPage:
    def test_root_returns_html_with_disclaimer(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        body = r.text
        # 免责声明必须原样出现在欢迎页上
        assert "MindPulse 提供情绪支持，不提供医学诊断或紧急服务" in body
        # 危机指引与入口链接必须存在
        assert "findahelpline.com" in body
        assert "/docs" in body

    def test_health_stays_json(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["app"] == "mindpulse"
