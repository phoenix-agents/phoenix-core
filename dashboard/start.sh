#!/bin/bash
# OpenClaw Phoenix Dashboard Launcher

cd "$(dirname "$0")"

echo "Starting OpenClaw Phoenix Dashboard..."
echo "Access at: http://localhost:8000"
echo ""

../venv/bin/python web_dashboard.py
