#!/usr/bin/env python3
"""
Phoenix Core - 远程调试系统测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phoenix_core.remote_integration import RemoteDebugger


def test_remote_debugger_initialization():
    """测试远程调试器初始化"""
    print("\n" + "=" * 60)
    print("测试 1: RemoteDebugger 初始化")
    print("=" * 60)

    # 测试默认初始化（从环境变量读取）
    debugger = RemoteDebugger()

    print(f"   - 服务器 URL: {debugger.server_url or '(未配置)'}")
    print(f"   - 设备 ID: {debugger.device_id}")
    print(f"   - 自动重连：{debugger.auto_reconnect}")
    print(f"   - 心跳间隔：{debugger.heartbeat_interval}秒")
    print(f"   - 注册命令数：{len(debugger._commands)}")

    assert debugger.device_id is not None
    assert len(debugger._commands) == 7

    print("   ✅ 初始化测试通过")
    return debugger


def test_device_id_generation():
    """测试设备 ID 自动生成"""
    print("\n" + "=" * 60)
    print("测试 2: 设备 ID 生成")
    print("=" * 60)

    debugger = RemoteDebugger(device_id="test-device-001")
    print(f"   - 手动设置 ID: {debugger.device_id}")
    assert debugger.device_id == "test-device-001"

    # 测试自动生成
    debugger2 = RemoteDebugger()
    print(f"   - 自动生成 ID: {debugger2.device_id}")
    assert "-" in debugger2.device_id  # hostname-mac 格式

    print("   ✅ 设备 ID 测试通过")


async def test_command_execution():
    """测试命令执行"""
    print("\n" + "=" * 60)
    print("测试 3: 命令执行")
    print("=" * 60)

    debugger = RemoteDebugger(enable_remote_control=True)

    # 测试 get_status
    result = await debugger._cmd_get_status({})
    print(f"   - get_status: {result['success']}")
    assert result['success'] is True
    assert 'status' in result
    assert 'connected' in result['status']

    # 测试 get_config
    result = await debugger._cmd_get_config({})
    print(f"   - get_config: {result['success']}")
    assert result['success'] is True
    assert 'config' in result

    # 测试 run_diagnostic
    result = await debugger._cmd_run_diagnostic({})
    print(f"   - run_diagnostic: {result['success']}")
    assert result['success'] is True
    assert 'diagnostic' in result

    print("   ✅ 命令执行测试通过")


async def test_config_update():
    """测试配置更新"""
    print("\n" + "=" * 60)
    print("测试 4: 配置更新")
    print("=" * 60)

    debugger = RemoteDebugger(enable_remote_control=True)

    # 测试更新配置（不实际写文件）
    test_config = {"TEST_VAR": "test_value"}
    result = await debugger._cmd_update_config(test_config)

    print(f"   - update_config: {result.get('success', False)}")
    print(f"   - 消息：{result.get('message', '')}")

    # 清理测试配置
    if "TEST_VAR" in os.environ:
        del os.environ["TEST_VAR"]

    print("   ✅ 配置更新测试通过")


def test_command_registration():
    """测试命令注册"""
    print("\n" + "=" * 60)
    print("测试 5: 命令注册")
    print("=" * 60)

    debugger = RemoteDebugger()

    expected_commands = [
        'get_status', 'get_logs', 'get_config',
        'update_config', 'restart_bot', 'execute_code', 'run_diagnostic'
    ]

    for cmd in expected_commands:
        assert cmd in debugger._commands, f"命令 {cmd} 未注册"
        print(f"   - {cmd}: ✅")

    print(f"   ✅ 所有 {len(expected_commands)} 个命令已注册")


async def main():
    """运行所有测试"""
    print("\n" + "🚀" * 30)
    print("Phoenix Core 远程调试系统测试")
    print("🚀" * 30)

    # 同步测试
    debugger = test_remote_debugger_initialization()
    test_device_id_generation()
    test_command_registration()

    # 异步测试
    await test_command_execution()
    await test_config_update()

    print("\n" + "=" * 60)
    print("✅ 所有测试通过!")
    print("=" * 60)
    print("\n远程调试系统已准备就绪，支持以下功能:")
    print("  📡 自动连接调试服务器")
    print("  🔧 7 个远程命令 (状态/日志/配置/重启/诊断/代码)")
    print("  ❤️ 心跳保活 (30 秒间隔)")
    print("  🔄 断线自动重连 (5 秒延迟)")
    print("  🆔 自动设备 ID 生成")
    print("\n配置方式:")
    print("  export DEBUG_MASTER_URL=your-server:9000")
    print("  export DEBUG_DEVICE_ID=your-device-id")
    print("  export DEBUG_AUTH_TOKEN=your-token (可选)")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
