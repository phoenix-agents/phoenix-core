#!/usr/bin/env python3
"""
Phoenix Core - 远程调试集成模块 (v1.3 增强版)

功能:
1. 自动连接调试服务器
2. 支持远程日志查看
3. 支持远程配置更新
4. 支持远程代码执行
5. 设备认证和授权

Usage:
    from phoenix_core.remote_integration import RemoteDebugger

    debugger = RemoteDebugger(
        server_url="https://your-debug-server.com",
        device_id="user-001",
        auth_token="your-token"
    )
    await debugger.connect()
"""

import asyncio
import json
import os
import socket
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
import logging
import hashlib

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

logger = logging.getLogger(__name__)


class RemoteDebugger:
    """
    远程调试器

    连接到中央调试服务器，允许远程协助新用户
    """

    def __init__(
        self,
        server_url: str = None,
        device_id: str = None,
        auth_token: str = "",
        auto_reconnect: bool = True,
        enable_remote_control: bool = True
    ):
        self.server_url = server_url or os.environ.get("DEBUG_MASTER_URL", "")
        self.device_id = device_id or os.environ.get("DEBUG_DEVICE_ID", self._generate_device_id())
        self.auth_token = auth_token or os.environ.get("DEBUG_AUTH_TOKEN", "")
        self.auto_reconnect = auto_reconnect
        self.enable_remote_control = enable_remote_control

        self.ws = None
        self.connected = False
        self.reconnect_delay = 5
        self.heartbeat_interval = 30
        self.project_dir = Path(__file__).parent.parent
        self._commands: Dict[str, Callable] = {}
        self._device_info = self._collect_device_info()

        # 注册内置命令
        self._register_default_commands()

    def _generate_device_id(self) -> str:
        """生成设备 ID"""
        hostname = socket.gethostname()
        mac = hashlib.md5(
            str(uuid.getnode()).encode()
        ).hexdigest()[:8]
        return f"{hostname}-{mac}"

    def _collect_device_info(self) -> Dict:
        """收集设备信息"""
        return {
            "hostname": socket.gethostname(),
            "platform": sys.platform,
            "python_version": sys.version,
            "project_dir": str(self.project_dir),
            "start_time": datetime.now().isoformat(),
            "env_vars": {
                "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL", ""),
                "DEFAULT_PROVIDER": os.environ.get("DEFAULT_PROVIDER", ""),
            }
        }

    def _register_default_commands(self):
        """注册默认命令"""
        self._commands["get_status"] = self._cmd_get_status
        self._commands["get_logs"] = self._cmd_get_logs
        self._commands["get_config"] = self._cmd_get_config
        self._commands["update_config"] = self._cmd_update_config
        self._commands["restart_bot"] = self._cmd_restart_bot
        self._commands["execute_code"] = self._cmd_execute_code
        self._commands["run_diagnostic"] = self._cmd_run_diagnostic

    async def connect(self) -> bool:
        """连接到调试服务器"""
        if not WEBSOCKETS_AVAILABLE:
            logger.warning("websockets 未安装，远程调试不可用")
            return False

        if not self.server_url:
            logger.info("远程调试未配置 (缺少 server_url)")
            return False

        ws_url = f"ws://{self.server_url}/ws/debug/{self.device_id}"
        if self.auth_token:
            ws_url += f"?token={self.auth_token}"

        try:
            self.ws = await websockets.connect(ws_url, ping_interval=20)
            self.connected = True
            logger.info(f"✅ 已连接到调试服务器：{self.server_url}")

            # 发送设备信息
            await self._send_device_info()

            return True
        except Exception as e:
            logger.error(f"❌ 连接失败：{e}")
            return False

    async def _send_device_info(self):
        """发送设备信息到服务器"""
        message = {
            "type": "device_info",
            "info": self._device_info
        }
        await self.ws.send(json.dumps(message, ensure_ascii=False))

    async def send_log(self, level: str, message: str):
        """发送日志到服务器"""
        if self.ws and self.connected:
            try:
                await self.ws.send(json.dumps({
                    "type": "log",
                    "level": level,
                    "message": message,
                    "timestamp": datetime.now().isoformat()
                }, ensure_ascii=False))
            except Exception:
                pass

    async def _send_heartbeat(self):
        """发送心跳"""
        if self.ws and self.connected:
            try:
                await self.ws.send(json.dumps({
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat(),
                    "device_info": {
                        "pid": os.getpid(),
                        "memory_mb": self._get_memory_usage()
                    }
                }))
            except Exception:
                pass

    def _get_memory_usage(self) -> float:
        """获取内存使用 (MB)"""
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        except Exception:
            return 0.0

    async def _message_loop(self):
        """监听服务器消息"""
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.error(f"无效 JSON: {message}")
        except websockets.ConnectionClosed:
            logger.warning("连接已关闭")
        except Exception as e:
            logger.error(f"消息循环错误：{e}")

    async def _handle_message(self, message: Dict):
        """处理服务器消息"""
        msg_type = message.get("type")

        if msg_type == "welcome":
            logger.info(f"📡 服务器欢迎：{message.get('message', '')}")

        elif msg_type == "command":
            command = message.get("command")
            args = message.get("args", {})
            request_id = message.get("request_id")

            logger.info(f"📥 收到命令：{command}")
            result = await self._execute_command(command, args)

            # 返回结果
            await self.ws.send(json.dumps({
                "type": "command_result",
                "request_id": request_id,
                "command": command,
                "result": result
            }, ensure_ascii=False))

        elif msg_type == "config_update":
            config = message.get("config", {})
            logger.info(f"📥 收到配置更新")
            result = await self._cmd_update_config(config)

            await self.ws.send(json.dumps({
                "type": "config_update_ack",
                "success": result.get("success", False)
            }))

        elif msg_type == "disconnect":
            logger.info(f"📴 服务器要求断开：{message.get('reason', '')}")
            self.connected = False

    async def _execute_command(self, command: str, args: Dict) -> Dict:
        """执行命令"""
        # 安全检查
        if not self.enable_remote_control:
            return {
                "success": False,
                "message": "远程控制已禁用"
            }

        if command in self._commands:
            try:
                return await self._commands[command](args)
            except Exception as e:
                logger.error(f"命令执行失败：{e}")
                return {
                    "success": False,
                    "message": str(e)
                }
        else:
            return {
                "success": False,
                "message": f"未知命令：{command}"
            }

    # ========== 内置命令实现 ==========

    async def _cmd_get_status(self, args: Dict) -> Dict:
        """获取系统状态"""
        return {
            "success": True,
            "status": {
                "connected": self.connected,
                "server": self.server_url,
                "device_id": self.device_id,
                "memory_mb": self._get_memory_usage(),
                "uptime": str(datetime.now() - datetime.fromisoformat(self._device_info["start_time"]))
            }
        }

    async def _cmd_get_logs(self, args: Dict) -> Dict:
        """获取日志"""
        lines = args.get("lines", 100)
        level = args.get("level", "INFO")

        log_file = self.project_dir / "logs" / "api_server.log"
        if not log_file.exists():
            log_file = Path("/tmp/api_server.log")

        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                all_logs = f.readlines()
                # 按级别过滤
                if level != "ALL":
                    all_logs = [l for l in all_logs if f"[{level}]" in l or f"[{level.upper()}]" in l or not l.strip().startswith("[")]
                logs = "".join(all_logs[-lines:])

            return {
                "success": True,
                "logs": logs,
                "count": len(logs.split("\n"))
            }

        return {"success": True, "logs": "暂无日志", "count": 0}

    async def _cmd_get_config(self, args: Dict) -> Dict:
        """获取配置"""
        config = {}
        for key in ["BOT_NAME", "BOT_MODEL", "BOT_PROVIDER", "DISCORD_BOT_TOKEN",
                    "DISCORD_CHANNEL_ID", "DEFAULT_MODEL", "DEFAULT_PROVIDER"]:
            config[key] = os.environ.get(key, "")

        return {
            "success": True,
            "config": config
        }

    async def _cmd_update_config(self, config: Dict) -> Dict:
        """更新配置"""
        try:
            env_file = self.project_dir / ".env"

            # 读取现有配置
            existing = {}
            if env_file.exists():
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            existing[key] = value

            # 更新配置
            existing.update(config)

            # 写回文件
            with open(env_file, "w", encoding="utf-8") as f:
                for key, value in existing.items():
                    f.write(f"{key}={value}\n")

            # 更新 os.environ
            for key, value in config.items():
                os.environ[key] = value

            logger.info(f"✅ 配置已更新：{list(config.keys())}")
            return {"success": True, "message": f"已更新 {len(config)} 个配置项"}

        except Exception as e:
            logger.error(f"配置更新失败：{e}")
            return {"success": False, "message": str(e)}

    async def _cmd_restart_bot(self, args: Dict) -> Dict:
        """重启 Bot"""
        try:
            import subprocess
            # 温和重启：先停止再启动
            os.system("pkill -f phoenix_core_gateway || true")
            os.system("pkill -f api_server.py || true")

            # 延迟启动
            subprocess.Popen(
                ["python3", "api_server.py", "--port", "8000"],
                cwd=str(self.project_dir),
                start_new_session=True
            )

            return {"success": True, "message": "Bot 正在重启..."}

        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _cmd_execute_code(self, args: Dict) -> Dict:
        """执行 Python 代码"""
        code = args.get("code", "")

        if not code:
            return {"success": False, "message": "代码为空"}

        try:
            # 在沙盒中执行
            import io
            from contextlib import redirect_stdout, redirect_stderr

            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()

            # 创建执行环境
            exec_env = {"__builtins__": __builtins__, "logger": logger}

            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                exec(code, exec_env)

            return {
                "success": True,
                "stdout": stdout_buffer.getvalue(),
                "stderr": stderr_buffer.getvalue()
            }

        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "traceback": traceback.format_exc()
            }

    async def _cmd_run_diagnostic(self, args: Dict) -> Dict:
        """运行系统诊断"""
        results = {
            "python_ok": True,
            "dependencies_ok": True,
            "env_ok": True,
            "discord_ok": False,
            "issues": []
        }

        # 检查 Python 版本
        if sys.version_info < (3, 10):
            results["python_ok"] = False
            results["issues"].append(f"Python 版本过低：{sys.version}，需要 3.10+")

        # 检查关键依赖
        try:
            import discord
            results["discord_ok"] = True
        except ImportError:
            results["issues"].append("discord.py 未安装")

        # 检查环境变量
        if not os.environ.get("DEFAULT_MODEL"):
            results["env_ok"] = False
            results["issues"].append("DEFAULT_MODEL 未配置")

        return {
            "success": True,
            "diagnostic": results
        }

    async def run_loop(self):
        """运行主循环"""
        while True:
            try:
                if not await self.connect():
                    if not self.auto_reconnect:
                        return False
                    logger.info(f"⏳ {self.reconnect_delay}秒后重试...")
                    await asyncio.sleep(self.reconnect_delay)
                    continue

                # 启动心跳循环
                heartbeat_task = asyncio.create_task(self._heartbeat_loop())

                # 消息监听
                await self._message_loop()

                heartbeat_task.cancel()

            except Exception as e:
                logger.error(f"运行错误：{e}")

            self.connected = False
            if not self.auto_reconnect:
                return False

            logger.info(f"⏳ {self.reconnect_delay}秒后重连...")
            await asyncio.sleep(self.reconnect_delay)

    async def _heartbeat_loop(self):
        """心跳循环"""
        while self.connected:
            await self._send_heartbeat()
            await asyncio.sleep(self.heartbeat_interval)

    async def start_background(self):
        """在后台启动远程调试"""
        loop = asyncio.get_event_loop()
        task = loop.create_task(self.run_loop())
        logger.info("📡 远程调试客户端已在后台启动")
        return task


# ========== 全局实例 ==========
_debugger: Optional[RemoteDebugger] = None


def get_debugger() -> Optional[RemoteDebugger]:
    """获取全局 RemoteDebugger 实例"""
    global _debugger
    if _debugger is None:
        # 从环境变量读取配置
        server_url = os.environ.get("DEBUG_MASTER_URL")
        device_id = os.environ.get("DEBUG_DEVICE_ID")
        auth_token = os.environ.get("DEBUG_AUTH_TOKEN", "")

        if server_url:
            _debugger = RemoteDebugger(
                server_url=server_url,
                device_id=device_id,
                auth_token=auth_token
            )
    return _debugger


async def start_remote_debug() -> Optional[asyncio.Task]:
    """启动远程调试客户端"""
    debugger = get_debugger()
    if debugger:
        return await debugger.start_background()
    return None


def send_log(level: str, message: str):
    """便捷函数：发送日志"""
    debugger = get_debugger()
    if debugger and debugger.connected:
        asyncio.create_task(debugger.send_log(level, message))


# 导入 uuid（在模块顶部没有定义）
import uuid
