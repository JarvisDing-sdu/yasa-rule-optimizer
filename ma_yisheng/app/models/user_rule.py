"""Per-user rule library models."""
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey
from app.database import Base
from datetime import datetime, timezone


class UserRuleSet(Base):
    __tablename__ = "user_rule_sets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1024), default="")
    source_type = Column(String(32), default="generated")  # official_clone | generated | manual
    lang = Column(String(16), nullable=False)
    scene = Column(String(16), default="full")
    is_active = Column(Integer, default=1)
    rule_count = Column(Integer, default=0)
    created_at = Column(Float, default=lambda: datetime.now(timezone.utc).timestamp())
    updated_at = Column(Float, default=lambda: datetime.now(timezone.utc).timestamp(),
                        onupdate=lambda: datetime.now(timezone.utc).timestamp())


class UserRule(Base):
    __tablename__ = "user_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_set_id = Column(Integer, ForeignKey("user_rule_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_data = Column(Text, nullable=False)  # JSON string of single rule
    rule_id = Column(String(255), nullable=False)  # metadata.ruleId
    is_enabled = Column(Integer, default=1)
    created_at = Column(Float, default=lambda: datetime.now(timezone.utc).timestamp())
