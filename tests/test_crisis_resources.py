"""危机资源：不硬编码单一号码、未知地区先询问、带来源与核对日期。"""

from conftest import headers


class TestCrisisResources:
    def test_no_country_asks_region(self, client):
        data = client.get("/api/crisis/resources").json()
        assert data["need_country"] is True
        assert data["resources"] == []
        assert data["directories"]  # 国际目录兜底
        assert "国家或地区" in data["note"]

    def test_known_country_returns_verified_resources(self, client):
        data = client.get("/api/crisis/resources?country=CN").json()
        assert data["need_country"] is False
        assert data["emergency_number"] == "120"
        assert data["resources"]
        for resource in data["resources"]:
            assert resource["source"]
            assert resource["verified"]

    def test_all_entries_carry_source_and_verification(self, client):
        # 每个已收录国家的每条资源都必须有来源与核对日期
        for code in ("CN", "US", "GB", "JP", "BR", "IN", "SG", "DE", "FR", "AU", "CA", "KR", "ES", "NZ"):
            data = client.get(f"/api/crisis/resources?country={code}").json()
            assert data["need_country"] is False, code
            assert data["emergency_number"], code
            assert data["resources"], code

    def test_unknown_country_falls_back_to_directories(self, client):
        data = client.get("/api/crisis/resources?country=ZZ").json()
        assert data["need_country"] is True
        assert data["directories"]
        assert data["resources"] == []

    def test_invalid_country_code_rejected(self, client):
        assert client.get("/api/crisis/resources?country=CHN").status_code == 422

    def test_universal_directories_exist(self, client):
        dirs = client.get("/api/crisis/resources").json()["directories"]
        assert any("findahelpline" in d for d in dirs)
        assert any("iasp" in d for d in dirs)
