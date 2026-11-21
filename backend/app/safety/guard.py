"""SafetyGuard：独立于 LLM 的确定性风险分级模块。

核心原则（与 docs/SAFETY_DESIGN.md 一致）：
1. 规则优先于提示词：分级与危机响应完全不经过 LLM，即使模型被说服也不会
   改变分级结果。
2. urgent 场景绕过 LLM，返回版本化的固定危机脚本（见 prompts/chat/v1/），
   保证响应永远不包含方法、剂量、地点或规避救援的信息。
3. 只输出风险等级与信号类别；聊天原文不写入日志，也不写入 SafetyEvent。

已知限制：正则分级存在误报/漏报，需要社区与专业审核持续迭代
（见 CONTRIBUTING.md 的安全评审要求）。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .patterns import (
    CATEGORY_EXPLANATIONS,
    GRIEF_PATTERNS,
    INJECTION_PATTERNS,
    SAFE_SUBSTRINGS,
    SUPPORT_PATTERNS,
    URGENT_PATTERNS,
)

logger = logging.getLogger("mindpulse.safety")

ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)


@dataclass
class SafetyVerdict:
    level: str  # safe | support | urgent
    signal_categories: list[str] = field(default_factory=list)
    prompt_injection: bool = False

    @property
    def is_urgent(self) -> bool:
        return self.level == "urgent"

    def human_reasons(self) -> list[str]:
        """给用户看的分级原因（不含任何原文片段）。"""
        reasons = [CATEGORY_EXPLANATIONS[c] for c in self.signal_categories if c in CATEGORY_EXPLANATIONS]
        if self.prompt_injection:
            reasons.append("该消息试图让系统关闭安全规则；此请求已被拒绝，安全规则不可关闭")
        return reasons


def normalize(text: str) -> str:
    """小写化并去除零宽字符；把口语安全短语替换为逗号避免拼接出误报。"""
    lowered = text.translate(ZERO_WIDTH).lower()
    for phrase in SAFE_SUBSTRINGS:
        lowered = lowered.replace(phrase.lower(), "，")
    return lowered


class SafetyGuard:
    """确定性风险分级。线程安全、无状态、不依赖网络与 LLM。"""

    def classify(self, text: str) -> SafetyVerdict:
        cleaned = normalize(text)

        prompt_injection = any(p.search(cleaned) for p in INJECTION_PATTERNS)

        # 1) 剔除哀伤/转述语境后再判断 urgent，避免“我朋友自杀了”误判
        urgent_probe = cleaned
        for grief in GRIEF_PATTERNS:
            urgent_probe = grief.sub("，", urgent_probe)

        categories: list[str] = []
        for name, patterns in URGENT_PATTERNS.items():
            if any(p.search(urgent_probe) for p in patterns):
                categories.append(name)

        if categories:
            return SafetyVerdict(level="urgent", signal_categories=categories, prompt_injection=prompt_injection)

        # 2) support：持续低落或强烈焦虑
        support_categories = [
            name for name, patterns in SUPPORT_PATTERNS.items() if any(p.search(cleaned) for p in patterns)
        ]
        if support_categories:
            return SafetyVerdict(
                level="support", signal_categories=support_categories, prompt_injection=prompt_injection
            )

        return SafetyVerdict(level="safe", signal_categories=[], prompt_injection=prompt_injection)

    # ------------------------------------------------------------------
    # 输出侧防护：检查 LLM 回复是否违反了安全策略（双保险）
    # ------------------------------------------------------------------

    _OUTPUT_METHOD_HINTS: tuple[re.Pattern[str], ...] = tuple(
        re.compile(p, re.IGNORECASE)
        for p in (
            r"(自杀|自尽|上吊|割腕|烧炭|吞药|服药)[^。！？]{0,12}(方法|步骤|方式|怎么|如何|剂量|多少)",
            r"(方法|步骤|方式)[^。！？]{0,8}(自杀|自尽|上吊|割腕|烧炭|吞药)",
            r"(服用|吃下|吃|摄入)[^。！？0-9]{0,10}\d+\s?(片|粒|颗|毫克|mg|克|g)",
            r"(致命|致死)(剂量|浓度)",
            r"how to (kill|hang|hurt) (yourself|myself|oneself)",
            r"lethal dose",
        )
    )

    def screen_output(self, text: str) -> bool:
        """True 表示回复违规，需要替换为安全兜底文案。"""
        cleaned = normalize(text)
        return any(p.search(cleaned) for p in self._OUTPUT_METHOD_HINTS)


# 依赖注入用单例
_default_guard = SafetyGuard()


def get_guard() -> SafetyGuard:
    return _default_guard
