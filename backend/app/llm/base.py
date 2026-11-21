"""LLM Provider 抽象层。

不把任何供应商写死：只要实现 complete() 就可以接入新的模型服务。
供应商凭据只存在于服务端环境变量，绝不进入 iOS 客户端或仓库。
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProviderError(RuntimeError):
    """供应商调用失败（网络、鉴权、超时等）。错误信息不得包含 API key。"""


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def complete(
        self,
        *,
        system: str,
        turns: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 600,
    ) -> str:
        """turns: [{"role": "user"|"assistant", "content": ...}, ...]"""
        raise NotImplementedError
