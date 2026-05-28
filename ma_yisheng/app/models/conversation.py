"""Conversation model for persistent chat memory."""
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base
from datetime import datetime, timezone


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String(255), default="新对话")
    messages = Column(Text, default="[]")  # JSON array of {role, content, timestamp}
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
