#!/bin/bash
# OpenClaw Phoenix Dashboard Launcher - SIMPLE VERSION (干净版)
#
# 注意：这是简化版 Dashboard
# 原版 Dashboard 请使用：python3 api_server.py --port 8000

cd "$(dirname "$0")"

echo "Starting OpenClaw Phoenix Dashboard (SIMPLE VERSION)..."
echo "Access at: http://localhost:8001"
echo ""

../venv/bin/python web_dashboard_simple.py
