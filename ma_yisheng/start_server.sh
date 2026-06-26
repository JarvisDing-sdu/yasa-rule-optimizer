#!/bin/bash
# 码医生 YASA 扫描后端 - 启动脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── 加载密钥配置 ──────────────────────────────────────────────────────────
if [ -f "/etc/ma_yisheng/env" ]; then
    set -a
    source /etc/ma_yisheng/env
    set +a
fi

# ── 检查并安装依赖 ─────────────────────────────────────────────────────────
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "安装服务器依赖..."
    pip3 install -r server_requirements.txt
fi

# ── 读取启动参数 ───────────────────────────────────────────────────────────
HOST=${API_HOST:-0.0.0.0}
PORT=${API_PORT:-8000}

echo "启动码医生后端：http://$HOST:$PORT"
echo "API 文档：http://$HOST:$PORT/docs"
echo "按 Ctrl+C 停止"
echo ""

exec python3 main.py --host "$HOST" --port "$PORT" 2>/dev/null || exec python3 main.py
