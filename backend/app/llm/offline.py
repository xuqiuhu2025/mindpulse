"""offline provider：零依赖的确定性兜底。

用途：
1. 开发环境没有 API key 时也能完整跑通产品流程；
2. 自动化测试的确定性基础（不 mock 网络）；
3. 真实供应商故障时的降级响应。

文案原则与系统 Prompt 一致：先共情、最多一个主要问题、不诊断、
不伪造现实动作、不制造依赖。
"""

from __future__ import annotations

from .base import LLMProvider

_REPLIES_SAFE = {
    "greeting": (
        "你好呀。很高兴你在这里。今天过得怎么样？"
    ),
    "work": (
        "听起来最近工作带给你的压力不小。愿意把它说出来，本身就是照顾自己的开始。"
        "最近是事情变多了，还是节奏变了？"
    ),
    "sorting_thoughts": (
        "整理思绪是个很好的开始。不用着急，想到什么就说什么，我们可以慢慢来。"
        "此刻脑子里最占地方的那件事是什么？"
    ),
    "want_to_talk": (
        "我在听。这里没有需要赶着完成的话题，你想从哪里说起都可以。"
    ),
    "general": (
        "谢谢你愿意分享这些。我想先好好听你说。"
        "最近有什么让你印象最深的事吗？"
    ),
}

_REPLY_SUPPORT = (
    "听起来这段时间真的很辛苦。你的这些感受是真实的，也是值得被认真对待的。"
    "你不需要一个人扛着这些——如果方便，可以想想身边有没有一个你现在信任、能说上几句话的人；"
    "如果情绪持续影响生活，专业心理支持也是很好的选择。\n"
    "也可以先做一件很小的事，比如去窗边站一会儿，或者给自己倒杯水。\n"
    "你愿意和我多说说最近的状态吗？"
)

_REPLY_OFFLINE_FALLBACK = (
    "抱歉，我这边暂时没能连接到服务，稍后再试试看。"
    "如果此刻你需要立刻的支持，请联系身边可信任的人。"
)


class OfflineProvider(LLMProvider):
    name = "offline"

    def __init__(self) -> None:
        # 记录最近一次收到的 prompt，供测试断言安全章程始终在场。
        self.last_system: str = ""
        self.last_turns: list[dict[str, str]] = []

    def _route_safe(self, last_user_text: str) -> str:
        t = last_user_text
        if any(k in t for k in ("你好", "在吗", "哈喽", "hello", "hi", "嗨", "上午好", "下午好", "晚上好")):
            return _REPLIES_SAFE["greeting"]
        if any(k in t for k in ("工作", "上班", "加班", "老板", "业绩", "deadline", "离职", "kpi", "kpi")):
            return _REPLIES_SAFE["work"]
        if any(k in t for k in ("整理", "思绪", "理清楚", "想不明白", "乱")):
            return _REPLIES_SAFE["sorting_thoughts"]
        if any(k in t for k in ("聊聊", "说说话", "找个人", "陪我")):
            return _REPLIES_SAFE["want_to_talk"]
        return _REPLIES_SAFE["general"]

    async def complete(
        self,
        *,
        system: str,
        turns: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 600,
    ) -> str:
        self.last_system = system
        self.last_turns = list(turns)
        last_user = ""
        for turn in reversed(turns):
            if turn.get("role") == "user":
                last_user = turn.get("content", "")
                break

        # offline provider 同样要遵守分层：support 层给固定支持文案。
        # safe 层按关键词路由；这里不判断 urgent（urgent 不应进入 LLM 流程）。
        if "支持模式附加说明" in system or "support-mode" in system:
            return _REPLY_SUPPORT
        return self._route_safe(last_user)

    @property
    def offline_fallback_text(self) -> str:
        return _REPLY_OFFLINE_FALLBACK
