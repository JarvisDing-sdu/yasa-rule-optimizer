"""Auth routes: /api/auth/*"""
from fastapi import APIRouter, HTTPException, Request
from app.schemas.auth import SendCodeRequest, RegisterRequest, LoginRequest, ResetPasswordRequest
from app.middleware.rate_limit import limiter, AUTH_LIMITS

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/send-code", summary="发送邮箱验证码")
@limiter.limit(AUTH_LIMITS["send_code"])
def send_verification_code(request: Request, req: SendCodeRequest):
    from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_NAME, SMTP_SECURITY
    from auth import generate_verification_code, save_verification_code, try_acquire_send_slot
    from email_service import send_verification_email

    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD]):
        raise HTTPException(status_code=503, detail="邮件服务未配置")
    if not try_acquire_send_slot(req.email, interval=60):
        raise HTTPException(status_code=429, detail="发送过于频繁，请 1 分钟后重试")

    code = generate_verification_code()
    smtp_config = {
        "host": SMTP_HOST, "port": SMTP_PORT,
        "user": SMTP_USER, "password": SMTP_PASSWORD,
        "from_name": SMTP_FROM_NAME,
        "security": SMTP_SECURITY,
    }
    ok, err_msg = send_verification_email(req.email, code, smtp_config)
    if not ok:
        raise HTTPException(status_code=500, detail=f"发送邮件失败：{err_msg}")

    save_verification_code(req.email, code, ttl=300)
    return {"message": "验证码已发送，5 分钟内有效"}


@router.post("/register", summary="用户注册")
@limiter.limit(AUTH_LIMITS["register"])
def register(request: Request, req: RegisterRequest):
    from config import JWT_SECRET, JWT_EXPIRE_DAYS
    from auth import verify_code, create_user, create_jwt_token

    if not verify_code(req.email, req.code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="密码至少 8 位")

    user_id = create_user(req.email, req.password)
    if not user_id:
        raise HTTPException(status_code=400, detail="邮箱已注册")

    token = create_jwt_token(user_id, req.email, JWT_SECRET, JWT_EXPIRE_DAYS)
    if not token:
        raise HTTPException(status_code=500, detail="生成 token 失败")
    return {"token": token, "email": req.email}


@router.post("/login", summary="用户登录")
@limiter.limit(AUTH_LIMITS["login"])
def login(request: Request, req: LoginRequest):
    from config import JWT_SECRET, JWT_EXPIRE_DAYS
    from auth import get_user_by_email, verify_password, create_jwt_token
    from auth import check_login_allowed, record_login_fail, record_login_success

    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{req.email}"

    if not check_login_allowed(rate_key):
        raise HTTPException(status_code=429, detail="登录失败次数过多，请 15 分钟后重试")

    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        record_login_fail(rate_key)
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    record_login_success(rate_key)
    token = create_jwt_token(user["id"], user["email"], JWT_SECRET, JWT_EXPIRE_DAYS)
    if not token:
        raise HTTPException(status_code=500, detail="生成 token 失败")
    return {"token": token, "email": user["email"]}


@router.post("/reset-password", summary="重置密码")
@limiter.limit(AUTH_LIMITS["reset_password"])
def reset_password(request: Request, req: ResetPasswordRequest):
    from auth import verify_code, reset_password, get_user_by_email

    if not get_user_by_email(req.email):
        raise HTTPException(status_code=404, detail="该邮箱未注册")
    if not verify_code(req.email, req.code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="密码至少 8 位")
    if not reset_password(req.email, req.new_password):
        raise HTTPException(status_code=500, detail="重置失败")
    return {"message": "密码已重置，请重新登录"}
