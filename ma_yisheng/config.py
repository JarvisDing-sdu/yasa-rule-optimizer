# -*- coding: utf-8 -*-
"""配置加载模块"""

import os
from pathlib import Path

# 尝试加载 .env
try:
    from dotenv import load_dotenv
    # 优先从系统安全目录加载密钥，再加载项目 .env（用于本地开发覆盖）
    load_dotenv("/etc/ma_yisheng/env")
    load_dotenv()
except ImportError:
    pass


def get_project_root() -> Path:
    """获取项目根目录（脚本所在目录）"""
    return Path(__file__).resolve().parent


def get_reports_dir() -> Path:
    """获取报告保存目录"""
    return get_project_root() / "yasa-reports"


RECENT_PATHS_FILE = "recent_paths.json"
RECENT_PATHS_MAX = 10


def get_recent_paths() -> list:
    """获取最近扫描路径列表，最多 RECENT_PATHS_MAX 条"""
    p = get_project_root() / RECENT_PATHS_FILE
    if not p.exists():
        return []
    try:
        import json
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        paths = data.get("paths", [])
        return [x for x in paths if isinstance(x, str) and x.strip()][:RECENT_PATHS_MAX]
    except Exception:
        return []


def add_recent_path(path: str) -> None:
    """将路径加入最近列表，已存在则移到最前"""
    path = (path or "").strip()
    if not path:
        return
    paths = get_recent_paths()
    if path in paths:
        paths.remove(path)
    paths.insert(0, path)
    paths = paths[:RECENT_PATHS_MAX]
    try:
        import json
        p = get_project_root() / RECENT_PATHS_FILE
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"paths": paths}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# 配置项
YASA_BUNDLE_PATH = os.environ.get("YASA_BUNDLE_PATH", "").strip()
YASA_EXECUTABLE = os.environ.get("YASA_EXECUTABLE", "yasa").strip()
UAST_PYTHON_EXE = os.environ.get("UAST_PYTHON_EXE", "uast4py-linux-amd64").strip()
UAST_GO_EXE = os.environ.get("UAST_GO_EXE", "uast4go-linux-amd64").strip()
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "deepseek").strip()
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com").strip()
LLM_API_KEY = os.environ.get("LLM_API_KEY", "").strip()
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-v4-pro").strip()
# 服务器模式：设置 SERVER_URL 后客户端将所有扫描、LLM 请求全部转发到远程 API
SERVER_URL = os.environ.get("SERVER_URL", "http://47.94.95.178:8000").strip().rstrip("/")
SERVER_MODE = bool(SERVER_URL)
# SCAN_TIMEOUT: 秒数，默认 300（5分钟），0 表示无限制
try:
    _st = os.environ.get("SCAN_TIMEOUT", "300").strip()
    SCAN_TIMEOUT = int(_st) if _st else 300
except ValueError:
    SCAN_TIMEOUT = 300

# 扫描时排除的目录（逗号分隔），这些目录不会被 YASA 扫描
DEFAULT_EXCLUDE_DIRS = "node_modules,.git,__pycache__,.venv,venv,dist,build,.idea,.vscode,target,.mypy_cache,.pytest_cache,.tox,vendor,.next,.nuxt,coverage,eggs,.eggs"
_exclude_raw = os.environ.get("SCAN_EXCLUDE_DIRS", "").strip()
SCAN_EXCLUDE_DIRS = [d.strip() for d in (_exclude_raw or DEFAULT_EXCLUDE_DIRS).split(",") if d.strip()]

# 上传文件大小限制（字节），默认 100MB
MAX_UPLOAD_SIZE = int(os.environ.get("MAX_UPLOAD_SIZE", str(100 * 1024 * 1024)).strip() or str(100 * 1024 * 1024))

# Semgrep 离线规则目录（留空则使用在线 p/xxx 规则集）
SEMGREP_RULES_PATH = os.environ.get("SEMGREP_RULES_PATH", "").strip()

# CORS 允许的前端域名，逗号分隔，留空则不允许跨域携带凭证
# 示例：ALLOWED_ORIGINS=http://localhost:3000,https://your-domain.com
_origins_raw = os.environ.get("ALLOWED_ORIGINS", "").strip()
ALLOWED_ORIGINS: list = [o.strip() for o in _origins_raw.split(",") if o.strip()]

# 认证配置
_JWT_SECRET_RAW = os.environ.get("JWT_SECRET", "").strip()
_WEAK_JWT_DEFAULTS = {
    "change-this-secret-key-in-production",
    "change-this-to-a-random-secret-key",
    "",
}
if _JWT_SECRET_RAW in _WEAK_JWT_DEFAULTS:
    import secrets as _secrets
    _JWT_SECRET_RAW = _secrets.token_urlsafe(48)
    print("[config] JWT_SECRET 未设置或仍为默认值，已自动替换为随机密钥（服务重启后失效，请在 .env 中设置 JWT_SECRET）")
JWT_SECRET = _JWT_SECRET_RAW
JWT_EXPIRE_DAYS = int(os.environ.get("JWT_EXPIRE_DAYS", "30").strip() or "30")

# SMTP 邮件配置
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587").strip() or "587")
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "马医生").strip()



def _to_wsl_path(p: Path) -> str:
    """将 Windows 路径转为 WSL 内路径"""
    path = p.resolve()
    drive = path.drive
    if not drive:
        return str(path)
    letter = drive[0].lower()
    rest = path.relative_to(drive)
    return f"/mnt/{letter}{rest.as_posix()}"


def get_rule_config_path(lang: str, scene: str = "") -> str:
    """根据语言和场景返回规则文件路径（WSL 内路径）。全部使用项目 rules/，不依赖 YASA bundle"""
    scene = (scene or "minimal").lower()
    lang = lang.lower()
    p = get_project_root() / "rules" / f"rule_config_{lang}_{scene}.json"
    if p.exists():
        return _to_wsl_path(p)
    return ""


def get_checker_pack_and_analyzer(lang: str, scene: str = "") -> tuple:
    """返回 (checkerPackIds, analyzer)，用于污点分析"""
    m = {
        ("python", "minimal"): ("taint-flow-python-default", "PythonAnalyzer"),
        ("python", "full"): ("taint-flow-python-default", "PythonAnalyzer"),
        ("python", "xast"): ("taint-flow-python-default", "PythonAnalyzer"),
        ("java", "minimal"): ("taint-flow-java-default", "JavaAnalyzer"),
        ("java", "full"): ("taint-flow-java-default", "JavaAnalyzer"),
        ("js", "minimal"): ("taint-flow-javascript-default", "JavaScriptAnalyzer"),
        ("js", "full"): ("taint-flow-javascript-default", "JavaScriptAnalyzer"),
        ("php", "minimal"): ("taint-flow-php-default", "PhpAnalyzer"),
        ("php", "full"): ("taint-flow-php-default", "PhpAnalyzer"),
        ("go", "minimal"): ("taint-flow-golang-default", "GoAnalyzer"),
        ("go", "full"): ("taint-flow-golang-default", "GoAnalyzer"),
        ("c", "minimal"): ("taint-flow-c-default", "CAnalyzer"),
        ("c", "full"): ("taint-flow-c-default", "CAnalyzer"),
    }
    key = (lang.lower(), scene.lower() if scene else "minimal")
    if key in m:
        return m[key]
    if lang.lower() == "python":
        return ("taint-flow-python-default", "PythonAnalyzer")
    if lang.lower() == "java":
        return ("taint-flow-java-default", "JavaAnalyzer")
    if lang.lower() == "js":
        return ("taint-flow-javascript-default", "JavaScriptAnalyzer")
    if lang.lower() == "php":
        return ("taint-flow-php-default", "PhpAnalyzer")
    if lang.lower() == "go":
        return ("taint-flow-golang-default", "GoAnalyzer")
    if lang.lower() == "c":
        return ("taint-flow-c-default", "CAnalyzer")
    return ("", "")


def get_uast_sdk_path(lang: str) -> str:
    """根据语言返回 uast SDK 路径（仅 Python/Go 需要）"""
    base = YASA_BUNDLE_PATH.rstrip("/")
    if not base:
        return ""
    if lang.lower() == "python":
        exe = UAST_PYTHON_EXE or "uast4py-linux-amd64"
        return f"{base}/{exe}"
    if lang.lower() == "go":
        exe = UAST_GO_EXE or "uast4go-linux-amd64"
        return f"{base}/{exe}"
    return ""


def is_configured() -> bool:
    """检查必要配置是否完整"""
    if not YASA_BUNDLE_PATH:
        return False
    yasa_path = Path(YASA_BUNDLE_PATH) / YASA_EXECUTABLE
    # 无法直接检查 WSL 内路径，只检查配置是否存在
    return True


def save_env_config(updates: dict) -> bool:
    """
    将配置项保存到 .env 文件。updates 格式: {"YASA_BUNDLE_PATH": "/home/xx/yasa", ...}
    保留 .env 中其他未修改的项。
    """
    env_path = get_project_root() / ".env"
    output = []
    written_keys = set()
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for ln in f:
                    s = ln.strip()
                    if "=" in s and not s.startswith("#"):
                        k = s.split("=", 1)[0].strip()
                        if k in updates:
                            output.append(f"{k}={str(updates.get(k) or '').strip()}")
                            written_keys.add(k)
                        else:
                            output.append(ln.rstrip("\n"))
                    else:
                        output.append(ln.rstrip("\n"))
        except Exception:
            output = []
    for k, v in updates.items():
        if k not in written_keys:
            output.append(f"{k}={str(v or '').strip()}")
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(output) + ("\n" if output else ""))
        reload_config()
        return True
    except Exception:
        return False


def save_scan_timeout(seconds: int) -> bool:
    """将 SCAN_TIMEOUT 保存到 .env，用于对话/Agent 的默认扫描超时"""
    global SCAN_TIMEOUT
    env_path = get_project_root() / ".env"
    lines = []
    found = False
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for ln in f:
                if ln.strip().startswith("SCAN_TIMEOUT="):
                    lines.append(f"SCAN_TIMEOUT={seconds}\n")
                    found = True
                else:
                    lines.append(ln)
    if not found:
        lines.append(f"\n# 扫描超时（秒），0=无限制\nSCAN_TIMEOUT={seconds}\n")
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        reload_config()
        return True
    except Exception:
        return False


def get_missing_config() -> list:
    """返回缺失的配置项（服务器模式只需 SERVER_URL 已设置即视为完整）"""
    if SERVER_MODE:
        return []
    missing = []
    if not YASA_BUNDLE_PATH:
        missing.append("YASA_BUNDLE_PATH（YASA 安装目录的 WSL 路径，如 /home/csj/yasa-linux-x64）")
    if not LLM_API_KEY:
        missing.append("LLM_API_KEY（DeepSeek 或 OpenAI 的 API Key）")
    return missing


def reload_config() -> None:
    """重新加载 .env 并更新配置（配置向导保存后调用）"""
    global YASA_BUNDLE_PATH, YASA_EXECUTABLE, UAST_PYTHON_EXE, UAST_GO_EXE, LLM_PROVIDER, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, SCAN_TIMEOUT, SCAN_EXCLUDE_DIRS, SERVER_URL, SERVER_MODE, JWT_SECRET, JWT_EXPIRE_DAYS, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_NAME, SEMGREP_RULES_PATH, ALLOWED_ORIGINS
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except ImportError:
        pass
    YASA_BUNDLE_PATH = os.environ.get("YASA_BUNDLE_PATH", "").strip()
    YASA_EXECUTABLE = os.environ.get("YASA_EXECUTABLE", "yasa").strip()
    UAST_PYTHON_EXE = os.environ.get("UAST_PYTHON_EXE", "uast4py-linux-amd64").strip()
    UAST_GO_EXE = os.environ.get("UAST_GO_EXE", "uast4go-linux-amd64").strip()
    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "deepseek").strip()
    LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com").strip()
    LLM_API_KEY = os.environ.get("LLM_API_KEY", "").strip()
    LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-v4-pro").strip()
    try:
        _st = os.environ.get("SCAN_TIMEOUT", "300").strip()
        SCAN_TIMEOUT = int(_st) if _st else 300
    except ValueError:
        SCAN_TIMEOUT = 300
    _exclude_raw = os.environ.get("SCAN_EXCLUDE_DIRS", "").strip()
    SCAN_EXCLUDE_DIRS = [d.strip() for d in (_exclude_raw or DEFAULT_EXCLUDE_DIRS).split(",") if d.strip()]
    SERVER_URL = os.environ.get("SERVER_URL", "http://47.94.95.178:8000").strip().rstrip("/")
    SERVER_MODE = bool(SERVER_URL)
    JWT_SECRET = os.environ.get("JWT_SECRET", "change-this-secret-key-in-production").strip()
    JWT_EXPIRE_DAYS = int(os.environ.get("JWT_EXPIRE_DAYS", "30").strip() or "30")
    SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587").strip() or "587")
    SMTP_USER = os.environ.get("SMTP_USER", "").strip()
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()
    SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "马医生").strip()
    SEMGREP_RULES_PATH = os.environ.get("SEMGREP_RULES_PATH", "").strip()
    _origins_raw = os.environ.get("ALLOWED_ORIGINS", "").strip()
    ALLOWED_ORIGINS = [o.strip() for o in _origins_raw.split(",") if o.strip()]
