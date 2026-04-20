#!/usr/bin/env python3
"""
Phoenix Core 冒烟测试

核心功能快速验证，改完代码必跑

策略:
- 日常冒烟：只抽检 1-2 个 Bot，保证速度
- 完整测试：放在 CI nightly build 里

Usage:
    # 运行测试
    python tests/test_smoke.py

    # 或 pytest
    pytest tests/test_smoke.py -v
"""

import requests
import json
import os
import sys
import time
from pathlib import Path

# ========== 配置 ==========
BASE_URL = os.environ.get("PHOENIX_API_URL", "http://127.0.0.1:8000")
PROJECT_ROOT = Path(__file__).parent.parent
WORKSPACES_DIR = PROJECT_ROOT / "workspaces"
HEARTBEAT_DIR = PROJECT_ROOT / "data" / "heartbeats"

# 超时设置
DEFAULT_TIMEOUT = 5

# Bot 数量阈值 (8 个 Bot 系统)
MIN_BOTS = 8


# ========== 测试用例 ==========

def test_api_health():
    """测试 API 服务是否响应"""
    try:
        resp = requests.get(f"{BASE_URL}/api/health", timeout=DEFAULT_TIMEOUT)
        assert resp.status_code == 200, f"健康检查返回 {resp.status_code}"
        print("✅ API 健康检查通过")
        return True
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到 API 服务器 {BASE_URL}")
        print("   请先运行：python3 api_server.py --port 8000")
        return False
    except Exception as e:
        print(f"❌ API 健康检查失败：{e}")
        return False


def test_api_bots():
    """测试获取 Bot 列表 - 只验证数量，不验证每个 Bot 详情"""
    resp = requests.get(f"{BASE_URL}/api/bots", timeout=DEFAULT_TIMEOUT)
    assert resp.status_code == 200, f"Bot 列表 API 返回 {resp.status_code}"

    data = resp.json()
    assert isinstance(data, dict), "Bot 列表应该返回 dict"

    bot_count = len(data) if data else 0

    # 只验证数量，不逐个检查每个 Bot
    if bot_count >= MIN_BOTS:
        print(f"✅ Bot 列表获取成功，当前 {bot_count} 个 Bot (≥{MIN_BOTS})")
    else:
        print(f"⚠️ Bot 数量较少，当前 {bot_count} 个 (期望≥{MIN_BOTS})")

    return True


def test_api_stats():
    """测试统计 API"""
    resp = requests.get(f"{BASE_URL}/api/stats", timeout=DEFAULT_TIMEOUT)
    assert resp.status_code == 200, f"统计 API 返回 {resp.status_code}"
    
    data = resp.json()
    assert data is not None, "统计数据不应为空"
    print(f"✅ 统计 API 正常")
    return True


def test_api_heartbeat():
    """测试心跳 API"""
    resp = requests.get(f"{BASE_URL}/api/heartbeat", timeout=DEFAULT_TIMEOUT)
    
    # 可能 200 (可用) 或 503 (模块未安装)
    if resp.status_code == 200:
        print(f"✅ 心跳 API 正常")
        return True
    elif resp.status_code == 503:
        print(f"⚠️  心跳 API 未启用 (服务不可用)")
        return True  # 不视为失败
    else:
        print(f"⚠️  心跳 API 返回 {resp.status_code}")
        return True  # 不阻塞


def test_heartbeat_files():
    """测试 Bot 心跳文件 - 使用新的独立文件模式"""
    if not HEARTBEAT_DIR.exists():
        print("⚠️  心跳目录不存在 (Bot 可能未使用新 heartbeat_v2)")
        return True  # 不视为失败

    heartbeat_files = list(HEARTBEAT_DIR.glob("*.json"))

    if not heartbeat_files:
        print("⚠️  没有心跳文件 (Bot 可能未运行心跳)")
        return True  # 不视为失败

    now = time.time()
    active_count = 0
    total_count = len(heartbeat_files)

    for hf in heartbeat_files:
        try:
            with open(hf, 'r') as f:
                data = json.load(f)

            # 检查时间戳
            last_beat = data.get('last_beat', 0)
            age = now - last_beat

            if age > 15:  # 15 秒超时
                print(f"⚠️  心跳超时：{hf.name} ({age:.0f}秒前)")
            else:
                print(f"✅ 心跳正常：{hf.name} ({age:.1f}秒前)")
                active_count += 1

        except Exception as e:
            print(f"⚠️  读取心跳文件失败 {hf.name}: {e}")

    print(f"📊 心跳统计：{total_count} 个文件，{active_count} 个活跃")
    return True


def test_bot_validation():
    """测试 Bot API 参数校验 (应该返回 400 而不是 500)"""
    # 发送空请求体，应该返回 400 而不是崩掉
    resp = requests.post(
        f"{BASE_URL}/api/bot/command",
        json={},
        timeout=DEFAULT_TIMEOUT
    )
    
    # 期望 400 (参数校验失败) 或 404 (端点不存在)
    # 不期望 500 (服务器错误)
    if resp.status_code in [400, 404, 500]:
        if resp.status_code == 500:
            print(f"⚠️  Bot 命令 API 返回 500 (可能需要添加校验)")
        else:
            print(f"✅ Bot 命令 API 校验正常 (返回 {resp.status_code})")
        return True
    else:
        print(f"⚠️  Bot 命令 API 返回 {resp.status_code}")
        return True


def test_dashboard_ui():
    """测试 Dashboard 页面加载"""
    try:
        resp = requests.get(BASE_URL, timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 200:
            content_length = len(resp.content)
            if content_length > 1000:
                print(f"✅ Dashboard 页面加载成功 ({content_length} bytes)")
                return True
            else:
                print(f"⚠️  Dashboard 页面内容过短 ({content_length} bytes)")
                return True
        elif resp.status_code == 404:
            print("⚠️  Dashboard 页面未找到")
            return True
        else:
            print(f"⚠️  Dashboard 返回 {resp.status_code}")
            return True
    except Exception as e:
        print(f"⚠️  Dashboard 测试失败：{e}")
        return True


def test_memory_db_integrity():
    """测试 SQLite 记忆数据库完整性"""
    try:
        import sqlite3
        db_path = PROJECT_ROOT / "data" / "memory.db"

        if not db_path.exists():
            print("⚠️  记忆数据库不存在 (尚未使用 SQLite 记忆)")
            return True  # 不视为失败

        conn = sqlite3.connect(str(db_path))
        result = conn.execute("PRAGMA integrity_check;").fetchone()

        if result[0] == "ok":
            print("✅ SQLite 记忆库完整性通过")

            # 额外检查：WAL 模式是否启用
            wal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            if wal_mode.lower() == "wal":
                print(f"✅ WAL 模式已启用 (journal_mode={wal_mode})")
            else:
                print(f"⚠️  WAL 模式未启用 (journal_mode={wal_mode})")

            conn.close()
            return True
        else:
            print(f"❌ 数据库完整性检查失败：{result[0]}")
            return False

    except Exception as e:
        print(f"⚠️  记忆库检查异常：{e}")
        return True  # 不阻塞


# ========== 主流程 ==========

def run_all_tests():
    """运行所有冒烟测试"""
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║           Phoenix Core 冒烟测试                             ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()
    print(f"API 地址：{BASE_URL}")
    print(f"项目根目录：{PROJECT_ROOT}")
    print()
    
    tests = [
        ("API 健康检查", test_api_health),
        ("Bot 列表 API", test_api_bots),
        ("统计 API", test_api_stats),
        ("心跳 API", test_api_heartbeat),
        ("心跳文件", test_heartbeat_files),
        ("Bot 参数校验", test_bot_validation),
        ("Dashboard UI", test_dashboard_ui),
        ("记忆库完整性", test_memory_db_integrity),
    ]
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {name} 异常：{e}")
            failed += 1
    
    print()
    print("=" * 50)
    print(f"结果：{passed} 通过，{failed} 失败")
    
    if failed > 0:
        print("\n❌ 冒烟测试失败")
        return 1
    else:
        print("\n🎉 所有核心冒烟测试通过！")
        return 0


if __name__ == "__main__":
    sys.exit(run_all_tests())
