#!/bin/bash
# Phoenix Core - 一键启动脚本
# 用法：bash start.sh [workspace_name]

set -e

WORKSPACE=${1:-"客服"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=================================================="
echo "  Phoenix Core - 一键启动"
echo "=================================================="
echo ""
echo "工作区：$WORKSPACE"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 检查依赖
if [ ! -d "venv" ]; then
    echo "📦 首次运行，正在安装依赖..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo ""
echo "=================================================="
echo "  启动服务"
echo "=================================================="
echo ""

# 启动 API Server (端口 8000，包含 Dashboard)
echo "🌐 启动 Dashboard: http://localhost:8000"
python3 api_server.py --port 8000 &
API_PID=$!

# 等待 API Server 启动
sleep 3

# 启动 Bot
echo "🤖 启动 Bot: $WORKSPACE"
python3 phoenix_core_gateway_v2.py --workspace "workspaces/$WORKSPACE" &
BOT_PID=$!

echo ""
echo "=================================================="
echo "  ✅ 启动完成!"
echo "=================================================="
echo ""
echo "  Dashboard: http://localhost:8000"
echo "  API:       http://localhost:8000/api"
echo ""
echo "  按 Ctrl+C 停止所有服务"
echo ""

# 等待用户中断
trap "echo ''; echo '正在停止服务...'; kill $API_PID $BOT_PID 2>/dev/null; echo '已停止'; exit 0" INT

# 保持运行
wait
