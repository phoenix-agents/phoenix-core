"""
Phoenix Core 远程调试客户端
主动连接中央调试服务器，支持日志推送、配置同步、代码接收
"""

import asyncio
import json
import os
import sys
import websockets
from datetime import datetime
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class RemoteDebugClient:
    """远程调试客户端"""

    def __init__(self, server_url: str, device_id: str, auth_token: str = ""):
        self.server_url = server_url
        self.device_id = device_id
        self.auth_token = auth_token
        self.ws = None
        self.connected = False
        self.project_dir = Path(__file__).parent
        self.reconnect_delay = 5  # 重连延迟 (秒)
        self.heartbeat_interval = 30  # 心跳间隔 (秒)

    async def connect(self):
        """连接到调试服务器"""
        ws_url = f"ws://{self.server_url}/ws/debug/{self.device_id}"
        if self.auth_token:
            ws_url += f"?token={self.auth_token}"

        try:
            self.ws = await websockets.connect(ws_url, ping_interval=20)
            self.connected = True
            logger.info(f"✅ 已连接到调试服务器：{self.server_url}")

            # 发送设备信息
            await self.send_device_info()

            return True
        except Exception as e:
            logger.error(f"❌ 连接失败：{e}")
            return False

    async def send_device_info(self):
        """发送设备信息到服务器"""
        info = {
            "type": "device_info",
            "info": {
                "hostname": os.uname().nodename,
                "platform": sys.platform,
                "python_version": sys.version,
                "default_model": os.environ.get("DEFAULT_MODEL", ""),
                "default_provider": os.environ.get("DEFAULT_PROVIDER", ""),
                "start_time": datetime.now().isoformat()
            }
        }
        await self.ws.send(json.dumps(info))

    async def send_log(self, level: str, message: str):
        """发送日志到服务器"""
        if self.ws and self.connected:
            try:
                await self.ws.send(json.dumps({
                    "type": "log",
                    "level": level,
                    "message": message
                }))
            except Exception:
                pass

    async def heartbeat_loop(self):
        """心跳循环"""
        while self.connected:
            try:
                await self.ws.send(json.dumps({
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat()
                }))
                # 等待心跳确认
                try:
                    response = await asyncio.wait_for(self.ws.recv(), timeout=10)
                    data = json.loads(response)
                    if data.get("type") == "heartbeat_ack":
                        logger.debug("❤️ 心跳确认")
                except asyncio.TimeoutError:
                    logger.warning("⚠️ 心跳超时")
            except Exception as e:
                logger.error(f"心跳错误：{e}")
                break
            await asyncio.sleep(self.heartbeat_interval)

    async def handle_message(self, message: dict):
        """处理服务器消息"""
        msg_type = message.get("type")

        if msg_type == "welcome":
            logger.info(f"📡 服务器响应：{message.get('message')}")

        elif msg_type == "command":
            command = message.get("command")
            args = message.get("args", {})
            logger.info(f"📥 收到命令：{command}")
            result = await self.execute_command(command, args)
            await self.ws.send(json.dumps({
                "type": "command_result",
                "command": command,
                "result": result
            }))

        elif msg_type == "code_update":
            files = message.get("files", [])
            logger.info(f"📥 收到代码更新：{len(files)} 个文件")
            result = await self.apply_code_update(files)
            await self.ws.send(json.dumps({
                "type": "code_update_ack",
                "success": result["success"],
                "message": result.get("message")
            }))

        elif msg_type == "config_update":
            config = message.get("config", {})
            logger.info(f"📥 收到配置更新")
            result = await self.update_config(config)
            await self.ws.send(json.dumps({
                "type": "config_update_ack",
                "success": result["success"]
            }))

        elif msg_type == "disconnect":
            logger.info(f"📴 服务器要求断开：{message.get('reason')}")
            self.connected = False

    async def execute_command(self, command: str, args: dict) -> dict:
        """执行远程命令"""
        try:
            if command == "restart":
                # 重启服务
                logger.info("🔄 正在重启服务...")
                os.system("pkill -f api_server.py || true")
                os.system("python3 api_server.py &")
                return {"success": True, "message": "服务已重启"}

            elif command == "reload_config":
                # 重新加载配置
                logger.info("📖 重新加载配置...")
                # 这里可以重新读取.env 文件
                return {"success": True, "message": "配置已重新加载"}

            elif command == "get_status":
                # 获取状态
                return {
                    "success": True,
                    "status": {
                        "cpu": "N/A",
                        "memory": "N/A",
                        "uptime": "N/A"
                    }
                }

            elif command == "get_logs":
                # 获取日志
                log_file = self.project_dir / "logs" / "api_server.log"
                if log_file.exists():
                    with open(log_file, "r") as f:
                        logs = f.readlines()[-100:]
                    return {"success": True, "logs": "".join(logs)}
                return {"success": True, "logs": "暂无日志"}

            else:
                return {"success": False, "message": f"未知命令：{command}"}

        except Exception as e:
            logger.error(f"命令执行失败：{e}")
            return {"success": False, "message": str(e)}

    async def apply_code_update(self, files: list) -> dict:
        """应用代码更新"""
        try:
            for file in files:
                path = file.get("path")
                content = file.get("content")

                if not path or not content:
                    continue

                # 计算完整路径
                full_path = self.project_dir / path

                # 创建目录
                full_path.parent.mkdir(parents=True, exist_ok=True)

                # 写入文件
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)

                logger.info(f"✅ 文件已更新：{path}")

            return {"success": True, "message": f"已更新 {len(files)} 个文件"}

        except Exception as e:
            logger.error(f"代码更新失败：{e}")
            return {"success": False, "message": str(e)}

    async def update_config(self, config: dict) -> dict:
        """更新配置"""
        try:
            env_file = self.project_dir / ".env"

            # 读取现有配置
            existing = {}
            if env_file.exists():
                with open(env_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            existing[key] = value

            # 更新配置
            existing.update(config)

            # 写回文件
            with open(env_file, "w") as f:
                for key, value in existing.items():
                    f.write(f"{key}={value}\n")

            # 更新 os.environ
            for key, value in config.items():
                os.environ[key] = value

            logger.info(f"✅ 配置已更新")
            return {"success": True}

        except Exception as e:
            logger.error(f"配置更新失败：{e}")
            return {"success": False, "message": str(e)}

    async def run(self):
        """运行客户端"""
        while True:
            try:
                if not await self.connect():
                    logger.info(f"⏳ {self.reconnect_delay}秒后重试...")
                    await asyncio.sleep(self.reconnect_delay)
                    continue

                # 启动心跳
                heartbeat_task = asyncio.create_task(self.heartbeat_loop())

                # 监听服务器消息
                try:
                    async for message in self.ws:
                        try:
                            data = json.loads(message)
                            await self.handle_message(data)
                        except json.JSONDecodeError:
                            logger.error(f"无效 JSON: {message}")
                except websockets.ConnectionClosed:
                    logger.warning("连接已关闭")

                heartbeat_task.cancel()

            except Exception as e:
                logger.error(f"错误：{e}")

            self.connected = False
            logger.info(f"⏳ {self.reconnect_delay}秒后重连...")
            await asyncio.sleep(self.reconnect_delay)


# ============ 集成到 api_server.py 的钩子 ============

def start_remote_debug():
    """启动远程调试客户端（从 api_server.py 调用）"""
    server_url = os.environ.get("DEBUG_MASTER_URL")
    device_id = os.environ.get("DEBUG_DEVICE_ID")
    auth_token = os.environ.get("DEBUG_AUTH_TOKEN", "")

    if not server_url or not device_id:
        logger.info("📡 远程调试未启用 (缺少 DEBUG_MASTER_URL 或 DEBUG_DEVICE_ID)")
        return None

    logger.info(f"📡 启动远程调试客户端...")
    logger.info(f"   服务器：{server_url}")
    logger.info(f"   设备 ID: {device_id}")

    client = RemoteDebugClient(server_url, device_id, auth_token)

    # 在后台线程运行
    import threading
    thread = threading.Thread(target=lambda: asyncio.run(client.run()), daemon=True)
    thread.start()

    return client


# ============ 独立运行 ============

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Phoenix Core 远程调试客户端")
    parser.add_argument("--server", required=True, help="调试服务器地址 (host:port)")
    parser.add_argument("--device-id", required=True, help="设备 ID")
    parser.add_argument("--token", default="", help="认证 Token")

    args = parser.parse_args()

    print(f"""
╔════════════════════════════════════════════════════════╗
║     Phoenix Core 远程调试客户端                          ║
╠════════════════════════════════════════════════════════╣
║  服务器：{args.server}
║  设备 ID: {args.device_id}
║  状态：正在连接...
╚════════════════════════════════════════════════════════╝
    """)

    client = RemoteDebugClient(args.server, args.device_id, args.token)
    asyncio.run(client.run())
