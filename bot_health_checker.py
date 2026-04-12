#!/usr/bin/env python3
"""
Bot Health Checker - 健康检查 + 自动重启

功能:
1. 每 30 秒心跳检测
2. 无心跳自动重启
3. 连续 3 次失败告警
4. PID 文件同步检查

Usage:
    python3 bot_health_checker.py start      # 启动健康检查
    python3 bot_health_checker.py status     # 查看检查状态
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
HEARTBEAT_INTERVAL = 30  # 心跳检测间隔 (秒)
HEARTBEAT_TIMEOUT = 60   # 心跳超时阈值 (秒)
MAX_FAILURES = 3         # 最大失败次数后告警
HEARTBEAT_PORT = 8765    # 健康检查服务端口

PID_FILE = Path("/tmp/phoenix_bots.pid.json")
HEALTH_FILE = Path("/tmp/phoenix_health.json")
PHOENIX_CORE_DIR = Path(__file__).parent
WORKSPACES_DIR = PHOENIX_CORE_DIR / "workspaces"


class BotHealthStatus:
    """单个 Bot 的健康状态"""

    def __init__(self, bot_name: str):
        self.bot_name = bot_name
        self.last_heartbeat: Optional[datetime] = None
        self.consecutive_failures = 0
        self.total_restarts = 0
        self.last_restart: Optional[datetime] = None
        self.status = "unknown"  # unknown, healthy, unhealthy, critical
        self.pid: Optional[int] = None

    def to_dict(self) -> Dict:
        return {
            "bot_name": self.bot_name,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "consecutive_failures": self.consecutive_failures,
            "total_restarts": self.total_restarts,
            "last_restart": self.last_restart.isoformat() if self.last_restart else None,
            "status": self.status,
            "pid": self.pid
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "BotHealthStatus":
        status = cls(data["bot_name"])
        status.last_heartbeat = datetime.fromisoformat(data["last_heartbeat"]) if data.get("last_heartbeat") else None
        status.consecutive_failures = data.get("consecutive_failures", 0)
        status.total_restarts = data.get("total_restarts", 0)
        status.last_restart = datetime.fromisoformat(data["last_restart"]) if data.get("last_restart") else None
        status.status = data.get("status", "unknown")
        status.pid = data.get("pid")
        return status


class HealthChecker:
    """健康检查器"""

    def __init__(self):
        self.bot_statuses: Dict[str, BotHealthStatus] = {}
        self.running = False
        self.check_thread: Optional[threading.Thread] = None
        self.alert_thread: Optional[threading.Thread] = None
        self._load_health_status()

    def _load_health_status(self):
        """从磁盘加载健康状态"""
        if HEALTH_FILE.exists():
            try:
                with open(HEALTH_FILE, "r") as f:
                    data = json.load(f)
                    for bot_data in data.get("bots", []):
                        self.bot_statuses[bot_data["bot_name"]] = BotHealthStatus.from_dict(bot_data)
                logger.info(f"Loaded health status for {len(self.bot_statuses)} bots")
            except Exception as e:
                logger.error(f"Failed to load health status: {e}")

    def _save_health_status(self):
        """保存健康状态到磁盘"""
        try:
            data = {
                "last_updated": datetime.now().isoformat(),
                "bots": [status.to_dict() for status in self.bot_statuses.values()]
            }
            with open(HEALTH_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save health status: {e}")

    def _load_pids(self) -> Dict[str, int]:
        """从 PID 文件加载"""
        if PID_FILE.exists():
            with open(PID_FILE, "r") as f:
                return json.load(f)
        return {}

    def _is_process_running(self, pid: int) -> bool:
        """检查进程是否运行"""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _check_bot_heartbeat(self, bot_name: str) -> bool:
        """
        检查单个 Bot 的心跳

        心跳检查方式:
        1. 检查 PID 文件中的进程
        2. 检查 workspace 中的 HEARTBEAT.md 文件 (最近 60 秒内更新)
        """
        pids = self._load_pids()
        status = self.bot_statuses.get(bot_name)

        if not status:
            status = BotHealthStatus(bot_name)
            self.bot_statuses[bot_name] = status

        # 检查 1: PID 文件
        if bot_name in pids:
            pid = pids[bot_name]
            if self._is_process_running(pid):
                status.pid = pid
                status.last_heartbeat = datetime.now()
                status.consecutive_failures = 0
                status.status = "healthy"
                return True
            else:
                logger.warning(f"{bot_name} PID {pid} is stale")

        # 检查 2: HEARTBEAT.md 文件
        heartbeat_file = WORKSPACES_DIR / bot_name / "HEARTBEAT.md"
        if heartbeat_file.exists():
            try:
                mtime = datetime.fromtimestamp(heartbeat_file.stat().st_mtime)
                if datetime.now() - mtime < timedelta(seconds=HEARTBEAT_TIMEOUT):
                    status.last_heartbeat = mtime
                    status.consecutive_failures = 0
                    status.status = "healthy"
                    return True
                else:
                    logger.warning(f"{bot_name} heartbeat stale: {mtime}")
            except Exception as e:
                logger.error(f"Failed to check heartbeat file for {bot_name}: {e}")

        # 心跳失败
        status.consecutive_failures += 1
        if status.consecutive_failures >= MAX_FAILURES:
            status.status = "critical"
        else:
            status.status = "unhealthy"

        return False

    def _restart_bot(self, bot_name: str):
        """重启 Bot"""
        logger.info(f"Restarting {bot_name}...")

        status = self.bot_statuses.get(bot_name)
        if status:
            status.total_restarts += 1
            status.last_restart = datetime.now()

        # 清理旧的 PID
        pids = self._load_pids()
        if bot_name in pids:
            del pids[bot_name]
            with open(PID_FILE, "w") as f:
                json.dump(pids, f, indent=2)

        # 启动 Bot
        workspace = WORKSPACES_DIR / bot_name
        env_file = workspace / ".env"

        if not env_file.exists():
            logger.error(f"Cannot restart {bot_name}: .env not found")
            return

        # 读取 Bot 配置
        bot_model = None
        with open(env_file, "r") as f:
            for line in f:
                if line.startswith("BOT_MODEL="):
                    bot_model = line.split("=")[1].strip()
                    break

        if not bot_model:
            logger.error(f"Cannot restart {bot_name}: BOT_MODEL not found")
            return

        # 加载环境
        env = os.environ.copy()
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env[key.strip()] = value.strip()

        env["PHOENIX_HOME"] = str(Path.home() / ".phoenix")
        env["PHOENIX_BOT"] = bot_name
        env["PHOENIX_WORKSPACE"] = str(workspace)

        # 启动进程
        phoenix_dir = Path.home() / ".phoenix" / "phoenix-agent"
        log_file = workspace / "bot.log"

        try:
            process = subprocess.Popen(
                [sys.executable, str(phoenix_dir / "gateway" / "run.py")],
                env=env,
                cwd=str(phoenix_dir),
                stdout=open(log_file, "w"),
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )

            # 更新 PID 文件
            pids = self._load_pids()
            pids[bot_name] = process.pid
            with open(PID_FILE, "w") as f:
                json.dump(pids, f, indent=2)

            if status:
                status.pid = process.pid

            logger.info(f"Restarted {bot_name} (PID: {process.pid})")

        except Exception as e:
            logger.error(f"Failed to restart {bot_name}: {e}")

    def _send_alert(self, bot_name: str, message: str):
        """发送告警"""
        alert_file = WORKSPACES_DIR / "alert_log.md"
        timestamp = datetime.now().isoformat()

        alert_entry = f"""
## [{timestamp}] {bot_name} 告警

{message}

连续失败次数：{self.bot_statuses.get(bot_name, BotHealthStatus(bot_name)).consecutive_failures}
总重启次数：{self.bot_statuses.get(bot_name, BotHealthStatus(bot_name)).total_restarts}

---
"""
        try:
            with open(alert_file, "a") as f:
                f.write(alert_entry)
            logger.warning(f"ALERT: {bot_name} - {message}")
        except Exception as e:
            logger.error(f"Failed to write alert: {e}")

    def _check_all_bots(self):
        """检查所有 Bot"""
        logger.debug("Running health check...")

        for bot_name in ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]:
            # 确保状态对象存在
            if bot_name not in self.bot_statuses:
                self.bot_statuses[bot_name] = BotHealthStatus(bot_name)

            is_healthy = self._check_bot_heartbeat(bot_name)

            if not is_healthy:
                status = self.bot_statuses[bot_name]

                # 连续失败达到阈值，发送告警并重启
                if status.consecutive_failures >= MAX_FAILURES:
                    self._send_alert(
                        bot_name,
                        f"Bot 心跳检测失败 {MAX_FAILURES} 次，正在自动重启..."
                    )
                    self._restart_bot(bot_name)

                # 如果不健康但还没到告警阈值，尝试重启
                elif status.consecutive_failures > 0:
                    logger.warning(f"{bot_name} unhealthy, failures: {status.consecutive_failures}")
                    # 失败 1 次就尝试重启，不等待
                    self._restart_bot(bot_name)

            self._save_health_status()

    def _run_health_check_loop(self):
        """健康检查循环"""
        while self.running:
            try:
                self._check_all_bots()
            except Exception as e:
                logger.error(f"Health check error: {e}")

            # 等待下一次检查
            for _ in range(HEARTBEAT_INTERVAL * 10):
                if not self.running:
                    break
                time.sleep(0.1)

    def start(self):
        """启动健康检查"""
        if self.running:
            logger.warning("Health checker already running")
            return

        self.running = True
        self.check_thread = threading.Thread(target=self._run_health_check_loop, daemon=True)
        self.check_thread.start()

        logger.info(f"Health checker started (interval: {HEARTBEAT_INTERVAL}s)")
        logger.info(f"Monitoring {len(self.bot_statuses)} bots")

    def stop(self):
        """停止健康检查"""
        self.running = False
        if self.check_thread:
            self.check_thread.join(timeout=5)
        self._save_health_status()
        logger.info("Health checker stopped")

    def get_status(self) -> Dict:
        """获取健康状态"""
        self._check_all_bots()  # 先刷新一次

        return {
            "running": self.running,
            "last_check": datetime.now().isoformat(),
            "bots": {name: status.to_dict() for name, status in self.bot_statuses.items()}
        }


# HTTP 服务用于状态查询
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            health_checker._check_all_bots()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(health_checker.get_status(), indent=2).encode())
        elif self.path == "/status":
            health_checker._check_all_bots()
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()

            status = health_checker.get_status()
            output = ["Phoenix Core Bot Health Status", "=" * 50]

            for bot_name, bot_status in status["bots"].items():
                emoji = "🟢" if bot_status["status"] == "healthy" else "🟡" if bot_status["status"] == "unhealthy" else "🔴"
                output.append(f"{emoji} {bot_name}: {bot_status['status']} (failures: {bot_status['consecutive_failures']}, restarts: {bot_status['total_restarts']})")

            output.append("=" * 50)
            self.wfile.write("\n".join(output).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress HTTP logs


health_checker = HealthChecker()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "start":
        health_checker.start()

        # 启动 HTTP 服务
        server = HTTPServer(("localhost", HEALTHBEAT_PORT), HealthHandler)
        logger.info(f"Health status server running on port {HEALTHBEAT_PORT}")

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            health_checker.stop()
            server.shutdown()

    elif command == "stop":
        health_checker.stop()
        logger.info("Health checker stopped")

    elif command == "status":
        status = health_checker.get_status()
        print("\nPhoenix Core Bot Health Status")
        print("=" * 50)

        for bot_name, bot_status in status["bots"].items():
            emoji = "🟢" if bot_status["status"] == "healthy" else "🟡" if bot_status["status"] == "unhealthy" else "🔴"
            print(f"{emoji} {bot_name}: {bot_status['status']}")
            print(f"    Last heartbeat: {bot_status['last_heartbeat'] or 'N/A'}")
            print(f"    Failures: {bot_status['consecutive_failures']}, Restarts: {bot_status['total_restarts']}")

        print("=" * 50)

    elif command == "check":
        # 手动执行一次检查
        health_checker._check_all_bots()
        status = health_checker.get_status()
        print(json.dumps(status, indent=2))

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
