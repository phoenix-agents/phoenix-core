#!/usr/bin/env python3
"""
Bot Heartbeat Updater - Bot 心跳更新器

每个 Bot 在运行时定期更新 HEARTBEAT.md 文件
用于健康检查器检测 Bot 是否存活

Usage:
    在 Bot 启动时作为后台线程运行
"""

import logging
import time
from pathlib import Path
from datetime import datetime
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 10  # 每 10 秒更新一次心跳


class HeartbeatUpdater:
    """Bot 心跳更新器"""

    def __init__(self, bot_name: str):
        self.bot_name = bot_name
        self.workspace_dir = Path(__file__).parent / "workspaces/{bot_name}"
        self.heartbeat_file = self.workspace_dir / "HEARTBEAT.md"
        self.running = False
        self.thread: threading.Thread = None

    def _update_heartbeat(self):
        """更新心跳文件"""
        try:
            # 确保工作目录存在
            self.workspace_dir.mkdir(parents=True, exist_ok=True)

            # 写入心跳内容
            timestamp = datetime.now().isoformat()
            content = f"""# {self.bot_name} Heartbeat

**Last Update**: {timestamp}

## Status
- Bot: {self.bot_name}
- Timestamp: {timestamp}
- Status: Alive

## Recent Activity
- Last message: N/A
- Current task: N/A

---
_This file is auto-updated every {HEARTBEAT_INTERVAL} seconds_
"""
            with open(self.heartbeat_file, "w") as f:
                f.write(content)

            logger.debug(f"{self.bot_name} heartbeat updated: {timestamp}")

        except Exception as e:
            logger.error(f"{self.bot_name} failed to update heartbeat: {e}")

    def _run_loop(self):
        """心跳更新循环"""
        while self.running:
            try:
                self._update_heartbeat()
            except Exception as e:
                logger.error(f"{self.bot_name} heartbeat loop error: {e}")

            # 等待下一次更新
            for _ in range(HEARTBEAT_INTERVAL * 10):
                if not self.running:
                    break
                time.sleep(0.1)

    def start(self):
        """启动心跳更新"""
        if self.running:
            logger.warning(f"{self.bot_name} heartbeat already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

        # 立即更新一次
        self._update_heartbeat()

        logger.info(f"{self.bot_name} heartbeat updater started (interval: {HEARTBEAT_INTERVAL}s)")

    def stop(self):
        """停止心跳更新"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)

        # 最后一次更新
        self._update_heartbeat()

        logger.info(f"{self.bot_name} heartbeat updater stopped")


# 全局实例 (供 Bot 主程序调用)
_heartbeat_instance = None


def start_heartbeat(bot_name: str):
    """启动 Bot 心跳"""
    global _heartbeat_instance
    _heartbeat_instance = HeartbeatUpdater(bot_name)
    _heartbeat_instance.start()
    return _heartbeat_instance


def stop_heartbeat():
    """停止 Bot 心跳"""
    global _heartbeat_instance
    if _heartbeat_instance:
        _heartbeat_instance.stop()


def get_heartbeat_instance():
    """获取心跳实例"""
    return _heartbeat_instance


if __name__ == "__main__":
    # 命令行模式：指定 Bot 名称启动心跳
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 bot_heartbeat.py <bot_name>")
        sys.exit(1)

    bot_name = sys.argv[1]
    updater = HeartbeatUpdater(bot_name)

    try:
        updater.start()
        print(f"Heartbeat updater started for {bot_name}")
        print("Press Ctrl+C to stop")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping...")
        updater.stop()
        print("Stopped")
