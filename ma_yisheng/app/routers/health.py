"""Health + admin routes."""
from datetime import datetime
from typing import Any, Dict
from fastapi import APIRouter, Depends
from app.deps import get_current_user

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", summary="健康检查")
def health_check() -> Dict[str, Any]:
    from config import LLM_API_KEY, YASA_BUNDLE_PATH
    return {
        "status": "ok",
        "service": "码医生后端",
        "yasa_configured": bool(YASA_BUNDLE_PATH),
        "llm_configured": bool(LLM_API_KEY),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/me", summary="获取当前用户信息")
def me_endpoint(user: Dict = Depends(get_current_user)) -> Dict[str, Any]:
    return {"user_id": user["user_id"], "email": user["email"]}
