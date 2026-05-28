"""Rate limiting middleware using slowapi."""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# Auth endpoints are stricter
AUTH_LIMITS = {
    "send_code": "3/minute",      # 验证码发送：每分钟最多 3 次
    "login": "10/minute",          # 登录：每分钟最多 10 次
    "register": "5/minute",        # 注册：每分钟最多 5 次
    "reset_password": "3/minute",  # 重置密码：每分钟最多 3 次
}
