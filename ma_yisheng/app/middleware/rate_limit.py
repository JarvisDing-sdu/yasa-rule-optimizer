"""Rate limiting middleware using slowapi."""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# Auth endpoints are stricter
AUTH_LIMITS = {
    "send_code": "3/minute",
    "login": "1000/minute",         # 开发调试期间放宽松
    "register": "5/minute",
    "reset_password": "3/minute",
}
