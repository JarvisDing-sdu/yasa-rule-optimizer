"""Runtime configuration routes."""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

router = APIRouter(prefix="/api/config", tags=["config"])


class RuntimeConfigUpdate(BaseModel):
    YASA_BUNDLE_PATH: str = ""
    YASA_EXECUTABLE: str = "yasa"
    UAST_PYTHON_EXE: str = "uast4py-linux-amd64"
    UAST_GO_EXE: str = "uast4go-linux-amd64"
    LLM_PROVIDER: str = "deepseek"
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-v4-pro"
    SERVER_URL: str = ""
    GITHUB_TOKEN: str = ""
    SEMGREP_RULES_PATH: str = ""
    SCAN_TIMEOUT: str = "300"
    SMTP_HOST: str = ""
    SMTP_PORT: str = "587"
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "马医生"
    SMTP_SECURITY: str = "auto"

    @field_validator("*", mode="before")
    @classmethod
    def coerce_to_string(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value)


CONFIG_KEYS = tuple(RuntimeConfigUpdate.model_fields.keys())


@router.get("")
def get_runtime_config():
    import config

    if not config.CONFIG_UI_ENABLED:
        return {
            "values": {},
            "configured": {
                "yasa": bool(config.YASA_BUNDLE_PATH),
                "llm": bool(config.LLM_API_KEY),
            },
            "missing": [],
            "env_path": "",
            "editable": False,
        }

    values = {key: getattr(config, key, "") for key in CONFIG_KEYS}
    return {
        "values": values,
        "configured": {
            "yasa": bool(config.YASA_BUNDLE_PATH),
            "llm": bool(config.LLM_API_KEY),
        },
        "missing": config.get_missing_config(),
        "env_path": str(config.get_env_path()),
        "editable": True,
    }


@router.post("")
def update_runtime_config(payload: RuntimeConfigUpdate):
    import config

    if not config.CONFIG_UI_ENABLED:
        raise HTTPException(status_code=403, detail="服务器部署已关闭在线环境配置")

    updates = {key: str(getattr(payload, key, "") or "").strip() for key in CONFIG_KEYS}
    if not config.save_env_config(updates):
        raise HTTPException(status_code=500, detail="保存配置失败")

    return {
        "ok": True,
        "configured": {
            "yasa": bool(config.YASA_BUNDLE_PATH),
            "llm": bool(config.LLM_API_KEY),
        },
        "missing": config.get_missing_config(),
    }


class MailTestRequest(BaseModel):
    to_email: str


@router.post("/test-mail")
def test_mail(payload: MailTestRequest):
    import config
    from email_service import send_verification_email

    if not config.CONFIG_UI_ENABLED:
        raise HTTPException(status_code=403, detail="服务器部署已关闭在线环境配置")

    if not payload.to_email.strip():
        raise HTTPException(status_code=400, detail="请填写测试收件邮箱")

    smtp_config = {
        "host": config.SMTP_HOST,
        "port": config.SMTP_PORT,
        "user": config.SMTP_USER,
        "password": config.SMTP_PASSWORD,
        "from_name": config.SMTP_FROM_NAME,
        "security": config.SMTP_SECURITY,
    }
    ok, err_msg = send_verification_email(payload.to_email.strip(), "123456", smtp_config)
    if not ok:
        raise HTTPException(status_code=500, detail=err_msg)
    return {"ok": True, "message": "测试邮件已发送"}


@router.post("/clear-login-locks")
def clear_login_locks():
    from auth import get_db_path
    import sqlite3

    conn = sqlite3.connect(str(get_db_path()), check_same_thread=False)
    try:
        conn.execute("DELETE FROM login_attempts")
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "message": "登录失败锁定已清除"}
