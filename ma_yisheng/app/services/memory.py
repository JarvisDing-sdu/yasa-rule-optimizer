"""Conversation memory service — stores and retrieves chat history."""
import json
import time
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.conversation import Conversation

MAX_MESSAGES = 60  # Keep last 60 messages per conversation
SUMMARY_THRESHOLD = 40  # Start summarizing when exceeding this


def _get_db() -> Session:
    return SessionLocal()


def create_conversation(user_id: int, title: str = "新对话") -> dict:
    db = _get_db()
    try:
        conv = Conversation(user_id=user_id, title=title[:100], messages="[]")
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return _conv_to_dict(conv)
    finally:
        db.close()


def get_conversation(conv_id: int, user_id: int) -> Optional[dict]:
    db = _get_db()
    try:
        conv = db.query(Conversation).filter_by(id=conv_id, user_id=user_id).first()
        return _conv_to_dict(conv) if conv else None
    finally:
        db.close()


def list_conversations(user_id: int, limit: int = 50) -> list:
    db = _get_db()
    try:
        convs = (
            db.query(Conversation)
            .filter_by(user_id=user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .all()
        )
        return [_conv_to_dict(c) for c in convs]
    finally:
        db.close()


def add_message(conv_id: int, user_id: int, role: str, content: str) -> Optional[dict]:
    """Append a message to conversation, auto-summarize if too long."""
    db = _get_db()
    try:
        # BEGIN IMMEDIATE 获取写锁，防止并发读写造成消息丢失
        db.execute(text("BEGIN IMMEDIATE"))
        conv = db.query(Conversation).filter_by(id=conv_id, user_id=user_id).first()
        if not conv:
            db.rollback()
            return None
        messages = json.loads(conv.messages or "[]")
        messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(messages) > MAX_MESSAGES:
            messages = messages[-MAX_MESSAGES:]
        conv.messages = json.dumps(messages, ensure_ascii=False)
        conv.updated_at = datetime.now(timezone.utc)
        # Auto-title from first user message
        if conv.title == "新对话" and role == "user" and len(messages) <= 2:
            conv.title = content[:50] + ("..." if len(content) > 50 else "")
        db.commit()
        return _conv_to_dict(conv)
    finally:
        db.close()


def get_messages(conv_id: int, user_id: int) -> list:
    """Get message list for a conversation."""
    db = _get_db()
    try:
        conv = db.query(Conversation).filter_by(id=conv_id, user_id=user_id).first()
        if not conv:
            return []
        return json.loads(conv.messages or "[]")
    finally:
        db.close()


def delete_conversation(conv_id: int, user_id: int) -> bool:
    db = _get_db()
    try:
        conv = db.query(Conversation).filter_by(id=conv_id, user_id=user_id).first()
        if not conv:
            return False
        db.delete(conv)
        db.commit()
        return True
    finally:
        db.close()


def _conv_to_dict(conv: Conversation) -> dict:
    return {
        "id": conv.id,
        "user_id": conv.user_id,
        "title": conv.title,
        "messages": json.loads(conv.messages or "[]"),
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
    }
