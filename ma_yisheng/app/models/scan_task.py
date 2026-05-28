"""Scan task model."""
from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from app.database import Base
from datetime import datetime, timezone

class ScanTask(Base):
    __tablename__ = "scan_tasks"

    task_id = Column(String(64), primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    status = Column(String(20), default="pending", index=True)
    scan_path = Column(String(1024))
    lang = Column(String(20))
    progress = Column(String(50))
    result = Column(Text)  # JSON string
    created_at = Column(Float)
    finished_at = Column(Float, nullable=True)
