"""Prompt 契约测试：版本化管理 + 章程必备条款 + 危机脚本安全边界。"""

from app.prompt_service import PromptService


def prompts() -> PromptService:
    return PromptService()


class TestPromptVersioning:
    def test_manifest_loads(self):
        service = prompts()
        assert service.version == "chat/v1"
        assert service.manifest["files"]["system_zh"].startswith("chat/v1/")

    def test_chat_response_carries_prompt_version(self, client, device_id):
        from conftest import chat

        data = chat(client, device_id, "你好")
        assert data["prompt_version"] == "chat/v1"


class TestCharterInvariants:
    """系统章程必须包含的条款——改动 Prompt 必须同步更新这里的断言。"""

    REQUIRED_CLAUSES = (
        "不是医生",
        "不做临床诊断",
        "没有身体",
        "不制造排他性依赖",
        "绝不鼓励用户远离家人、朋友或专业人士",
        "先回应用户此刻的情绪",
        "一次最多提出一个主要问题",
        "不根据健康数据推断用户患有任何疾病",
        "SafetyGuard",
        "不提供医学诊断或紧急服务",
    )

    def test_system_zh_contains_all_clauses(self):
        text = prompts().system_prompt(level="safe", injection=False)
        for clause in self.REQUIRED_CLAUSES:
            assert clause in text, clause

    def test_support_addendum_appended_for_support_level(self):
        text = prompts().system_prompt(level="support", injection=False)
        assert "支持模式附加说明" in text

    def test_injection_addendum_appended(self):
        text = prompts().system_prompt(level="safe", injection=True)
        assert "注入防护附加说明" in text
        assert "无效" in text


class TestCrisisScriptBoundaries:
    def test_urgent_script_required_content(self):
        script = prompts().crisis_script("urgent")
        for phrase in ("立即危险", "急救", "急诊室", "保密", "国家或地区", "陪着你的人", "物品"):
            assert phrase in script, phrase

    def test_action_script_prioritizes_emergency(self):
        script = prompts().crisis_script("action")
        assert "急诊室" in script
        assert "不要等待" in script
        assert "保管" in script

    def test_scripts_never_contain_methods_or_doses(self):
        for variant in ("urgent", "action"):
            script = prompts().crisis_script(variant)
            for word in ("毫克", "mg", "剂量", "步骤：", "方法有"):
                assert word not in script, (variant, word)

    def test_scripts_never_create_dependency(self):
        for variant in ("urgent", "action"):
            script = prompts().crisis_script(variant)
            for phrase in ("我会一直陪着你", "你只有我", "别告诉别人"):
                assert phrase not in script, (variant, phrase)

    def test_scripts_use_token_not_hardcoded_number(self):
        # 脚本不硬编码具体热线号码；号码由资源服务按用户地区注入
        script = prompts().crisis_script("urgent")
        assert "{{RESOURCES_BLOCK}}" in script
        assert "{{EMERGENCY_HINT}}" in script
