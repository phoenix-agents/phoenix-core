#!/usr/bin/env python3
"""
Phoenix Core Heartbeat Monitor - 心跳监控

Bot 定期发送心跳到共享文件，Dashboard 读取心跳判断健康状态

Bot 端用法:
    from phoenix_core.heartbeat import HeartbeatSender

    sender = HeartbeatSender(bot_name="客服", workspace="./workspaces/客服")
    sender.start()  # 后台线程每 30 秒发送心跳

    # 程序退出时
    sender.stop()

Dashboard 端用法:
    from phoenix_core.heartbeat import HeartbeatMonitor

    monitor = HeartbeatMonitor(workspace="./workspaces")
    status = monitor.check_bot_health("客服")  # {"healthy": True, "last_seen": "..."}
    all_status = monitor.get_all_bots_status()  # {"客服": {...}, "运营": {...}}
"""

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class HeartbeatSender:
    """Bot 端心跳发送器"""

    def __init__(
        self,
        bot_name: str,
        workspace: str = ".",
        heartbeat_interval: int = 30,
        timeout: int = 90,
    ):
        """
        Args:
            bot_name: Bot 名称
            workspace: 工作空间目录
            heartbeat_interval: 心跳间隔 (秒)
            timeout: 超时阈值 (秒)，超过此时间未更新心跳视为不健康
        """
        self.bot_name = bot_name
        self.workspace = Path(workspace)
        self.heartbeat_interval = heartbeat_interval
        self.timeout = timeout

        # 心跳文件路径
        self.heartbeat_file = self.workspace / f".heartbeat_{bot_name}.json"

        # 线程控制
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _write_heartbeat(self):
        """写入心跳数据"""
        heartbeat_data = {
            "bot_name": self.bot_name,
            "timestamp": datetime.now().isoformat(),
            "pid": os.getpid(),
            "status": "running",
        }

        try:
            # 原子写入心跳文件
            self.heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.heartbeat_file.with_suffix(".tmp")

            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(heartbeat_data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, self.heartbeat_file)

        except Exception as e:
            print(f"[Heartbeat] 写入失败：{e}")

    def _heartbeat_loop(self):
        """心跳循环线程"""
        while not self._stop_event.is_set():
            self._write_heartbeat()

            # 等待间隔时间 (可被中断)
            self._stop_event.wait(timeout=self.heartbeat_interval)

        # 最后一次心跳 (停止前)
        self._write_heartbeat()
        print(f"[Heartbeat] {self.bot_name} 心跳已停止")

    def start(self):
        """启动心跳线程"""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        print(f"[Heartbeat] {self.bot_name} 心跳Started (间隔={self.heartbeat_interval}s)")

    def stop(self):
        """停止心跳线程"""
        if not self._thread or not self._thread.is_alive():
            return

        self._stop_event.set()
        self._thread.join(timeout=5)
        self._thread = None

    def cleanup(self):
        """清理心跳文件"""
        try:
            if self.heartbeat_file.exists():
                self.heartbeat_file.unlink()
        except Exception as e:
            print(f"[Heartbeat] 清理失败：{e}")


class HeartbeatMonitor:
    """Dashboard 端心跳监控器"""

    def __init__(self, workspace: str = ".", timeout: int = 90):
        """
        Args:
            workspace: 工作空间目录 (包含所有 Bot 子目录)
            timeout: 超时阈值 (秒)
        """
        self.workspace = Path(workspace)
        self.timeout = timeout

    def check_bot_health(self, bot_name: str) -> Dict:
        """
        检查单个 Bot 健康状态

        Returns:
            {
                "healthy": bool,
                "last_seen": str,
                "pid": int,
                "status": str,
                "seconds_ago": float
            }
        """
        heartbeat_file = self.workspace / f".heartbeat_{bot_name}.json"

        if not heartbeat_file.exists():
            return {
                "healthy": False,
                "last_seen": None,
                "pid": None,
                "status": "no_heartbeat_file",
                "seconds_ago": None,
                "error": "心跳文件不存在"
            }

        try:
            with open(heartbeat_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            timestamp_str = data.get("timestamp")
            if not timestamp_str:
                return {
                    "healthy": False,
                    "last_seen": None,
                    "pid": None,
                    "status": "invalid_heartbeat",
                    "seconds_ago": None,
                    "error": "心跳数据缺少 timestamp"
                }

            # 计算时间差
            heartbeat_time = datetime.fromisoformat(timestamp_str)
            now = datetime.now()
            delta = (now - heartbeat_time).total_seconds()

            healthy = delta < self.timeout

            return {
                "healthy": healthy,
                "last_seen": timestamp_str,
                "pid": data.get("pid"),
                "status": data.get("status", "unknown"),
                "seconds_ago": round(delta, 1),
                "timeout": self.timeout
            }

        except json.JSONDecodeError as e:
            return {
                "healthy": False,
                "last_seen": None,
                "pid": None,
                "status": "corrupted_heartbeat",
                "seconds_ago": None,
                "error": f"心跳文件损坏：{e}"
            }
        except Exception as e:
            return {
                "healthy": False,
                "last_seen": None,
                "pid": None,
                "status": "error",
                "seconds_ago": None,
                "error": str(e)
            }

    def get_all_bots_status(self, bot_names: Optional[list] = None) -> Dict[str, Dict]:
        """
        获取所有 Bot 健康状态

        Args:
            bot_names: Bot 名称列表，为 None 则扫描工作空间目录

        Returns:
            {"客服": {...}, "运营": {...}, ...}
        """
        if bot_names is None:
            # 扫描工作空间目录
            bot_names = []
            for item in self.workspace.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    bot_names.append(item.name)

        result = {}
        for bot_name in bot_names:
            result[bot_name] = self.check_bot_health(bot_name)

        return result

    def get_healthy_bots(self) -> list:
        """获取健康 Bot 列表"""
        all_status = self.get_all_bots_status()
        return [
            name for name, status in all_status.items()
            if status.get("healthy", False)
        ]

    def get_unhealthy_bots(self) -> list:
        """获取不健康 Bot 列表"""
        all_status = self.get_all_bots_status()
        return [
            name for name, status in all_status.items()
            if not status.get("healthy", False)
        ]


# 便捷函数
def send_heartbeat_once(bot_name: str, workspace: str = ".") -> bool:
    """发送一次心跳 (用于简单场景)"""
    sender = HeartbeatSender(bot_name, workspace)
    sender._write_heartbeat()
    return True


def check_health(bot_name: str, workspace: str = ".") -> Dict:
    """检查 Bot 健康状态 (用于简单场景)"""
    monitor = HeartbeatMonitor(workspace)
    return monitor.check_bot_health(bot_name)
