"""聊天服务：SafetyGuard 先行，LLM 只处理 safe/support 场景。

urgent 场景完全绕过 LLM，返回 prompts/ 中版本化的固定危机脚本，
保证永远不会泄露方法、剂量、地点或规避救援的信息。
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..llm.base import LLMProvider, LLMProviderError
from ..models.db import Conversation, Message, SafetyEvent
from ..models.schemas import (
    ChatRequest,
    ChatResponse,
    CrisisInfo,
    SafetyInfo,
)
from ..prompt_service import PromptService
from ..safety.guard import SafetyGuard, SafetyVerdict
from .crisis_resources import CrisisResourceService

logger = logging.getLogger("mindpulse.chat")

# 真实供应商故障时的兜底文案（不含任何用户数据、不伪装现实动作）
PROVIDER_FALLBACK_REPLY = (
    "抱歉，我这边暂时没能连接到服务，请稍后再试。"
    "如果此刻你需要支持，可以联系身边可信任的人。"
)
OUTPUT_VIOLATION_REPLY = (
    "我想更谨慎地回应刚才的话题。你愿意换一种方式，说说你现在的感受吗？"
)


class ChatService:
    def __init__(
        self,
        db: Session,
        *,
        settings,
        provider: LLMProvider,
        guard: SafetyGuard,
        prompts: PromptService,
        crisis: CrisisResourceService,
    ) -> None:
        self.db = db
        self.settings = settings
        self.provider = provider
        self.guard = guard
        self.prompts = prompts
        self.crisis = crisis

    # ------------------------------------------------------------------

    def _get_or_create_conversation(self, device_id: str, conversation_id: str | None) -> Conversation:
        if conversation_id:
            conv = self.db.get(Conversation, conversation_id)
            if conv is None or conv.device_id != device_id:
                raise LookupError("conversation_not_found")
            return conv
        conv = Conversation(device_id=device_id)
        self.db.add(conv)
        self.db.flush()
        return conv

    def _history_turns(self, conversation_id: str, limit: int) -> list[dict[str, str]]:
        rows = (
            self.db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        rows = list(reversed(rows))
        return [{"role": m.role, "content": m.content} for m in rows]

    def _record_event(
        self, device_id: str, conversation_id: str | None, message_id: str | None, verdict: SafetyVerdict
    ) -> None:
        event = SafetyEvent(
            device_id=device_id,
            conversation_id=conversation_id,
            message_id=message_id,
            level=verdict.level,
            signal_categories=list(verdict.signal_categories),
            prompt_injection=verdict.prompt_injection,
        )
        self.db.add(event)

    # ------------------------------------------------------------------

    def _build_crisis_reply(self, verdict: SafetyVerdict, country: str | None) -> tuple[str, CrisisInfo]:
        crisis_info = self.crisis.get(country)
        variant = "action" if "immediate_action" in verdict.signal_categories else "urgent"
        script = self.prompts.crisis_script(variant)

        if crisis_info.need_country:
            emergency_hint = "（可在你所在地区的官方渠道查询当地急救号码，或直接前往最近的急诊室）"
            resources_lines = ["- 国际求助目录：" + " / ".join(crisis_info.directories)]
        else:
            emergency_hint = ""
            resources_lines = []
            if crisis_info.emergency_number:
                resources_lines.append(f"- 当地急救电话：{crisis_info.emergency_number}")
            for r in crisis_info.resources:
                pieces = [f"- {r.name}"]
                if r.phone:
                    pieces.append(f"电话 {r.phone}")
                if r.hours:
                    pieces.append(f"（{r.hours}）")
                resources_lines.append("".join(pieces))
            resources_lines.append("- 更多目录：" + " / ".join(crisis_info.directories))

        reply = script.replace("{{EMERGENCY_HINT}}", emergency_hint).replace(
            "{{RESOURCES_BLOCK}}", "\n".join(resources_lines)
        )
        return reply, crisis_info

    # ------------------------------------------------------------------

    async def handle(self, device_id: str, req: ChatRequest) -> ChatResponse:
        text = req.message.strip()
        verdict = self.guard.classify(text)

        conversation = self._get_or_create_conversation(device_id, req.conversation_id)
        user_message = Message(
            conversation_id=conversation.id, role="user", content=text, safety_level=verdict.level
        )
        self.db.add(user_message)
        self.db.flush()

        if verdict.level != "safe" or verdict.prompt_injection:
            # 只记录分级与类别；聊天原文不进日志也不进 SafetyEvent
            self._record_event(device_id, conversation.id, user_message.id, verdict)
            logger.info(
                "safety classified level=%s categories=%s injection=%s",
                verdict.level,
                ",".join(verdict.signal_categories),
                verdict.prompt_injection,
            )

        # ---------- urgent：固定脚本，不经过 LLM ----------
        if verdict.is_urgent:
            reply, crisis_info = self._build_crisis_reply(verdict, req.country)
            assistant = Message(
                conversation_id=conversation.id, role="assistant", content=reply, safety_level="urgent"
            )
            self.db.add(assistant)
            self.db.commit()
            return ChatResponse(
                conversation_id=conversation.id,
                message_id=assistant.id,
                reply=reply,
                safety=SafetyInfo(
                    level="urgent",
                    signal_categories=verdict.signal_categories,
                    prompt_injection=verdict.prompt_injection,
                    crisis=crisis_info,
                ),
                prompt_version=self.prompts.version,
            )

        # ---------- safe / support：LLM 参与，SafetyGuard 仍把关输出 ----------
        system = self.prompts.system_prompt(level=verdict.level, injection=verdict.prompt_injection, locale=req.locale)
        history = self._history_turns(conversation.id, self.settings.chat_history_turns)
        turns = [*history, {"role": "user", "content": text}]

        try:
            reply = await self.provider.complete(system=system, turns=turns)
        except LLMProviderError:
            logger.warning("llm provider unavailable, using fallback reply")
            reply = PROVIDER_FALLBACK_REPLY

        if self.guard.screen_output(reply):
            logger.warning("llm output violated policy, replaced with safe fallback")
            reply = OUTPUT_VIOLATION_REPLY

        assistant = Message(
            conversation_id=conversation.id, role="assistant", content=reply, safety_level=verdict.level
        )
        self.db.add(assistant)
        self.db.commit()

        return ChatResponse(
            conversation_id=conversation.id,
            message_id=assistant.id,
            reply=reply,
            safety=SafetyInfo(
                level=verdict.level,
                signal_categories=verdict.signal_categories,
                prompt_injection=verdict.prompt_injection,
                crisis=None,
            ),
            prompt_version=self.prompts.version,
        )

    # ------------------------------------------------------------------

    def clear_chat(self, device_id: str, conversation_id: str | None) -> int:
        """清空当前对话：删除该会话的全部消息。返回删除条数。"""
        if conversation_id:
            conv = self.db.get(Conversation, conversation_id)
            if conv is None or conv.device_id != device_id:
                raise LookupError("conversation_not_found")
        else:
            conv = (
                self.db.execute(
                    select(Conversation)
                    .where(Conversation.device_id == device_id)
                    .order_by(Conversation.updated_at.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if conv is None:
                return 0
        count = len(conv.messages)
        for m in list(conv.messages):
            self.db.delete(m)
        self.db.commit()
        return count
