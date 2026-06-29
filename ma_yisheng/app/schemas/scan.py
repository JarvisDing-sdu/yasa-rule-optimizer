"""Scan/chat request/response schemas."""
from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict

class ScanPathRequest(BaseModel):
    path: str
    lang: str = ""
    scene: str = "full"
    engine: str = "yasa"
    timeout: int = 1800
    rule_set_ids: List[int] = []


class ChatRequest(BaseModel):
    # 兼容旧前端格式：{"messages": [{"role":"user","content":"..."}, ...]}
    # 以及新格式：{"message": "...", "history": [...]}
    message: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None
    history: Optional[list] = None
    deep_thinking: bool = False
    stream: bool = False

    @field_validator('message', mode='before')
    @classmethod
    def message_not_empty(cls, v):
        return v or None

    def get_user_input(self) -> str:
        """Extract the last user message regardless of format."""
        if self.messages:
            # Old format: last message is the user input
            for m in reversed(self.messages):
                if m.get("role") == "user":
                    return m.get("content", "")
        return self.message or ""

    def get_history(self) -> list:
        """Extract chat history regardless of format."""
        if self.history is not None:
            return self.history
        if self.messages:
            return self.messages[:-1]
        return []


class FindingReviewBody(BaseModel):
    finding_id: Optional[str] = None
    review: Optional[str] = None
    fix: Optional[str] = None
    index: Optional[int] = None
    fingerprint: Optional[str] = None
