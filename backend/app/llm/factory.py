"""根据环境变量构建 LLM Provider。默认 offline，保证干净环境可启动。"""

from __future__ import annotations

import logging

from ..config import Settings
from .base import LLMProvider
from .offline import OfflineProvider
from .openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger("mindpulse.llm")


def build_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "offline":
        return OfflineProvider()

    if settings.llm_provider == "openai_compatible":
        if not settings.llm_api_key:
            # 不打印 key 本身，也不打印任何用户数据
            logger.warning("MINDPULSE_LLM_PROVIDER=openai_compatible 但未设置 MINDPULSE_LLM_API_KEY，回退到 offline 模式")
            return OfflineProvider()
        return OpenAICompatibleProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    logger.warning("未知 provider=%s，回退到 offline 模式", settings.llm_provider)
    return OfflineProvider()
