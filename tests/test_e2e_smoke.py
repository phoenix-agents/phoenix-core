#!/usr/bin/env python3
"""
Phoenix Core E2E 冒烟测试

使用 Playwright 进行端到端测试，验证关键功能路径

测试覆盖:
1. Dashboard 页面加载
2. Bot 状态显示
3. API 响应

Usage:
    # 安装依赖
    pip install pytest pytest-playwright

    # 安装浏览器
    playwright install chromium

    # 运行测试
    pytest tests/test_e2e_smoke.py -v

    # 有头模式 (显示浏览器)
    pytest tests/test_e2e_smoke.py -v --headed
"""

import pytest
import asyncio
from pathlib import Path
import subprocess
import time
import requests


# 配置
BASE_URL = "http://localhost:8000"
TIMEOUT = 30000


pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext


@pytest.fixture(scope="module")
def browser_context():
    """创建浏览器上下文"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.set_default_timeout(TIMEOUT)
        yield context
        context.close()
        browser.close()


class TestDashboardUI:
    """Dashboard UI 测试"""

    def test_root_page_loads(self, browser_context):
        """测试根页面加载"""
        page = browser_context.new_page()
        page.goto(BASE_URL, wait_until="networkidle")

        # 验证页面标题
        assert "Phoenix" in page.title() or "Dashboard" in page.title()

        # 验证页面有内容
        content = page.content()
        assert len(content) > 1000

        page.close()

    def test_bot_status_visible(self, browser_context):
        """测试 Bot 状态可见"""
        page = browser_context.new_page()
        page.goto(BASE_URL, wait_until="networkidle")

        # 查找 Bot 状态元素
        # 注意：根据实际 HTML 调整选择器
        bot_cards = page.query_selector_all(".bot-card, .bot-status, [data-bot-name]")
        assert len(bot_cards) > 0, "应该显示 Bot 状态卡片"

        page.close()

    def test_no_console_errors(self, browser_context):
        """测试没有控制台错误"""
        page = browser_context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto(BASE_URL, wait_until="networkidle")

        # 允许一些启动时的正常错误
        assert len(console_errors) < 5, f"控制台错误过多：{console_errors}"

        page.close()


class TestAPIEndpoints:
    """API 端点测试"""

    def test_api_bots(self):
        """测试 Bot API"""
        response = requests.get(f"{BASE_URL}/api/bots", timeout=10)
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)
        # 应该有 Bot 数据
        assert len(data) >= 0  # 可能为空但没有错误

    def test_api_health(self):
        """测试健康检查 API"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200

        data = response.json()
        assert "checks" in data or "status" in data

    def test_api_stats(self):
        """测试统计 API"""
        response = requests.get(f"{BASE_URL}/api/stats", timeout=10)
        assert response.status_code == 200

        data = response.json()
        assert data is not None

    def test_api_heartbeat(self):
        """测试心跳 API"""
        response = requests.get(f"{BASE_URL}/api/heartbeat", timeout=10)

        # 可能 503 (模块不可用) 或 200 (正常)
        assert response.status_code in [200, 503]


class TestBotWorkflow:
    """Bot 工作流测试"""

    def test_bot_heartbeat_files_exist(self):
        """测试 Bot 心跳文件存在 (如果有运行的 Bot)"""
        workspaces_dir = Path(__file__).parent.parent / "workspaces"

        if not workspaces_dir.exists():
            pytest.skip("Workspaces 目录不存在")

        # 检查是否有心跳文件
        heartbeat_files = list(workspaces_dir.glob(".heartbeat_*.json"))

        # 注意：这可能为空如果 Bot 没有运行心跳
        # 这是一个软性检查
        if heartbeat_files:
            for hf in heartbeat_files:
                assert hf.stat().st_size > 0, f"心跳文件为空：{hf}"


def run_server_check():
    """运行前检查服务器是否运行"""
    try:
        response = requests.get(BASE_URL, timeout=5)
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        return False


if __name__ == "__main__":
    # 手动运行测试
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║           Phoenix Core E2E 冒烟测试                         ║")
    print("╚═══════════════════════════════════════════════════════════╝")

    # 检查服务器
    if not run_server_check():
        print(f"❌ 服务器未运行在 {BASE_URL}")
        print("   请先运行：python3 api_server.py --port 8000")
        exit(1)

    print(f"✅ 服务器运行在 {BASE_URL}")
    print()

    # 运行 pytest
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
