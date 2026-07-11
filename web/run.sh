#!/usr/bin/env bash
set -e

# PageHarvest — 一键启动 Web 应用

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
cd "$ROOT"

PORT="${PORT:-8080}"
HOST="0.0.0.0"

echo "✦ PageHarvest 启动中..."
echo ""
echo "   请在浏览器打开: http://localhost:$PORT"
echo "   (本地服务器，数据不上传互联网)"
echo ""
echo "   按 Ctrl+C 停止"
echo ""

PYTHON="${PYTHON:-python3}"

# 检查必要依赖
$PYTHON -c "import flask" 2>/dev/null || {
  echo "缺少依赖，尝试安装..."
  pip3 install --break-system-packages flask openpyxl pandas 2>&1 | tail -3
}

exec $PYTHON -m web.app --host "$HOST" --port "$PORT"
