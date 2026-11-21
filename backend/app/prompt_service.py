"""版本化 Prompt 加载器。

Prompt 文件存放在 monorepo 根目录 prompts/ 下，通过 manifest.json 管理：
- manifest.json 声明当前版本与文件映射；
- 修改 Prompt 必须新开版本目录 + 更新 CHANGELOG.md（见 prompts/CHANGELOG.md）；
- 服务端在每次聊天响应里返回 prompt_version，方便审计与回放。
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger("mindpulse.prompts")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PROMPTS_DIR = _REPO_ROOT / "prompts"


class PromptService:
    def __init__(self, prompts_dir: Path | None = None) -> None:
        self.prompts_dir = prompts_dir or _DEFAULT_PROMPTS_DIR
        manifest_path = self.prompts_dir / "manifest.json"
        with open(manifest_path, encoding="utf-8") as f:
            self.manifest = json.load(f)
        self.version: str = self.manifest["version"]
        self._cache: dict[str, str] = {}

    def _load(self, key: str) -> str:
        if key in self._cache:
            return self._cache[key]
        rel = self.manifest["files"][key]
        path = self.prompts_dir / rel
        text = path.read_text(encoding="utf-8")
        self._cache[key] = text
        return text

    def system_prompt(self, level: str, injection: bool, locale: str = "zh") -> str:
        parts: list[str] = []
        parts.append(self._load(f"system_{locale}"))
        if level == "support":
            parts.append(self._load(f"addendum_support_{locale}"))
        if injection:
            parts.append(self._load(f"addendum_injection_{locale}"))
        return "\n\n".join(parts)

    def crisis_script(self, variant: str, locale: str = "zh") -> str:
        """variant: urgent | action。固定文案，由 SafetyGuard 流程直接使用，不经过 LLM。"""
        return self._load(f"crisis_{variant}_{locale}")


@lru_cache(maxsize=1)
def get_prompt_service() -> PromptService:
    return PromptService()
