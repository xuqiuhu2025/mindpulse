"""日志配置：多层脱敏，保证聊天原文、健康数值、API key 与用户标识不落日志。

实现两层防护：
1. RedactionFilter：对所有 log record 做实时替换——已知密钥字面量、
   sk-/AKIA/ghp_ 等常见密钥形态都会替换为 [REDACTED]。
2. 约定式防护：HTTP 中间件只记录 method/path/status/耗时，不记录
   请求体、查询串与响应体（见 main.py）。
"""

from __future__ import annotations

import logging
import re

from .config import Settings

_REDACTED = "[REDACTED]"

_SECRET_SHAPES = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}", re.IGNORECASE),
)


class RedactionFilter(logging.Filter):
    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        self._secrets = [s for s in secrets if s]

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True

        redacted = message
        for secret in self._secrets:
            if secret in redacted:
                redacted = redacted.replace(secret, _REDACTED)
        for shape in _SECRET_SHAPES:
            redacted = shape.sub(_REDACTED, redacted)

        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def configure_logging(settings: Settings) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(handler)

    for handler in root.handlers:
        handler.addFilter(RedactionFilter([settings.llm_api_key]))

    # uvicorn 的默认 handler 也要套上脱敏
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        for handler in logging.getLogger(name).handlers:
            handler.addFilter(RedactionFilter([settings.llm_api_key]))
