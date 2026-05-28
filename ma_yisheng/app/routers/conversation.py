"""Conversation routes: /api/conversations/*"""
from typing import Dict
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.deps import get_current_user
from app.services import memory

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class NewConversationBody(BaseModel):
    title: str = "新对话"


class MessageBody(BaseModel):
    role: str  # "user" or "assistant"
    content: str


@router.get("", summary="列出所有对话")
def list_conversations(user: Dict = Depends(get_current_user)):
    convs = memory.list_conversations(user["user_id"])
    return {"conversations": convs, "count": len(convs)}


@router.post("", summary="创建新对话")
def create_conversation(body: NewConversationBody, user: Dict = Depends(get_current_user)):
    conv = memory.create_conversation(user["user_id"], body.title)
    return conv


@router.get("/{conv_id}", summary="获取对话详情")
def get_conversation(conv_id: int, user: Dict = Depends(get_current_user)):
    conv = memory.get_conversation(conv_id, user["user_id"])
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conv


@router.get("/{conv_id}/messages", summary="获取对话消息列表")
def get_messages(conv_id: int, user: Dict = Depends(get_current_user)):
    conv = memory.get_conversation(conv_id, user["user_id"])
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"messages": conv["messages"], "count": len(conv["messages"])}


@router.post("/{conv_id}/messages", summary="追加消息")
def add_message(conv_id: int, body: MessageBody, user: Dict = Depends(get_current_user)):
    if body.role not in ("user", "assistant"):
        raise HTTPException(status_code=400, detail="role 必须为 user 或 assistant")
    conv = memory.add_message(conv_id, user["user_id"], body.role, body.content)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conv


@router.delete("/{conv_id}", summary="删除对话")
def delete_conversation(conv_id: int, user: Dict = Depends(get_current_user)):
    ok = memory.delete_conversation(conv_id, user["user_id"])
    if not ok:
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"ok": True}
