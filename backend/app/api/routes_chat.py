"""聊天路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models.schemas import ChatRequest, ChatResponse, ClearChatRequest
from ..services.chat_service import ChatService
from .deps import get_ctx, get_db, get_device_id

router = APIRouter(tags=["chat"])


def _service(db: Session, ctx) -> ChatService:
    return ChatService(
        db,
        settings=ctx.settings,
        provider=ctx.provider,
        guard=ctx.guard,
        prompts=ctx.prompts,
        crisis=ctx.crisis,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
    ctx=Depends(get_ctx),
):
    try:
        return await _service(db, ctx).handle(device_id, req)
    except LookupError:
        raise HTTPException(status_code=404, detail="会话不存在")


@router.post("/chat/clear")
def clear_chat(
    req: ClearChatRequest,
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
    ctx=Depends(get_ctx),
):
    try:
        removed = _service(db, ctx).clear_chat(device_id, req.conversation_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"cleared_messages": removed}


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    device_id: str = Depends(get_device_id),
):
    from sqlalchemy import select

    from ..models.db import Conversation

    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.device_id != device_id:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "id": conv.id,
        "created_at": conv.created_at.isoformat(),
        "messages": [
            {"role": m.role, "content": m.content, "safety_level": m.safety_level, "created_at": m.created_at.isoformat()}
            for m in conv.messages
        ],
    }
