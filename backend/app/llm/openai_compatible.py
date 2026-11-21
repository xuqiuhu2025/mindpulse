"""OpenAI 兼容 Provider：通过 MINDPULSE_LLM_BASE_URL 接入任意兼容供应商
（OpenAI / DeepSeek / Moonshot / GLM / vLLM / Ollama 等）。

安全约定：
- API key 只从环境变量读取，不落盘、不打日志、不出服务端。
- 错误信息只包含状态码与错误类型，绝不回显请求头或密钥。
"""

from __future__ import annotations

import logging

import httpx

from .base import LLMProvider, LLMProviderError

logger = logging.getLogger("mindpulse.llm")


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds

    async def complete(
        self,
        *,
        system: str,
        turns: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 600,
    ) -> str:
        messages = [{"role": "system", "content": system}, *turns]
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            # 只记录异常类型，不记录 URL 查询参数/头内容
            logger.warning("llm provider network error: %s", type(exc).__name__)
            raise LLMProviderError("LLM 服务暂不可用") from exc

        if resp.status_code != 200:
            logger.warning("llm provider http error: status=%s", resp.status_code)
            raise LLMProviderError(f"LLM 服务返回错误（HTTP {resp.status_code}）")

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            logger.warning("llm provider malformed response")
            raise LLMProviderError("LLM 服务返回了无法解析的内容") from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMProviderError("LLM 服务返回了空内容")
        return content
