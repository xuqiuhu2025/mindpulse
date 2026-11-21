"""MindPulse 后端配置。

所有配置来自环境变量（前缀 MINDPULSE_），严禁把真实 API key 写进代码或仓库。
开发环境请复制仓库根目录的 .env.example 为 .env 并按需填写。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MINDPULSE_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # 应用
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./mindpulse.db"

    # LLM Provider 抽象层
    # 默认 offline：无外部依赖、可离线运行与测试，不依赖任何供应商。
    # 切换为 openai_compatible 后，任何兼容 OpenAI Chat Completions 协议的
    # 供应商（OpenAI、DeepSeek、Moonshot、GLM、本地 vLLM 等）都可以通过
    # MINDPULSE_LLM_BASE_URL 接入，不需要改代码。
    llm_provider: str = "offline"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 30.0

    # 主动关心（care engine）阈值：宁可少提醒，不可吓唬用户
    care_min_baseline_days: int = 10      # 每个指标至少需要的天数才形成基线（不含最近窗口）
    care_recent_days: int = 3             # “最近”窗口长度
    care_sustained_window_days: int = 7   # 持续性检查窗口
    care_sustained_min_days: int = 5      # 单指标需在该窗口内偏离 >= 5 天才算“持续”
    care_multi_metric_count: int = 2      # 至少多少项指标同时偏离才触发
    care_sleep_drop_ratio: float = 0.20
    care_steps_drop_ratio: float = 0.30
    care_resting_hr_delta: float = 8.0
    care_hrv_drop_ratio: float = 0.25

    # 聊天
    max_message_chars: int = 4000
    chat_history_turns: int = 10

    # CORS（iOS 原生客户端不受 CORS 限制；这里主要给本地 Web 调试用）
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # prompts/ 目录（默认取 monorepo 根目录）
    prompts_dir: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
