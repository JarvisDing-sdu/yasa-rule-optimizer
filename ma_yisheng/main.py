"""马医生 YASA 扫描器 - FastAPI 应用入口（重构版）"""
import os
import time
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from fastapi.staticfiles import StaticFiles
from config import ALLOWED_ORIGINS
from app.database import init_db as init_sqlalchemy_db
from app.middleware.rate_limit import limiter
from app.middleware.security import SecurityHeadersMiddleware
import mimetypes

mimetypes.init()
mimetypes.add_type("text/javascript", ".js", strict=True)
mimetypes.add_type("text/javascript", ".mjs", strict=True)
mimetypes.add_type("text/css", ".css", strict=True)
mimetypes.add_type("application/json", ".json", strict=True)
mimetypes.add_type("image/svg+xml", ".svg", strict=True)
# 生产环境开关：设置 DISABLE_SWAGGER=1 关闭 /docs 和 /openapi.json
DISABLE_SWAGGER = os.environ.get("DISABLE_SWAGGER", "0").strip() == "1"


def _cleanup_worker():
    import time as _time
    while True:
        _time.sleep(3600)
        try:
            from app.deps import _db
            conn = _db()
            cutoff = _time.time() - 7 * 86400
            conn.execute("DELETE FROM scan_tasks WHERE created_at < ? AND status IN ('done','failed','cancelled')", (cutoff,))
            conn.commit()
            conn.close()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app_instance):
    from auth import init_db as init_auth_db
    init_auth_db()
    init_sqlalchemy_db()
    t = threading.Thread(target=_cleanup_worker, daemon=True)
    t.start()
    yield

app = FastAPI(
    title="马医生 YASA 扫描后端",
    version="2.1.0",
    description="代码漏洞扫描 REST API",
    lifespan=lifespan,
    docs_url=None if DISABLE_SWAGGER else "/docs",
    redoc_url=None,
    openapi_url=None if DISABLE_SWAGGER else "/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# CORS：只允许明确配置的 origins，不再有 "*" 回退
if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def access_log(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000
    user_agent = request.headers.get("user-agent", "-")[:60]
    print(
        f'[access] {request.client.host} "{request.method} {request.url.path}" '
        f'{response.status_code} {duration:.0f}ms "{user_agent}"'
    )
    return response


# Routers
from app.routers.auth import router as auth_router
from app.routers.scan import router as scan_router
from app.routers.report import router as report_router
from app.routers.chat import router as chat_router
from app.routers.health import router as health_router
from app.routers.conversation import router as conversation_router
from app.routers.rule_sets import router as rule_sets_router
from app.routers.cve import router as cve_router

app.include_router(auth_router)
app.include_router(scan_router)
app.include_router(report_router)
app.include_router(chat_router)
app.include_router(health_router)
app.include_router(conversation_router)
app.include_router(rule_sets_router)
app.include_router(cve_router)

try:
    from rule_generation_api import router as rule_gen_router
    app.include_router(rule_gen_router)
except Exception as e:
    print(f"[rule-generation] 加载失败: {e}")


# Static frontend
FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "frontend_src",
    "dist"
)
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def _frontend_file_response(name: str, media_type: str = "text/html") -> FileResponse:
    """Serve a built frontend file, falling back to legacy static pages."""
    candidates = [
        os.path.join(FRONTEND_DIR, name),
        os.path.join(STATIC_DIR, name),
    ]
    for file_path in candidates:
        if os.path.isfile(file_path):
            return FileResponse(file_path, media_type=media_type)
    return FileResponse(candidates[0], media_type=media_type)


@app.get("/rule-generation")
async def serve_rule_generation_page():
    return _frontend_file_response("rule-generation.html")


@app.get("/rule-workshop")
async def serve_rule_workshop_page():
    return _frontend_file_response("rule-workshop.html")


if os.path.isdir(FRONTEND_DIR):
    assets_dir = os.path.join(FRONTEND_DIR, "assets")

    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    async def serve_root():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"), media_type="text/html")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = os.path.join(FRONTEND_DIR, full_path)

        if os.path.isfile(file_path):
            return FileResponse(file_path)

        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"), media_type="text/html")

if __name__ == "__main__":
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description="马医生 YASA 扫描后端")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    print(f"启动马医生后端 v2.1：http://{args.host}:{args.port}")
    uvicorn.run("main:app", host=args.host, port=args.port, reload=args.reload)
